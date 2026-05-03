from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv
from tools import TOOLS, run_tool

load_dotenv()


client = Anthropic()

MODEL = "claude-sonnet-4-5"  # swap to sonnet-4-6 once you verify the string on your account
MAX_TOKENS = 4096
MAX_ITERATIONS = 25



def main() -> None:
    prompt = Path("PROMPT.md").read_text()

    messages = [{"role": "user", "content": prompt}]

    for iteration in range(1, MAX_ITERATIONS + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "text":
                print(block.text)
            elif block.type == "tool_use":
                print(f"\n[tool_use] {block.name}({block.input})")

        if response.stop_reason != "tool_use":
            print(
                f"\n--- stop: {response.stop_reason} | iter {iteration}/{MAX_ITERATIONS} | "
                f"in: {response.usage.input_tokens} tok, "
                f"out: {response.usage.output_tokens} tok ---"
            )
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = run_tool(block.name, block.input)
                print(f"[tool_result]\n{result}")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

        messages.append({"role": "user", "content": tool_results})
    else:
        print(
            f"\n--- halted: reached MAX_ITERATIONS={MAX_ITERATIONS} "
            f"without end_turn. Raise the cap or inspect the prompt. ---"
        )


if __name__ == "__main__":
    main()
