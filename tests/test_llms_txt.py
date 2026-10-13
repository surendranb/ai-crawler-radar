# SPDX-License-Identifier: MIT
"""Unit tests for llms.txt CommonMark V2 validation and generation."""

import pytest
from ai_crawler_radar.llms_txt import LLMsTxtValidator, generate_llms_txt


def test_valid_llms_txt_validation():
    sample_content = """# FastMCP

> A high-performance Python framework for building Model Context Protocol servers.

This specification describes FastMCP architecture and tool creation protocols.

## Core Documentation

- [Quickstart Guide](https://fastmcp.org/quickstart): 5-minute setup guide
- [Tool Annotations](https://fastmcp.org/tools): Schema and parameter documentation
- [Server Transports](https://fastmcp.org/transports): stdio and SSE transport protocols

## Optional

- [Full Docs Concatenation](https://fastmcp.org/llms-full.txt): Complete concatenated documentation
"""
    res = LLMsTxtValidator.validate(sample_content, base_url="https://fastmcp.org")
    assert res["valid"] is True
    assert res["score"] == 100
    assert res["title"] == "FastMCP"
    assert "framework" in res["summary"].lower()
    assert len(res["sections"]) == 2
    assert res["links_count"] == 4
    assert len(res["errors"]) == 0


def test_invalid_llms_txt_missing_h1():
    bad_content = """## Section Only
- [Link](https://example.com): Description
"""
    res = LLMsTxtValidator.validate(bad_content)
    assert res["valid"] is False
    assert any("Missing required H1 title" in e for e in res["errors"])


def test_generator_produces_compliant_file():
    domain = "https://agentic-tools.com"
    generated = generate_llms_txt(
        title="Agentic Tools",
        summary="A suite of high-utility tools for AI coding assistants.",
        domain=domain,
    )

    # Validate generated text
    res = LLMsTxtValidator.validate(generated, base_url=domain)
    assert res["valid"] is True
    assert res["score"] == 100
    assert res["title"] == "Agentic Tools"
    assert res["links_count"] >= 3
