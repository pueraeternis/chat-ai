"""Hosted web_search tool (server-side orchestration, url_citation annotations)."""

from openai import OpenAI
from settings import api_key, base_url, model_id, print_json

WEB_SEARCH_TOOL = {
    "type": "web_search",
    "search_context_size": "low",
    "user_location": {
        "type": "approximate",
        "approximate": {
            "country": "US",
            "city": "New York",
            "region": "New York",
            "timezone": "America/New_York",
        },
    },
}


def main() -> None:
    client = OpenAI(base_url=base_url(), api_key=api_key(), timeout=600.0)
    response = client.chat.completions.create(
        model=model_id(),
        messages=[
            {
                "role": "user",
                "content": ("Use web search: what is the current stable Python release version? Brief answer with sources."),
            },
        ],
        max_tokens=1024,
        extra_body={"tools": [WEB_SEARCH_TOOL]},
    )
    print(f"POST {base_url()}/chat/completions (web_search)\n")
    print_json("response", response)


if __name__ == "__main__":
    main()
