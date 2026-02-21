"""
Pricing calculator for Claude API token usage.

Centralizes pricing constants and cost calculation logic.
"""

from cc_session_explorer.core.models import TokenUsage

# Claude pricing per million tokens
# Source: https://platform.claude.com/docs/en/about-claude/pricing
# Cache pricing multipliers:
#   5-min cache write: 1.25x base input
#   1-hour cache write: 2x base input
#   Cache read: 0.1x base input
CLAUDE_PRICING = {
    'claude-opus-4-5-20251101': {'input': 5.00, 'output': 25.00},
    'claude-sonnet-4-5-20250929': {'input': 3.00, 'output': 15.00},
    'claude-haiku-4-5-20251001': {'input': 1.00, 'output': 5.00},
    'claude-3-5-sonnet-20241022': {'input': 3.00, 'output': 15.00},
    'claude-3-5-sonnet-20240620': {'input': 3.00, 'output': 15.00},
    'claude-3-opus-20240229': {'input': 15.00, 'output': 75.00},
    'claude-3-sonnet-20240229': {'input': 3.00, 'output': 15.00},
    'claude-3-haiku-20240307': {'input': 0.25, 'output': 1.25},
}

CACHE_WRITE_5M_MULTIPLIER = 1.25
CACHE_WRITE_1H_MULTIPLIER = 2.0
CACHE_READ_MULTIPLIER = 0.1

DEFAULT_MODEL = 'claude-sonnet-4-5-20250929'


class PricingCalculator:
    """Calculates USD cost from token usage and model pricing."""

    def calculate(self, model: str, usage: TokenUsage) -> float:
        """Calculate the USD cost for the given model and token usage."""
        pricing = CLAUDE_PRICING.get(model, CLAUDE_PRICING[DEFAULT_MODEL])
        base_input_price = pricing['input']

        input_cost = (usage.input_tokens / 1_000_000) * base_input_price
        output_cost = (usage.output_tokens / 1_000_000) * pricing['output']

        # Cache write cost depends on TTL
        if usage.cache_5m_tokens or usage.cache_1h_tokens:
            cache_creation_cost = (
                (usage.cache_5m_tokens / 1_000_000) * base_input_price * CACHE_WRITE_5M_MULTIPLIER
                + (usage.cache_1h_tokens / 1_000_000) * base_input_price * CACHE_WRITE_1H_MULTIPLIER
            )
        else:
            # Fallback for older files without TTL breakdown: assume 5-min cache
            cache_creation_cost = (usage.cache_creation_tokens / 1_000_000) * base_input_price * CACHE_WRITE_5M_MULTIPLIER

        cache_read_cost = (usage.cache_read_tokens / 1_000_000) * base_input_price * CACHE_READ_MULTIPLIER

        return input_cost + output_cost + cache_creation_cost + cache_read_cost
