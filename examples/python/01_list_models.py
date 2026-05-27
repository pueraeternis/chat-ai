"""List models exposed by chat-proxy (passthrough from vLLM)."""

from openai import OpenAI
from settings import api_key, base_url, print_json


def main() -> None:
    client = OpenAI(base_url=base_url(), api_key=api_key())
    models = client.models.list()
    print(f"POST {base_url()}/models\n")
    print_json("response", models)


if __name__ == "__main__":
    main()
