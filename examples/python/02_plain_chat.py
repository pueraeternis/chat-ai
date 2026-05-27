"""Plain text chat (non-streaming)."""

from openai import OpenAI
from settings import api_key, base_url, model_id, print_json


def main() -> None:
    client = OpenAI(base_url=base_url(), api_key=api_key(), timeout=300.0)
    response = client.chat.completions.create(
        model=model_id(),
        messages=[
            {
                "role": "user",
                "content": "What is 17 + 25? Reply with the number only.",
            },
        ],
        max_tokens=64,
        temperature=0,
    )
    print(f"POST {base_url()}/chat/completions\n")
    print_json("response", response)


if __name__ == "__main__":
    main()
