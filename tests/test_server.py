# SPDX-License-Identifier: MIT
"""Unit tests for FastMCP server tool execution."""

import pytest
from ai_crawler_radar.server import (
    bot_directory,
    audit_robots,
    skills_list,
    skill_read,
    mcp,
)


def test_bot_directory_tool():
    """Verify bot_directory MCP tool execution."""
    res = bot_directory(query="perplexity", category="all")
    assert "Cloudflare Radar Bot Directory" in res
    assert "Perplexity" in res or "perplexity" in res


def test_skills_tools():
    """Verify dynamic skill loading."""
    s_list = skills_list()
    assert "ai_crawler_radar_skill" in s_list

    s_content = skill_read("ai_crawler_radar_skill")
    assert "AI Crawler Radar Operational Playbook" in s_content
    assert "WAF Hard-Block" in s_content


def test_skill_read_missing():
    """Verify error message formatting on missing skill."""
    res = skill_read("non_existent_skill_xyz")
    assert "[INPUT_FIXABLE]" in res


@pytest.mark.asyncio
async def test_audit_robots_tool():
    """Verify audit_robots tool handles local domain or mock gracefully."""
    res = await audit_robots("example.com")
    assert "robots.txt 3-Tier AI Audit" in res
    assert "TRAINING" in res
    assert "SEARCH" in res


@pytest.mark.asyncio
async def test_generate_llms_txt_tool():
    """Verify generate_llms_txt tool output."""
    from ai_crawler_radar.server import generate_llms_txt
    res = await generate_llms_txt("example.com")
    assert "llms.txt" in res


@pytest.mark.asyncio
async def test_compare_readiness_tool():
    """Verify compare_readiness tool input validation and execution."""
    from ai_crawler_radar.server import compare_readiness
    res_empty = await compare_readiness([])
    assert "[INPUT_FIXABLE]" in res_empty
