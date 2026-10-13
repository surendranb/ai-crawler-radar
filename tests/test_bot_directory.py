# SPDX-License-Identifier: MIT
"""Unit tests for bot catalog lookup and category filtering."""

import pytest
from ai_crawler_radar.catalog import (
    load_bot_directory,
    search_bots,
    get_categories,
    get_bot_by_slug,
    find_matching_bots_for_ua,
)


def test_bot_directory_loading():
    """Verify that the embedded Cloudflare Radar bot directory contains exactly 758 verified bots."""
    bots = load_bot_directory()
    assert len(bots) == 758, f"Expected 758 verified bots, found {len(bots)}"
    sample = bots[0]
    assert "slug" in sample
    assert "name" in sample
    assert "category" in sample


def test_bot_categories():
    """Verify all 17 distinct categories are present and populated."""
    categories = get_categories()
    assert len(categories) == 17
    assert "AI_CRAWLER" in categories
    assert "AI_SEARCH" in categories
    assert "AI_ASSISTANT" in categories
    assert "SEARCH_ENGINE_CRAWLER" in categories


def test_search_bots_by_query():
    """Test searching bots by brand/operator query."""
    openai_bots = search_bots(query="openai")
    assert len(openai_bots) >= 4
    names = [b["name"] for b in openai_bots]
    assert "GPTBot" in names
    assert "ChatGPT-User" in names
    assert "OAI-SearchBot" in names

    anthropic_bots = search_bots(query="anthropic")
    assert len(anthropic_bots) >= 2
    a_names = [b["name"] for b in anthropic_bots]
    assert any("Claude" in n for n in a_names)


def test_search_bots_by_category():
    """Test category filtering."""
    ai_crawlers = search_bots(category="AI_CRAWLER")
    assert len(ai_crawlers) > 20
    assert all(b.get("category") == "AI_CRAWLER" for b in ai_crawlers)

    ai_search = search_bots(category="AI_SEARCH")
    assert len(ai_search) > 5
    assert all(b.get("category") == "AI_SEARCH" for b in ai_search)


def test_get_bot_by_slug():
    """Test lookup by exact slug."""
    gptbot = get_bot_by_slug("gptbot")
    assert gptbot is not None
    assert gptbot["name"] == "GPTBot"
    assert gptbot["operator"] == "OpenAI"

    assert get_bot_by_slug("non-existent-bot-slug-xyz") is None


def test_find_matching_bots_for_ua():
    """Test matching incoming user agents against patterns."""
    ua = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot"
    matches = find_matching_bots_for_ua(ua)
    assert len(matches) > 0
    assert any(b["slug"] == "gptbot" for b in matches)
