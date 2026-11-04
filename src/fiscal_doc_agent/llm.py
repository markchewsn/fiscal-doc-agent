"""Model factory from env, plus USD cost from LangChain usage metadata."""

import os

from botocore.config import Config
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

DEFAULT_MODEL = "bedrock_converse:global.anthropic.claude-sonnet-5-5"

# USD per 1M tokens: (input, output, cache_read, cache_write_5m).
# Source: https://platform.claude.com/docs/en/about-claude/pricing (Anthropic list price,
# as of 2026-10-06). Bedrock global cross-region profiles bill at list price; check
# https://aws.amazon.com/bedrock/pricing/ before relying on these. Cache rates are
# 0.1x (read) and 1.25x (5-minute write) of input.
PRICES_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
PRICES_AS_OF = "2026-10-06"
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),  # prompts <=100K tokens
}


def get_model():
    """Build the chat model named by LLM_MODEL ("<provider>:<model id>")."""
    load_dotenv()
    spec = os.getenv("LLM_MODEL", DEFAULT_MODEL)
    kwargs = {}
    if spec.startswith("bedrock"):
        kwargs["region_name"] = os.getenv("AWS_REGION", "ap-southeast-1")
        # boto3's 60s read timeout is too short for a whole-document call with thinking.
        kwargs["config"] = Config(read_timeout=300, retries={"max_attempts": 2, "mode": "adaptive"})
    return init_chat_model(spec, max_tokens=16000, **kwargs)


def cost_usd(usage_by_model: dict) -> float | None:
    """Sum cost over {model_name: usage_metadata}; None if any model has no price."""
    total = 0.0
    for model, u in usage_by_model.items():
        price = next((p for k, p in PRICES.items() if k in model), None)
        if price is None:
            return None
        details = u.get("input_token_details") or {}
        read, write = details.get("cache_read", 0), details.get("cache_creation", 0)
        uncached = u["input_tokens"] - read - write  # LangChain input_tokens includes cache
        tokens = (uncached, u["output_tokens"], read, write)
        total += sum(t * p for t, p in zip(tokens, price)) / 1_000_000
    return total
