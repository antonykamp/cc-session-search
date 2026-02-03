"""Tests for the token breakdown module."""

import pytest
from datetime import datetime, timezone

from cc_session_search.core.conversation_parser import ParsedMessage
from cc_session_search.token_breakdown import (
    CategoryTokens,
    TokenBreakdown,
    classify_message,
    compute_token_breakdown,
)


def _make_msg(
    role='assistant',
    content='hello',
    tool_uses=None,
    metadata=None,
    token_count=0,
    cost_usd=0.0,
    input_tokens=0,
    output_tokens=0,
    cache_creation_tokens=0,
    cache_read_tokens=0,
):
    return ParsedMessage(
        uuid='test-uuid',
        role=role,
        content=content,
        timestamp=datetime.now(tz=timezone.utc),
        tool_uses=tool_uses,
        metadata=metadata or {},
        token_count=token_count,
        cost_usd=cost_usd,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
    )


class TestClassifyMessage:
    def test_user_message(self):
        msg = _make_msg(role='user', content='hi')
        assert classify_message(msg) == 'user'

    def test_tool_result(self):
        msg = _make_msg(role='tool', content='result data')
        assert classify_message(msg) == 'tool_result'

    def test_thinking_message(self):
        msg = _make_msg(role='assistant', content='[Thinking: let me consider this]')
        assert classify_message(msg) == 'thinking'

    def test_text_message(self):
        msg = _make_msg(role='assistant', content='Here is my answer.')
        assert classify_message(msg) == 'text'

    def test_single_tool_call(self):
        msg = _make_msg(
            role='assistant',
            content='[Calling tool: Read]',
        )
        assert classify_message(msg) == 'Read'

    def test_multiple_tool_calls(self):
        msg = _make_msg(
            role='assistant',
            content='[Calling 2 tools: Read, Bash]',
        )
        assert classify_message(msg) == 'Read'

    def test_tool_call_via_tool_uses(self):
        msg = _make_msg(
            role='assistant',
            content='Let me read the file.',
            tool_uses={'tool_calls': [{'name': 'Read', 'id': 'abc', 'input': {}}]},
        )
        assert classify_message(msg) == 'Read'

    def test_summary_role(self):
        msg = _make_msg(role='summary', content='conversation summary')
        assert classify_message(msg) == 'summary'


class TestCategoryTokens:
    def test_total_tokens(self):
        cat = CategoryTokens(input_tokens=100, output_tokens=50, cache_creation_tokens=20, cache_read_tokens=30)
        assert cat.total_tokens == 200

    def test_iadd(self):
        a = CategoryTokens(input_tokens=10, output_tokens=5, cost_usd=0.01)
        b = CategoryTokens(input_tokens=20, output_tokens=10, cost_usd=0.02)
        a += b
        assert a.input_tokens == 30
        assert a.output_tokens == 15
        assert a.cost_usd == pytest.approx(0.03)


class TestComputeTokenBreakdown:
    def test_single_block(self):
        """A single assistant message counts characters from content."""
        msg = _make_msg(
            role='assistant',
            content='Hello world!',  # 12 chars
            metadata={'api_msg_id': 'msg-1'},
        )
        breakdown = compute_token_breakdown([msg])
        assert 'text' in breakdown.categories
        assert breakdown.categories['text'].input_tokens == pytest.approx(12.0)
        assert breakdown.total.total_tokens == pytest.approx(12.0)

    def test_grouped_messages(self):
        """Messages sharing api_msg_id each contribute their own content estimate."""
        thinking = _make_msg(
            role='assistant',
            content='[Thinking: abcd]',  # 16 chars -> 4
            metadata={'api_msg_id': 'msg-1'},
        )
        text = _make_msg(
            role='assistant',
            content='Here is my answer.',  # 18 chars -> 4.5
            metadata={'api_msg_id': 'msg-1'},
        )
        breakdown = compute_token_breakdown([thinking, text])

        assert breakdown.categories['thinking'].input_tokens == pytest.approx(len('[Thinking: abcd]'))
        assert breakdown.categories['text'].input_tokens == pytest.approx(len('Here is my answer.'))

    def test_duplicate_content_deduplication(self):
        """Duplicate content blocks within a group should be deduplicated."""
        msg1 = _make_msg(
            role='assistant',
            content='[Thinking: something]',  # 21 chars -> 5.25
            metadata={'api_msg_id': 'msg-1'},
        )
        msg2 = _make_msg(
            role='assistant',
            content='[Thinking: something]',  # duplicate
            metadata={'api_msg_id': 'msg-1'},
        )
        msg3 = _make_msg(
            role='assistant',
            content='Text response',  # 13 chars -> 3.25
            metadata={'api_msg_id': 'msg-1'},
        )
        breakdown = compute_token_breakdown([msg1, msg2, msg3])

        # Only 2 unique blocks counted
        assert breakdown.categories['thinking'].input_tokens == pytest.approx(21)
        assert breakdown.categories['text'].input_tokens == pytest.approx(13)
        assert breakdown.total.input_tokens == pytest.approx((21 + 13))

    def test_ungrouped_messages(self):
        """Messages without api_msg_id should still be classified."""
        user = _make_msg(role='user', content='hello', metadata={})
        tool = _make_msg(role='tool', content='result data', metadata={})

        breakdown = compute_token_breakdown([user, tool])
        assert 'user' in breakdown.categories
        # tool_result without matching tool call stays as 'tool_result'
        assert 'tool_result' in breakdown.categories
        assert breakdown.categories['user'].input_tokens == pytest.approx(len('hello'))
        assert breakdown.categories['tool_result'].input_tokens == pytest.approx(len('result data'))

    def test_tool_result_attributed_to_calling_tool(self):
        """Tool results should be attributed to the tool that called them."""
        tool_call = _make_msg(
            role='assistant',
            content='[Calling tool: Read]',
            metadata={'api_msg_id': 'msg-1'},
            tool_uses={'tool_calls': [{'name': 'Read', 'id': 'toolu_123', 'input': {}}]},
        )
        tool_result = _make_msg(
            role='tool',
            content='file contents here are long',
            metadata={},
            tool_uses={'tool_use_id': 'toolu_123'},
        )
        breakdown = compute_token_breakdown([tool_call, tool_result])
        # tool_result should be merged into 'Read', not 'tool_result'
        assert 'tool_result' not in breakdown.categories
        assert 'Read' in breakdown.categories
        expected = len('[Calling tool: Read]') + len('file contents here are long')
        assert breakdown.categories['Read'].input_tokens == pytest.approx(expected)

    def test_mixed_grouped_and_ungrouped(self):
        """Mix of messages with and without api_msg_id."""
        user = _make_msg(role='user', content='hello', metadata={})
        asst = _make_msg(
            role='assistant',
            content='response',
            metadata={'api_msg_id': 'msg-1'},
        )
        tool_result = _make_msg(role='tool', content='ok!!', metadata={})

        breakdown = compute_token_breakdown([user, asst, tool_result])
        assert 'user' in breakdown.categories
        assert 'text' in breakdown.categories
        assert 'tool_result' in breakdown.categories
        expected = len('hello') + len('response') + len('ok!!')
        assert breakdown.total.input_tokens == pytest.approx(expected)
        assert breakdown.categories['user'].estimated is True
        assert breakdown.categories['text'].estimated is True
        assert breakdown.categories['tool_result'].estimated is True

    def test_empty_messages(self):
        """Empty message list should produce empty breakdown."""
        breakdown = compute_token_breakdown([])
        assert len(breakdown.categories) == 0
        assert breakdown.total.total_tokens == 0

    def test_no_content(self):
        """Messages with empty content should not add tokens."""
        msg = _make_msg(role='assistant', content='', metadata={'api_msg_id': 'msg-1'})
        breakdown = compute_token_breakdown([msg])
        assert 'text' in breakdown.categories
        assert breakdown.categories['text'].total_tokens == 0
