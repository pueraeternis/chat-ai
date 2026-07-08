"""Measure streaming latency: time-to-first-token (TTFT) and tokens/sec."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from settings import api_key, base_url, model_id


@dataclass(frozen=True)
class StreamMetrics:
    ttft_s: float
    generation_s: float
    total_s: float
    completion_tokens: int
    prompt_tokens: int | None
    tokens_per_sec: float | None

    @property
    def tokens_per_sec_including_ttft(self) -> float | None:
        if self.completion_tokens <= 0 or self.total_s <= 0:
            return None
        return self.completion_tokens / self.total_s


def _has_content_token(delta: dict[str, Any]) -> bool:
    content = delta.get("content")
    reasoning = delta.get("reasoning_content")
    return bool(content) or bool(reasoning)


def _parse_sse_events(raw: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in raw.split(b"\n\n"):
        if not block.strip():
            continue
        data_lines = [
            line[6:]
            for line in block.split(b"\n")
            if line.startswith(b"data: ")
        ]
        if not data_lines:
            continue
        payload = b"\n".join(data_lines).decode("utf-8")
        if payload == "[DONE]":
            events.append({"done": True})
            continue
        events.append(json.loads(payload))
    return events


def measure_stream(
    *,
    prompt: str,
    max_tokens: int,
    temperature: float,
    timeout_s: float,
) -> StreamMetrics:
    body = {
        "model": model_id(),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    request = Request(
        f"{base_url()}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    started = time.perf_counter()
    first_token_at: float | None = None
    last_token_at: float | None = None
    completion_tokens = 0
    prompt_tokens: int | None = None

    with urlopen(request, timeout=timeout_s) as response:
        buffer = b""
        while True:
            chunk = response.read(4096)
            if not chunk:
                break
            buffer += chunk
            while b"\n\n" in buffer:
                event_bytes, buffer = buffer.split(b"\n\n", 1)
                for event in _parse_sse_events(event_bytes + b"\n\n"):
                    if event.get("done"):
                        continue
                    usage = event.get("usage")
                    if isinstance(usage, dict):
                        completion_tokens = int(usage.get("completion_tokens") or 0)
                        prompt_tokens_val = usage.get("prompt_tokens")
                        if prompt_tokens_val is not None:
                            prompt_tokens = int(prompt_tokens_val)
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    if _has_content_token(delta):
                        now = time.perf_counter()
                        if first_token_at is None:
                            first_token_at = now
                        last_token_at = now

    finished = time.perf_counter()
    if first_token_at is None:
        raise RuntimeError("stream finished without content tokens")

    ttft_s = first_token_at - started
    generation_s = (last_token_at or first_token_at) - first_token_at
    total_s = finished - started
    tokens_per_sec = (
        completion_tokens / generation_s if completion_tokens > 0 and generation_s > 0 else None
    )
    return StreamMetrics(
        ttft_s=ttft_s,
        generation_s=generation_s,
        total_s=total_s,
        completion_tokens=completion_tokens,
        prompt_tokens=prompt_tokens,
        tokens_per_sec=tokens_per_sec,
    )


def _fmt_seconds(value: float) -> str:
    if value >= 1:
        return f"{value:.2f}s"
    return f"{value * 1000:.0f}ms"


def _print_summary(label: str, runs: list[StreamMetrics]) -> None:
    ttfts = [run.ttft_s for run in runs]
    tps = [run.tokens_per_sec for run in runs if run.tokens_per_sec is not None]
    print(f"\n=== {label} ({len(runs)} run(s)) ===")
    print(f"model: {model_id()}")
    print(f"endpoint: {base_url()}/chat/completions")
    print(f"TTFT: median {_fmt_seconds(statistics.median(ttfts))}, "
          f"min {_fmt_seconds(min(ttfts))}, max {_fmt_seconds(max(ttfts))}")
    if tps:
        print(
            f"Generation speed: median {statistics.median(tps):.1f} tok/s, "
            f"min {min(tps):.1f}, max {max(tps):.1f}"
        )
    print("\nPer run:")
    for index, run in enumerate(runs, start=1):
        tps_text = f"{run.tokens_per_sec:.1f} tok/s" if run.tokens_per_sec else "n/a"
        print(
            f"  {index}. TTFT {_fmt_seconds(run.ttft_s)}, "
            f"generation {_fmt_seconds(run.generation_s)}, "
            f"tokens {run.completion_tokens}, "
            f"speed {tps_text}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prompt",
        default="Explain what a binary search tree is in 3 short paragraphs.",
        help="User prompt for the benchmark request",
    )
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--warmup",
        action="store_true",
        help="Run one throwaway request before measuring",
    )
    args = parser.parse_args()

    if args.warmup:
        print("Warmup request...")
        measure_stream(
            prompt="Say hi.",
            max_tokens=8,
            temperature=0.0,
            timeout_s=args.timeout,
        )

    runs: list[StreamMetrics] = []
    for index in range(args.runs):
        print(f"Run {index + 1}/{args.runs}...", flush=True)
        try:
            runs.append(
                measure_stream(
                    prompt=args.prompt,
                    max_tokens=args.max_tokens,
                    temperature=args.temperature,
                    timeout_s=args.timeout,
                )
            )
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            print(f"Benchmark failed: {exc}", file=sys.stderr)
            return 1

    _print_summary("Streaming benchmark", runs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
