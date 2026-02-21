"""Tests for the PricingCalculator."""

import pytest

from cc_session_explorer.core.models import TokenUsage
from cc_session_explorer.core.pricing import (
    PricingCalculator,
    CLAUDE_PRICING,
    CACHE_WRITE_5M_MULTIPLIER,
    CACHE_WRITE_1H_MULTIPLIER,
    CACHE_READ_MULTIPLIER,
)


@pytest.fixture
def calc():
    return PricingCalculator()


class TestPricingCalculator:
    def test_input_only(self, calc):
        usage = TokenUsage(input_tokens=1_000_000)
        cost = calc.calculate('claude-sonnet-4-5-20250929', usage)
        assert cost == pytest.approx(3.0)

    def test_output_only(self, calc):
        usage = TokenUsage(output_tokens=1_000_000)
        cost = calc.calculate('claude-sonnet-4-5-20250929', usage)
        assert cost == pytest.approx(15.0)

    def test_cache_read_uses_01x(self, calc):
        usage = TokenUsage(cache_read_tokens=1_000_000)
        cost = calc.calculate('claude-sonnet-4-5-20250929', usage)
        expected = 3.0 * CACHE_READ_MULTIPLIER
        assert cost == pytest.approx(expected)

    def test_5m_cache_write_uses_125x(self, calc):
        usage = TokenUsage(
            cache_creation_tokens=1_000_000,
            cache_5m_tokens=1_000_000,
        )
        cost = calc.calculate('claude-sonnet-4-5-20250929', usage)
        expected = 3.0 * CACHE_WRITE_5M_MULTIPLIER
        assert cost == pytest.approx(expected)

    def test_1h_cache_write_uses_2x(self, calc):
        usage = TokenUsage(
            cache_creation_tokens=1_000_000,
            cache_1h_tokens=1_000_000,
        )
        cost = calc.calculate('claude-sonnet-4-5-20250929', usage)
        expected = 3.0 * CACHE_WRITE_1H_MULTIPLIER
        assert cost == pytest.approx(expected)

    def test_fallback_to_5m_when_no_ttl_breakdown(self, calc):
        """When no cache_5m or cache_1h, falls back to 5-min multiplier."""
        usage = TokenUsage(cache_creation_tokens=1_000_000)
        cost = calc.calculate('claude-sonnet-4-5-20250929', usage)
        expected = 3.0 * CACHE_WRITE_5M_MULTIPLIER
        assert cost == pytest.approx(expected)

    def test_haiku_pricing(self, calc):
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
        cost = calc.calculate('claude-haiku-4-5-20251001', usage)
        expected = 1.0 + 5.0
        assert cost == pytest.approx(expected)

    def test_unknown_model_uses_default(self, calc):
        usage = TokenUsage(input_tokens=1_000_000)
        cost = calc.calculate('unknown-model', usage)
        # Should fall back to sonnet pricing
        assert cost == pytest.approx(3.0)

    def test_zero_usage(self, calc):
        usage = TokenUsage()
        cost = calc.calculate('claude-sonnet-4-5-20250929', usage)
        assert cost == 0.0

    def test_mixed_tokens(self, calc):
        usage = TokenUsage(
            input_tokens=10,
            output_tokens=8,
            cache_creation_tokens=5041,
            cache_read_tokens=15364,
            cache_1h_tokens=5041,
        )
        cost = calc.calculate('claude-sonnet-4-5-20250929', usage)
        expected = (
            (10 / 1e6) * 3.0
            + (8 / 1e6) * 15.0
            + (5041 / 1e6) * 3.0 * 2.0
            + (15364 / 1e6) * 3.0 * 0.1
        )
        assert cost == pytest.approx(expected, abs=1e-9)
