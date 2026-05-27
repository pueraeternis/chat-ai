"""Client function calling: tool_calls, then second turn with role=tool."""

from __future__ import annotations

import json

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionFunctionToolParam,
    ChatCompletionMessageParam,
    ChatCompletionToolMessageParam,
)
from settings import api_key, base_url, model_id, print_json

TOOLS: list[ChatCompletionFunctionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name",
                    },
                },
                "required": ["city"],
            },
        },
    },
]


def fake_weather(city: str) -> dict[str, str | int]:
    """Stub: replace with your real API in production code."""
    return {"city": city, "temperature_c": 18, "condition": "sunny"}


def main() -> None:
    client = OpenAI(base_url=base_url(), api_key=api_key(), timeout=300.0)
    messages: list[ChatCompletionMessageParam] = [
        {
            "role": "user",
            "content": "What is the weather in San Francisco? Use the tool.",
        },
    ]

    first = client.chat.completions.create(
        model=model_id(),
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        max_tokens=512,
    )
    print(f"POST {base_url()}/chat/completions (turn 1)\n")
    print_json("response (turn 1)", first)

    assistant_msg = first.choices[0].message
    if not assistant_msg.tool_calls:
        return

    function_tool_calls = [tc for tc in assistant_msg.tool_calls if tc.type == "function"]
    messages.append(
        ChatCompletionAssistantMessageParam(
            role="assistant",
            content=assistant_msg.content,
            tool_calls=[
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in function_tool_calls
            ],
        ),
    )

    for tc in function_tool_calls:
        args = json.loads(tc.function.arguments)
        result = fake_weather(args["city"])
        messages.append(
            ChatCompletionToolMessageParam(
                role="tool",
                tool_call_id=tc.id,
                content=json.dumps(result),
            ),
        )

    second = client.chat.completions.create(
        model=model_id(),
        messages=messages,
        tools=TOOLS,
        max_tokens=512,
    )
    print(f"POST {base_url()}/chat/completions (turn 2)\n")
    print_json("response (turn 2)", second)


if __name__ == "__main__":
    main()
