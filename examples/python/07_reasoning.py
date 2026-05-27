"""Optional reasoning (enable_thinking) — no tools in the same request."""

from openai import OpenAI
from settings import api_key, base_url, model_id, print_json


def main() -> None:
    client = OpenAI(base_url=base_url(), api_key=api_key(), timeout=300.0)
    response = client.chat.completions.create(
        model=model_id(),
        messages=[
            {
                "role": "user",
                "content": "Is 9.11 greater than 9.8? Explain briefly.",
            },
        ],
        max_tokens=1024,
        temperature=0,
        extra_body={"reasoning": {"enabled": True}},
    )
    print(f"POST {base_url()}/chat/completions (reasoning.enabled)\n")
    print_json("response", response)


if __name__ == "__main__":
    main()
