"""Plain text chat with SSE streaming (one JSON object per chunk)."""

import json

from openai import OpenAI
from settings import api_key, base_url, model_id


def main() -> None:
    client = OpenAI(base_url=base_url(), api_key=api_key(), timeout=300.0)
    stream = client.chat.completions.create(
        model=model_id(),
        messages=[
            {
                "role": "user",
                "content": "Count from 1 to 5, one number per line.",
            },
        ],
        max_tokens=64,
        temperature=0,
        stream=True,
    )
    print(f"POST {base_url()}/chat/completions (stream=true)\n")
    print("=== stream chunks (chat.completion.chunk per line) ===")
    for chunk in stream:
        print(json.dumps(chunk.model_dump(), ensure_ascii=False))


if __name__ == "__main__":
    main()
