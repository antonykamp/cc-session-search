"""Tests for the enricher pipeline stage."""

import pytest

from cc_session_explorer.core.models import TokenUsage
from cc_session_explorer.core.pricing import PricingCalculator
from cc_session_explorer.core.pipeline.normalizer import NormalizedMessage
from cc_session_explorer.core.pipeline.enricher import enrich_with_usage


def _make_normalized(
    role='assistant',
    api_msg_id=None,
    model='claude-sonnet-4-5-20250929',
    usage_data=None,
):
    return NormalizedMessage(
        uuid='test',
        role=role,
        blocks=[],
        content='hello',
        timestamp=None,
        api_msg_id=api_msg_id,
        model=model,
        usage_data=usage_data or {},
    )


@pytest.fixture
def pricing():
    return PricingCalculator()


class TestEnrichWithUsage:
    def test_assistant_gets_usage(self, pricing):
        msg = _make_normalized(
            role='assistant',
            api_msg_id='msg_1',
            usage_data={
                'input_tokens': 100,
                'output_tokens': 50,
                'cache_creation_input_tokens': 0,
                'cache_read_input_tokens': 0,
            },
        )
        enriched = enrich_with_usage([msg], pricing)
        usage = enriched[0].raw_metadata['_enriched_usage']
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total == 150
        assert usage.cost_usd > 0

    def test_user_gets_zero_usage(self, pricing):
        msg = _make_normalized(
            role='user',
            usage_data={'input_tokens': 100, 'output_tokens': 50},
        )
        enriched = enrich_with_usage([msg], pricing)
        usage = enriched[0].raw_metadata['_enriched_usage']
        assert usage.total == 0
        assert usage.cost_usd == 0.0

    def test_deduplicates_by_api_msg_id(self, pricing):
        msg1 = _make_normalized(
            role='assistant',
            api_msg_id='msg_1',
            usage_data={'input_tokens': 100, 'output_tokens': 50},
        )
        msg2 = _make_normalized(
            role='assistant',
            api_msg_id='msg_1',
            usage_data={'input_tokens': 100, 'output_tokens': 50},
        )
        enriched = enrich_with_usage([msg1, msg2], pricing)

        usage1 = enriched[0].raw_metadata['_enriched_usage']
        usage2 = enriched[1].raw_metadata['_enriched_usage']

        assert usage1.total == 150
        assert usage1.cost_usd > 0
        assert usage2.total == 0
        assert usage2.cost_usd == 0.0

    def test_different_api_msg_ids_counted_separately(self, pricing):
        msg1 = _make_normalized(
            role='assistant',
            api_msg_id='msg_1',
            usage_data={'input_tokens': 100, 'output_tokens': 50},
        )
        msg2 = _make_normalized(
            role='assistant',
            api_msg_id='msg_2',
            usage_data={'input_tokens': 200, 'output_tokens': 80},
        )
        enriched = enrich_with_usage([msg1, msg2], pricing)

        usage1 = enriched[0].raw_metadata['_enriched_usage']
        usage2 = enriched[1].raw_metadata['_enriched_usage']

        assert usage1.total == 150
        assert usage2.total == 280

    def test_cache_tokens_included(self, pricing):
        msg = _make_normalized(
            role='assistant',
            api_msg_id='msg_1',
            usage_data={
                'input_tokens': 0,
                'output_tokens': 0,
                'cache_creation_input_tokens': 1000,
                'cache_read_input_tokens': 5000,
                'cache_creation': {
                    'ephemeral_5m_input_tokens': 1000,
                    'ephemeral_1h_input_tokens': 0,
                },
            },
        )
        enriched = enrich_with_usage([msg], pricing)
        usage = enriched[0].raw_metadata['_enriched_usage']
        assert usage.cache_creation_tokens == 1000
        assert usage.cache_read_tokens == 5000
        assert usage.total == 6000

    def test_no_usage_data(self, pricing):
        msg = _make_normalized(role='assistant', api_msg_id='msg_1')
        enriched = enrich_with_usage([msg], pricing)
        usage = enriched[0].raw_metadata['_enriched_usage']
        assert usage.total == 0
        assert usage.cost_usd == 0.0
