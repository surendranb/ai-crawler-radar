# SPDX-License-Identifier: MIT
"""Unit tests for RFC 9309 3-tier robots.txt rules parser."""

import pytest
from ai_crawler_radar.robots_parser import parse_robots_txt, RobotsTxt


def test_empty_robots_allows_all():
    """Empty robots.txt must allow all crawlers across all tiers."""
    parser = parse_robots_txt("")
    audit = parser.audit_all_tiers("/")
    assert audit["tier_summary"]["training"]["status"] == "ALL_ALLOWED"
    assert audit["tier_summary"]["search"]["status"] == "ALL_ALLOWED"
    assert audit["tier_summary"]["live_fetch"]["status"] == "ALL_ALLOWED"


def test_tier_differentiation():
    """Verify standard modern robots.txt where training is blocked but search is allowed."""
    robots_content = """
User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: Meta-ExternalAgent
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: cohere-ai
Disallow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: *
Disallow: /admin/
Sitemap: https://example.com/sitemap.xml
"""
    parser = parse_robots_txt(robots_content)
    audit = parser.audit_all_tiers("/")

    # All 7 training bots should be blocked
    assert audit["tier_summary"]["training"]["status"] == "ALL_BLOCKED"
    assert audit["tier_summary"]["training"]["disallowed_count"] == 7

    # Search bots should be allowed
    assert audit["tier_summary"]["search"]["status"] == "ALL_ALLOWED"

    # Live user bots fall back to * which allows /
    assert audit["tier_summary"]["live_fetch"]["status"] == "ALL_ALLOWED"

    # Strategic recommendations should identify optimal AI search posture
    recs = audit["strategic_recommendations"]
    assert any("Optimal AI Search Posture" in r for r in recs)

    # Sitemaps detected
    assert "https://example.com/sitemap.xml" in audit["sitemaps"]


def test_rfc9309_longest_match_rule():
    """RFC 9309 Section 2.2.2: Longest matching directive wins."""
    robots_content = """
User-agent: OAI-SearchBot
Disallow: /docs/
Allow: /docs/api/
Disallow: /docs/api/secret
"""
    parser = parse_robots_txt(robots_content)

    # /docs/overview -> matches Disallow: /docs/ (len 6)
    assert parser.evaluate_bot("OAI-SearchBot", "/docs/overview")["allowed"] is False

    # /docs/api/quickstart -> matches Allow: /docs/api/ (len 10) > Disallow: /docs/ (len 6)
    assert parser.evaluate_bot("OAI-SearchBot", "/docs/api/quickstart")["allowed"] is True

    # /docs/api/secret/key -> matches Disallow: /docs/api/secret (len 16) > Allow: /docs/api/ (len 10)
    assert parser.evaluate_bot("OAI-SearchBot", "/docs/api/secret/key")["allowed"] is False


def test_equal_length_allow_wins():
    """RFC 9309 Section 2.2.2: On equal pattern length, Allow takes precedence over Disallow."""
    robots_content = """
User-agent: *
Disallow: /page
Allow: /page
"""
    parser = parse_robots_txt(robots_content)
    # Both patterns have len 5 -> Allow must win
    assert parser.evaluate_bot("GPTBot", "/page")["allowed"] is True


def test_wildcards_and_end_anchors():
    """Test wildcard * and end anchor $ patterns."""
    robots_content = """
User-agent: *
Disallow: /*.pdf$
Disallow: /private/*/secret
"""
    parser = parse_robots_txt(robots_content)

    assert parser.evaluate_bot("GPTBot", "/document.pdf")["allowed"] is False
    assert parser.evaluate_bot("GPTBot", "/document.pdf?version=1")["allowed"] is True  # $ not matched
    assert parser.evaluate_bot("GPTBot", "/private/folder/secret")["allowed"] is False
    assert parser.evaluate_bot("GPTBot", "/public/folder/secret")["allowed"] is True


def test_empty_disallow_clears_rules():
    """Empty Disallow: clears previous disallow directives."""
    robots_content = """
User-agent: *
Disallow: /
Disallow:
"""
    parser = parse_robots_txt(robots_content)
    assert parser.evaluate_bot("GPTBot", "/anything")["allowed"] is True
