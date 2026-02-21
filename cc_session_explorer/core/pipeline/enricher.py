"""
Token usage enrichment stage.

Handles API message ID deduplication and cost calculation using
the PricingCalculator.
"""

from cc_session_explorer.core.models import TokenUsage
from cc_session_explorer.core.pricing import PricingCalculator
from cc_session_explorer.core.pipeline.normalizer import NormalizedMessage


def enrich_with_usage(messages: list[NormalizedMessage], pricing: PricingCalculator) -> list[NormalizedMessage]:
    """Enrich messages with token counts and USD costs.

    Handles deduplication: when multiple JSONL lines share the same API
    message ID, usage is only counted for the first occurrence.
    """
    seen_api_msg_ids: set[str] = set()

    for msg in messages:
        usage_data = msg.usage_data
        input_tokens = usage_data.get('input_tokens', 0)
        output_tokens = usage_data.get('output_tokens', 0)
        cache_creation_tokens = usage_data.get('cache_creation_input_tokens', 0)
        cache_read_tokens = usage_data.get('cache_read_input_tokens', 0)

        cache_creation_detail = usage_data.get('cache_creation', {})
        cache_5m_tokens = cache_creation_detail.get('ephemeral_5m_input_tokens', 0)
        cache_1h_tokens = cache_creation_detail.get('ephemeral_1h_input_tokens', 0)

        # Check for duplicate API message IDs
        api_msg_id = msg.api_msg_id
        usage_already_counted = False
        if api_msg_id:
            if api_msg_id in seen_api_msg_ids:
                usage_already_counted = True
            else:
                seen_api_msg_ids.add(api_msg_id)

        has_usage = input_tokens > 0 or output_tokens > 0 or cache_creation_tokens > 0 or cache_read_tokens > 0

        if msg.role == 'assistant' and has_usage and not usage_already_counted:
            usage = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_tokens=cache_creation_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_5m_tokens=cache_5m_tokens,
                cache_1h_tokens=cache_1h_tokens,
            )
            usage.cost_usd = pricing.calculate(msg.model, usage)

            # Store enriched usage on the message's raw_metadata for the assembler
            msg.raw_metadata['_enriched_usage'] = usage
        else:
            msg.raw_metadata['_enriched_usage'] = TokenUsage()

    return messages
