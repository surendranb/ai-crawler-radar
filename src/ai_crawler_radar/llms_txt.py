# SPDX-License-Identifier: MIT
"""llms.txt and llms-full.txt CommonMark V2 validator and generator."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

import httpx


class LLMsTxtValidator:
    """Validates markdown against the llms.txt CommonMark V2 specification."""

    @staticmethod
    def validate(content: str, base_url: str = "") -> Dict[str, Any]:
        lines = [line.strip() for line in content.splitlines()]
        non_empty = [l for l in lines if l]

        errors: List[str] = []
        warnings: List[str] = []
        info: List[str] = []
        links: List[Dict[str, str]] = []

        if not content.strip():
            return {
                "valid": False,
                "score": 0,
                "errors": ["File is empty."],
                "warnings": [],
                "info": [],
                "links": [],
                "sections": [],
            }

        # 1. Check for H1 Title
        h1_titles = [l for l in lines if l.startswith("# ") and not l.startswith("## ")]
        if not h1_titles:
            errors.append("Missing required H1 title ('# Project Name').")
            title = None
        elif len(h1_titles) > 1:
            warnings.append(f"Multiple H1 titles detected ({len(h1_titles)}). Specification recommends a single H1.")
            title = h1_titles[0][2:].strip()
        else:
            title = h1_titles[0][2:].strip()

        # 2. Check for Blockquote Summary
        blockquotes = [l for l in lines if l.startswith("> ")]
        if not blockquotes:
            warnings.append("Missing recommended blockquote summary ('> Concise project overview') right below H1.")
            summary = None
        else:
            summary = " ".join([b[2:].strip() for b in blockquotes])

        # 3. Check for H2 Sections
        h2_sections = [l[3:].strip() for l in lines if l.startswith("## ")]
        if not h2_sections:
            warnings.append("No H2 sections found ('## Documentation', '## Guides', etc.). Structured sections improve LLM indexing.")

        # 4. Check for List Item Links: - [Title](url): Description
        link_pattern = re.compile(r"^[-*]\s*\[([^\]]+)\]\(([^)]+)\)(?::\s*(.*))?$")
        for line_num, line in enumerate(lines, start=1):
            if line.startswith(("- ", "* ")):
                match = link_pattern.match(line)
                if match:
                    l_title, l_url, l_desc = match.groups()
                    resolved_url = l_url.strip()
                    if base_url and not resolved_url.startswith(("http://", "https://", "/")):
                        resolved_url = urljoin(base_url, resolved_url)

                    # Validate URL
                    parsed = urlparse(resolved_url)
                    if not parsed.scheme and not resolved_url.startswith("/"):
                        warnings.append(f"Line {line_num}: Relative or malformed URL '{l_url}'. Prefer absolute URLs for AI crawlers.")

                    links.append({
                        "title": l_title.strip(),
                        "url": resolved_url,
                        "description": (l_desc or "").strip(),
                        "line": line_num,
                    })

        if not links:
            warnings.append("No structured link entries found. llms.txt should list key documentation links formatted as '- [Title](url): Description'.")

        # Compute readiness score (0 to 100)
        score = 100
        score -= (len(errors) * 35)
        score -= (len(warnings) * 10)
        score = max(0, min(100, score))

        valid = len(errors) == 0 and score >= 60

        return {
            "valid": valid,
            "score": score,
            "title": title,
            "summary": summary,
            "sections": h2_sections,
            "links_count": len(links),
            "links": links,
            "errors": errors,
            "warnings": warnings,
            "info": info,
        }


async def fetch_and_validate_llms_txt(domain_or_url: str) -> Dict[str, Any]:
    """Fetches and validates /llms.txt and checks for /llms-full.txt on a target domain."""
    norm = domain_or_url.strip()
    if not norm.startswith(("http://", "https://")):
        norm = "https://" + norm

    parsed = urlparse(norm)
    base_origin = f"{parsed.scheme}://{parsed.netloc}"
    llms_url = f"{base_origin}/llms.txt"
    llms_full_url = f"{base_origin}/llms-full.txt"

    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
        # Probe /llms.txt
        try:
            resp = await client.get(llms_url)
            status_code = resp.status_code
            content_type = resp.headers.get("content-type", "")
            raw_text = resp.text if status_code == 200 else ""
        except Exception as e:
            return {
                "exists": False,
                "url": llms_url,
                "status_code": 0,
                "error": str(e),
                "validation": None,
                "has_llms_full": False,
            }

        if status_code != 200:
            return {
                "exists": False,
                "url": llms_url,
                "status_code": status_code,
                "error": f"HTTP {status_code} - /llms.txt not found on {parsed.netloc}",
                "validation": None,
                "has_llms_full": False,
            }

        # Validate content
        val_res = LLMsTxtValidator.validate(raw_text, base_url=base_origin)

        # Check /llms-full.txt
        has_full = False
        full_size = 0
        try:
            full_resp = await client.get(llms_full_url)
            if full_resp.status_code == 200:
                has_full = True
                full_size = len(full_resp.content)
        except Exception:
            pass

        return {
            "exists": True,
            "url": llms_url,
            "status_code": 200,
            "content_type": content_type,
            "raw_size_bytes": len(resp.content),
            "validation": val_res,
            "has_llms_full": has_full,
            "llms_full_url": llms_full_url if has_full else None,
            "llms_full_size_bytes": full_size,
        }


def generate_llms_txt(
    title: str,
    summary: str,
    sections: Optional[List[Dict[str, Any]]] = None,
    domain: str = "",
) -> str:
    """Generates standard CommonMark V2 compliant /llms.txt content."""
    clean_title = title.strip() or (domain if domain else "AI Documentation")
    clean_summary = summary.strip() or f"Curated AI documentation and API reference for {clean_title}."

    parts = [
        f"# {clean_title}",
        "",
        f"> {clean_summary}",
        "",
        "This file provides structured documentation indices optimized for AI search engines,",
        "autonomous agents, and frontier language models.",
        "",
    ]

    if not sections:
        # Default starter sections
        base = domain.rstrip("/") if domain else "https://example.com"
        if not base.startswith("http"):
            base = "https://" + base

        sections = [
            {
                "name": "Documentation",
                "items": [
                    {"title": "Overview", "url": f"{base}/docs/overview", "desc": "High-level architecture and platform concepts"},
                    {"title": "Quickstart Guide", "url": f"{base}/docs/quickstart", "desc": "Step-by-step onboarding for developers"},
                    {"title": "API Reference", "url": f"{base}/docs/api", "desc": "Complete endpoint schemas and parameters"},
                ],
            },
            {
                "name": "Optional",
                "items": [
                    {"title": "Full Documentation Concatenation", "url": f"{base}/llms-full.txt", "desc": "Single-file complete documentation text for large-context models"},
                ],
            },
        ]

    for sec in sections:
        sec_name = sec.get("name", "Resources")
        parts.append(f"## {sec_name}")
        parts.append("")
        for item in sec.get("items", []):
            i_title = item.get("title", "Link")
            i_url = item.get("url", "#")
            i_desc = item.get("desc", "")
            if i_desc:
                parts.append(f"- [{i_title}]({i_url}): {i_desc}")
            else:
                parts.append(f"- [{i_title}]({i_url})")
        parts.append("")

    return "\n".join(parts).strip() + "\n"
