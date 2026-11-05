"""Model factory from env, plus USD cost from LangChain usage metadata."""

import os
from typing import NamedTuple

from botocore.config import Config
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

DEFAULT_MODEL = "bedrock_converse:global.anthropic.claude-sonnet-5-5"


class Price(NamedTuple):
    """USD per 1M tokens."""

    input: float
    output: float
    cache_read: float
    cache_write: float  # 5-minute TTL; 1-hour TTL is 2x input


# Anthropic list prices; Bedrock global cross-region profiles bill at list price (check
# https://aws.amazon.com/bedrock/pricing/). Cache rates are 0.1x read, 1.25x write of input.
PRICES_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
PRICES_AS_OF = "2026-10-06"
PRICES = {
    "claude-sonnet-5-5": Price(input=2.00, output=10.00, cache_read=0.20, cache_write=2.50),
    "claude-haiku-5-5": Price(input=0.10, output=0.50, cache_read=0.01, cache_write=0.125),  # prompts <=100K tokens
}


def get_model():
    """Build the chat model named by LLM_MODEL ("<provider>:<model id>")."""
    load_dotenv()
    spec = os.getenv("LLM_MODEL", DEFAULT_MODEL)
    kwargs = {}
    if spec.startswith("bedrock"):
        kwargs["region_name"] = os.getenv("AWS_REGION", "ap-southeast-1")
        # boto3's 60s read timeout is too short for a whole-document call with (default
        # adaptive) thinking. No retries.
        kwargs["config"] = Config(read_timeout=300, retries={"total_max_attempts": 1})
    return init_chat_model(spec, max_tokens=16000, **kwargs)


def cost_usd(usage_by_model: dict) -> float | None:
    """Sum cost over {model_name: usage_metadata}; None if any model has no price."""
    total = 0.0
    for model, u in usage_by_model.items():
        price = next((p for k, p in PRICES.items() if k in model), None)
        if price is None:
            return None
        details = u.get("input_token_details") or {}
        read = details.get("cache_read", 0)
        # Cache writes: LangChain moves them from cache_creation into per-TTL keys when the
        # provider reports a TTL breakdown (langchain-aws does for Bedrock), so sum all three.
        write = details.get("cache_creation", 0) + details.get("ephemeral_5m_input_tokens", 0)
        write_1h = details.get("ephemeral_1h_input_tokens", 0)
        uncached = u["input_tokens"] - read - write - write_1h  # input_tokens includes cache
        total += (
            uncached * price.input
            + u["output_tokens"] * price.output
            + read * price.cache_read
            + write * price.cache_write
            + write_1h * price.input * 2  # 1-hour TTL writes bill at 2x input
        ) / 1_000_000
    return total
