from functools import cache

from anthropic import Anthropic

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 500


@cache
def _get_client() -> Anthropic:
    return Anthropic()


def run(content: str, count: int = 1) -> str:
    resp = _get_client().messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Summarize the following into exactly {count} haiku(s). "
                    f"Each haiku must follow 5-7-5 syllables. "
                    f"Return only the haikus, separated by blank lines, no commentary.\n\n"
                    f"{content}"
                ),
            }
        ],
    )
    return "".join(b.text for b in resp.content if b.type == "text")
