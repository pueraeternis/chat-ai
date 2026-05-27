"""Vision: describe a local image via image_url (base64 data URL)."""

from __future__ import annotations

import base64
import mimetypes
import sys
from pathlib import Path

from openai import OpenAI
from settings import api_key, base_url, model_id, print_json


def image_to_data_url(path: Path) -> str:
    raw = path.read_bytes()
    mime, _ = mimetypes.guess_type(path.name)
    if not mime or not mime.startswith("image/"):
        mime = "image/jpeg"
    b64 = base64.standard_b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path-to-image>", file=sys.stderr)
        sys.exit(1)

    image_path = Path(sys.argv[1])
    if not image_path.is_file():
        print(f"File not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(base_url=base_url(), api_key=api_key(), timeout=300.0)
    data_url = image_to_data_url(image_path)
    response = client.chat.completions.create(
        model=model_id(),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Describe this image in one or two sentences.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            },
        ],
        max_tokens=256,
        temperature=0.2,
    )
    print(f"POST {base_url()}/chat/completions (vision)\n")
    print_json("response", response)


if __name__ == "__main__":
    main()
