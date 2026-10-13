# SPDX-License-Identifier: MIT
"""Standard FastMCP stdio server for ai-crawler-radar."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
try:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer(
        "ai-crawler-radar",
        title="AI Crawler Radar",
        instructions="Autonomous AI Search, Training & Agent Crawler Diagnostic Engine. Use to probe crawler accessibility, audit robots.txt across 3 bot tiers, diagnose WAF/Turnstile blocks, measure token bloat, and generate /llms.txt specifications.",
        website_url="https://github.com/surendranb/ai-crawler-radar",
    )
except ImportError:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP(
        "ai-crawler-radar",
        instructions="Autonomous AI Search, Training & Agent Crawler Diagnostic Engine. Use to probe crawler accessibility, audit robots.txt across 3 bot tiers, diagnose WAF/Turnstile blocks, measure token bloat, and generate /llms.txt specifications.",
    )

from ai_crawler_radar.catalog import search_bots, get_categories, load_bot_directory
from ai_crawler_radar.classifier import classify_response, calculate_token_bloat
from ai_crawler_radar.llms_txt import generate_llms_txt as build_llms_txt, fetch_and_validate_llms_txt
from ai_crawler_radar.prober import probe_url as run_probe_url
from ai_crawler_radar.robots_parser import parse_robots_txt
from ai_crawler_radar.telemetry import track_tool_call, classify_exception

# Skills registry
_SKILLS_BASE_URL = "https://raw.githubusercontent.com/surendranb/ai-crawler-radar/main/skills/"
_SKILLS_REGISTRY = {
    "ai_crawler_radar_skill": "Operational playbook for auditing and optimizing websites for AI search engines, training scrapers, and autonomous agents.",
}
_LOCAL_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"
if not _LOCAL_SKILLS_DIR.is_dir() and (Path.cwd() / "skills").is_dir():
    _LOCAL_SKILLS_DIR = Path.cwd() / "skills"


def _load_skill(name: str) -> tuple[Optional[str], bool]:
    clean = name.replace(".md", "").strip()
    local_path = _LOCAL_SKILLS_DIR / f"{clean}.md"
    if local_path.is_file():
        try:
            return local_path.read_text(encoding="utf-8"), True
        except Exception:
            pass

    url = f"{_SKILLS_BASE_URL}{clean}.md"
    try:
        req = httpx.get(url, timeout=4.0)
        if req.status_code == 200:
            return req.text, True
    except Exception:
        pass
    return None, False


@mcp.tool()
async def probe_url(url: str, tier: str = "all", check_markdown_twin: bool = True) -> str:
    """Probe a URL with authentic AI bot headers to diagnose WAF hard-blocks, Turnstile challenges, and token bloat.

    Args:
        url: Target web page URL to inspect (e.g. 'https://docs.anthropic.com' or 'example.com').
        tier: Bot tier to probe: 'all', 'training' (GPTBot, ClaudeBot), 'search' (OAI-SearchBot, PerplexityBot), or 'live_fetch' (ChatGPT-User, Claude-User).
        check_markdown_twin: If true, tests content negotiation (Accept: text/markdown), direct .md twin, and /llms.txt.
    """
    t0 = time.time()
    try:
        target = url.strip()
        if not target.startswith(("http://", "https://")):
            target = "https://" + target

        data = await run_probe_url(target, tier=tier, check_twin=check_markdown_twin)

        lines = [
            f"# AI Crawler Probe Report: {data['url']}",
            f"**Probed At**: {data['probed_at']} | **Total Bots Probed**: {data['summary']['total_bots_probed']}",
            f"**Summary**: {data['summary']['allowed_count']} Allowed, {data['summary']['blocked_count']} Blocked, {data['summary']['challenged_count']} Challenged",
            "",
            "## Bot Tier Probe Results",
            "| Bot | Tier | HTTP Status | Latency | Result | Primary Diagnostic |",
            "| :--- | :--- | :---: | :---: | :---: | :--- |",
        ]

        for bot_name, b in data["bots"].items():
            if bot_name == "BrowserBaseline":
                continue
            cls = b.get("classification", {})
            st = cls.get("status", "UNKNOWN")
            diag = cls.get("primary_issue", "-")
            status_code = b.get("status_code", 0)
            latency = f"{b.get('latency_ms', 0)}ms"

            if st == "ALLOWED":
                badge = "ALLOWED"
            elif st == "BLOCKED":
                badge = "BLOCKED"
            elif st == "CHALLENGED":
                badge = "CHALLENGED"
            elif st == "DEGRADED":
                badge = "DEGRADED"
            else:
                badge = st

            lines.append(f"| **{bot_name}** | {b.get('tier')} | `{status_code}` | {latency} | {badge} | {diag} |")

        # Browser baseline comparison
        baseline = data["bots"].get("BrowserBaseline")
        if baseline:
            lines.extend([
                "",
                f"### Baseline Browser Control: `{baseline.get('status_code')}` ({baseline.get('latency_ms')}ms)",
            ])

        # Differential cloaking / blocking
        if data["differential_blocks"]:
            lines.extend([
                "",
                "### ⚠️ Differential Bot Discrimination Detected",
                "The server served 200 OK to standard web browsers but blocked or challenged AI crawlers:",
            ])
            for d in data["differential_blocks"]:
                lines.append(f"- **{d['bot']}** ({d['tier']}): Blocked/Challenged with `{d['bot_status']}` - {d['issue']}")

        # Markdown twin results
        twin = data.get("markdown_twin")
        if twin:
            lines.extend([
                "",
                "## Markdown Twin & Content Negotiation",
            ])
            cneg = twin.get("content_negotiation")
            if cneg:
                served = cneg.get("served_markdown", False)
                has_vary = cneg.get("has_vary_accept", False)
                lines.append(f"- **Content Negotiation (`Accept: text/markdown`)**: {'Supported' if served else 'Not supported (served HTML)'} (HTTP `{cneg.get('status_code')}`)")
                if served and not has_vary:
                    lines.append("  - ⚠️ **Missing `Vary: Accept`**: Edge CDN caches may serve markdown to browsers or HTML to AI agents.")
            if twin.get("direct_twin_url"):
                lines.append(f"- **Direct `.md` URL**: Found at `{twin['direct_twin_url']['url']}`")
            if twin.get("llms_txt_url"):
                lines.append(f"- **/llms.txt**: Found at `{twin['llms_txt_url']['url']}`")
            if not twin.get("has_markdown_twin"):
                lines.append("- *No markdown twin or /llms.txt discovered.* Consider adding an `/llms.txt` file to cut token ingestion cost.")

        # Actionable recommendations
        all_diagnoses = []
        for b in data["bots"].values():
            for diag in b.get("classification", {}).get("diagnoses", []):
                if diag not in all_diagnoses:
                    all_diagnoses.append(diag)

        if all_diagnoses:
            lines.extend([
                "",
                "## Root-Cause Remediation Plan",
            ])
            for d in all_diagnoses:
                lines.append(f"- **[{d['severity']}] {d['code']}**: {d['message']}")
                lines.append(f"  - **Fix**: {d['remediation']}")

        result_text = "\n".join(lines)
        dur = (time.time() - t0) * 1000
        track_tool_call(
            "probe_url",
            duration_ms=dur,
            status="success",
            rows_returned=len(data["bots"]),
            result_chars=len(result_text),
            intent=f"Probed {target} ({tier})",
        )
        return result_text

    except Exception as exc:
        dur = (time.time() - t0) * 1000
        cat = classify_exception(exc)
        track_tool_call(
            "probe_url",
            duration_ms=dur,
            status="error",
            error_category=cat,
            error_message=str(exc),
        )
        return f"[TRANSIENT] Probe failed on '{url}': {exc}"


@mcp.tool()
async def audit_robots(domain: str, categories: str = "all") -> str:
    """Fetch and audit a domain's robots.txt across Training, Search, and Live Fetch AI bot tiers.

    Args:
        domain: Domain or URL to audit (e.g. 'stripe.com' or 'https://github.com').
        categories: Tier filter: 'all', 'training', 'search', or 'live_fetch'.
    """
    t0 = time.time()
    try:
        norm = domain.strip()
        if not norm.startswith(("http://", "https://")):
            norm = "https://" + norm

        parsed = urlparse(norm)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            try:
                resp = await client.get(robots_url)
                if resp.status_code == 404:
                    raw_robots = ""
                    note = "No robots.txt found (HTTP 404). All bots are permitted by default."
                elif resp.status_code == 200:
                    raw_robots = resp.text
                    note = f"Successfully parsed robots.txt ({len(raw_robots.splitlines())} lines)."
                else:
                    raw_robots = ""
                    note = f"robots.txt returned HTTP {resp.status_code}."
            except Exception as e:
                raw_robots = ""
                note = f"Failed to fetch robots.txt: {e}"

        parser = parse_robots_txt(raw_robots)
        audit = parser.audit_all_tiers("/")

        lines = [
            f"# robots.txt 3-Tier AI Audit: {parsed.netloc}",
            f"**Robots URL**: `{robots_url}`",
            f"**Status**: {note}",
            "",
            "## AI Tier Summary",
            "| Tier | Status | Allowed Bots | Disallowed Bots | Strategic Intent |",
            "| :--- | :---: | :---: | :---: | :--- |",
        ]

        tier_descriptions = {
            "training": "Model Pre-Training (GPTBot, ClaudeBot, CCBot)",
            "search": "AI Search Citations (OAI-SearchBot, PerplexityBot)",
            "live_fetch": "Interactive User Browsing (ChatGPT-User, Claude-User)",
        }

        for tier_key, t_info in audit["tier_summary"].items():
            st = t_info["status"]
            desc = tier_descriptions.get(tier_key, tier_key)
            lines.append(
                f"| **{tier_key.upper()}** | `{st}` | {t_info['allowed_count']} | {t_info['disallowed_count']} | {desc} |"
            )

        # Detailed breakdown
        lines.extend([
            "",
            "## Bot-by-Bot Rules Breakdown",
            "| Bot Name | Tier | Status | Matched Directive | Purpose |",
            "| :--- | :--- | :---: | :--- | :--- |",
        ])

        for tier_key, bot_list in audit["bots"].items():
            if categories != "all" and categories.lower() != tier_key.lower():
                continue
            for b in bot_list:
                status_icon = "ALLOWED" if b["allowed"] else "DISALLOWED"
                rule = b["matched_rule"] or "-"
                lines.append(f"| **{b['bot']}** | {tier_key} | {status_icon} | `{rule}` | {b.get('description', '-')} |")

        # Sitemaps
        if audit["sitemaps"]:
            lines.extend([
                "",
                "## Discovered Sitemaps",
            ])
            for s in audit["sitemaps"]:
                lines.append(f"- `{s}`")

        # Strategic recommendations
        if audit["strategic_recommendations"]:
            lines.extend([
                "",
                "## Strategic Guidance",
            ])
            for r in audit["strategic_recommendations"]:
                lines.append(f"- {r}")

        result_text = "\n".join(lines)
        dur = (time.time() - t0) * 1000
        track_tool_call(
            "audit_robots",
            duration_ms=dur,
            status="success",
            rows_returned=sum(len(l) for l in audit["bots"].values()),
            result_chars=len(result_text),
            intent=f"Audited robots.txt for {parsed.netloc}",
        )
        return result_text

    except Exception as exc:
        dur = (time.time() - t0) * 1000
        cat = classify_exception(exc)
        track_tool_call(
            "audit_robots",
            duration_ms=dur,
            status="error",
            error_category=cat,
            error_message=str(exc),
        )
        return f"[INPUT_FIXABLE] Could not audit robots.txt for '{domain}': {exc}"


@mcp.tool()
async def compare_readiness(urls: list[str]) -> str:
    """Compare AI crawler readiness across multiple domains or URLs side-by-side.

    Args:
        urls: List of target URLs to evaluate and benchmark (e.g. ['stripe.com', 'adyen.com']).
    """
    t0 = time.time()
    try:
        if not urls:
            return "[INPUT_FIXABLE] Provide at least one URL in the 'urls' list."

        clean_urls = []
        for u in urls[:10]:  # limit to top 10
            u = u.strip()
            if not u.startswith(("http://", "https://")):
                u = "https://" + u
            clean_urls.append(u)

        # Run concurrent probes
        probe_tasks = [run_probe_url(u, tier="all", check_twin=True) for u in clean_urls]
        probe_results = await asyncio.gather(*probe_tasks)

        lines = [
            "# AI Crawler Readiness Benchmark",
            "",
            "| Domain | Search Readiness | Training Policy | Token Bloat | Markdown / llms.txt | Readiness Grade |",
            "| :--- | :---: | :---: | :---: | :---: | :---: |",
        ]

        for res in probe_results:
            p_url = res["url"]
            netloc = urlparse(p_url).netloc

            # Search bots allowed?
            search_bots = [b for name, b in res["bots"].items() if b.get("tier") == "search"]
            search_allowed = all(b.get("classification", {}).get("status") == "ALLOWED" for b in search_bots)

            # Training bots
            training_bots = [b for name, b in res["bots"].items() if b.get("tier") == "training"]
            training_blocked = any(b.get("classification", {}).get("status") in ("BLOCKED", "CHALLENGED") for b in training_bots)

            # Token bloat from baseline
            baseline = res["bots"].get("BrowserBaseline")
            bloat_mult = 1.0
            if baseline and baseline.get("classification", {}).get("token_bloat"):
                bloat_mult = baseline["classification"]["token_bloat"].get("bloat_multiplier", 1.0)

            # Markdown twin / llms.txt
            has_twin = res.get("markdown_twin", {}).get("has_markdown_twin", False)

            # Grade calculation
            score = 100
            if not search_allowed:
                score -= 40
            if bloat_mult > 10.0:
                score -= 20
            elif bloat_mult > 5.0:
                score -= 10
            if not has_twin:
                score -= 15

            if score >= 85:
                grade = "🟢 A (AI Ready)"
            elif score >= 70:
                grade = "🟡 B (Acceptable)"
            elif score >= 50:
                grade = "🟠 C (Impaired)"
            else:
                grade = "🔴 F (Blocked/Severely Bloated)"

            search_str = "Allowed" if search_allowed else "Blocked"
            train_str = "Restricted" if training_blocked else "Allowed"
            bloat_str = f"{bloat_mult}x"
            twin_str = "Available" if has_twin else "Missing"

            lines.append(f"| **{netloc}** | {search_str} | {train_str} | {bloat_str} | {twin_str} | {grade} |")

        lines.extend([
            "",
            "### Legend",
            "- **Search Readiness**: Whether search engine crawlers (OAI-SearchBot, PerplexityBot) can retrieve the page without WAF blocks or challenges.",
            "- **Training Policy**: Whether foundation model training scrapers (GPTBot, ClaudeBot) are permitted or restricted.",
            "- **Token Bloat**: DOM overhead ratio (Raw HTML bytes vs extracted clean text). Lower is more token-efficient for LLM context windows.",
            "- **Markdown / llms.txt**: Presence of native content negotiation or /llms.txt structured docs.",
        ])

        result_text = "\n".join(lines)
        dur = (time.time() - t0) * 1000
        track_tool_call(
            "compare_readiness",
            duration_ms=dur,
            status="success",
            rows_returned=len(probe_results),
            result_chars=len(result_text),
            intent=f"Compared {len(clean_urls)} URLs",
        )
        return result_text

    except Exception as exc:
        dur = (time.time() - t0) * 1000
        cat = classify_exception(exc)
        track_tool_call(
            "compare_readiness",
            duration_ms=dur,
            status="error",
            error_category=cat,
            error_message=str(exc),
        )
        return f"[TRANSIENT] Comparison failed: {exc}"


@mcp.tool()
def bot_directory(query: str = "", category: str = "all") -> str:
    """Search and inspect verified web crawlers and AI bots from Cloudflare Radar Bot Directory (758 verified bots).

    Args:
        query: Search term matching bot name, slug, operator, or user-agent (e.g. 'openai', 'perplexity', 'claude').
        category: Filter by category: 'all', 'AI_CRAWLER', 'AI_SEARCH', 'AI_ASSISTANT', 'SEARCH_ENGINE_CRAWLER', 'ACADEMIC_RESEARCH', etc.
    """
    t0 = time.time()
    try:
        bots = search_bots(query=query, category=category, limit=60)
        all_cats = get_categories()

        lines = [
            f"# Cloudflare Radar Bot Directory ({len(bots)} matching bots)",
            f"**Query**: '{query or 'all'}' | **Category Filter**: '{category}'",
            "",
            "| Slug | Bot Name | Operator | Category | User-Agent Sample |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        for b in bots:
            slug = b.get("slug", "-")
            name = b.get("name", "-")
            operator = b.get("operator") or "Unknown"
            cat = b.get("category", "-")
            uas = b.get("userAgentPatterns") or b.get("userAgents") or []
            sample_ua = uas[0] if uas else "-"
            if len(sample_ua) > 40:
                sample_ua = sample_ua[:37] + "..."

            lines.append(f"| `{slug}` | **{name}** | {operator} | `{cat}` | `{sample_ua}` |")

        if not bots:
            lines.append("")
            lines.append("*No bots found matching query and category.*")
            lines.append(f"Available categories: {', '.join(all_cats)}")

        result_text = "\n".join(lines)
        dur = (time.time() - t0) * 1000
        track_tool_call(
            "bot_directory",
            duration_ms=dur,
            status="success",
            rows_returned=len(bots),
            result_chars=len(result_text),
            intent=f"Query '{query}', Cat '{category}'",
        )
        return result_text

    except Exception as exc:
        dur = (time.time() - t0) * 1000
        cat = classify_exception(exc)
        track_tool_call(
            "bot_directory",
            duration_ms=dur,
            status="error",
            error_category=cat,
            error_message=str(exc),
        )
        return f"[INPUT_FIXABLE] Bot directory query failed: {exc}"


@mcp.tool()
async def generate_llms_txt(domain: str) -> str:
    """Validate existing /llms.txt or generate a compliant CommonMark V2 /llms.txt for a domain.

    Args:
        domain: Target domain or website URL (e.g. 'fastmcp.org' or 'https://docs.anthropic.com').
    """
    t0 = time.time()
    try:
        norm = domain.strip()
        if not norm.startswith(("http://", "https://")):
            norm = "https://" + norm
        parsed = urlparse(norm)
        base_origin = f"{parsed.scheme}://{parsed.netloc}"

        # First check if domain already has /llms.txt
        existing = await fetch_and_validate_llms_txt(base_origin)

        lines = [
            f"# /llms.txt Generator & Validator: {parsed.netloc}",
        ]

        if existing["exists"]:
            val = existing["validation"]
            lines.extend([
                f"**Existing /llms.txt Found**: `{existing['url']}`",
                f"**Validation Status**: {'✅ VALID CommonMark V2' if val['valid'] else '⚠️ INVALID CommonMark V2'} (Score: {val['score']}/100)",
                f"**Title**: {val.get('title') or 'None'}",
                f"**Summary**: {val.get('summary') or 'None'}",
                f"**Total Resource Links**: {val.get('links_count', 0)}",
                f"**Companion /llms-full.txt**: {'Found' if existing['has_llms_full'] else 'Missing'}",
            ])
            if val.get("warnings"):
                lines.append("\n### Specification Warnings")
                for w in val["warnings"]:
                    lines.append(f"- {w}")
            if val.get("errors"):
                lines.append("\n### Specification Errors")
                for e in val["errors"]:
                    lines.append(f"- ❌ {e}")
        else:
            lines.extend([
                f"**Existing /llms.txt**: Not found on `{parsed.netloc}` (`{existing.get('error', 'HTTP 404')}`).",
                "",
                "### Generated CommonMark V2 `/llms.txt` Starter",
                "Deploy this file to the root of your domain (`https://" + parsed.netloc + "/llms.txt`):",
                "",
                "```markdown",
                build_llms_txt(
                    title=parsed.netloc.replace("www.", "").capitalize(),
                    summary=f"Official AI-friendly documentation index and API reference for {parsed.netloc}.",
                    domain=base_origin,
                ),
                "```",
            ])

        result_text = "\n".join(lines)
        dur = (time.time() - t0) * 1000
        track_tool_call(
            "generate_llms_txt",
            duration_ms=dur,
            status="success",
            rows_returned=1,
            result_chars=len(result_text),
            intent=f"Generated/Validated llms.txt for {parsed.netloc}",
        )
        return result_text

    except Exception as exc:
        dur = (time.time() - t0) * 1000
        cat = classify_exception(exc)
        track_tool_call(
            "generate_llms_txt",
            duration_ms=dur,
            status="error",
            error_category=cat,
            error_message=str(exc),
        )
        return f"[INPUT_FIXABLE] Failed to generate/validate llms.txt for '{domain}': {exc}"


@mcp.tool()
def skills_list() -> str:
    """List all dynamic skill playbooks available in ai-crawler-radar."""
    t0 = time.time()
    try:
        skills = set(_SKILLS_REGISTRY.keys())
        if _LOCAL_SKILLS_DIR.is_dir():
            skills.update(f.stem for f in _LOCAL_SKILLS_DIR.glob("*.md"))
        skills_sorted = sorted(skills)
        result_text = f"Available skills: {', '.join(skills_sorted)}"
        dur = (time.time() - t0) * 1000
        track_tool_call(
            "skills_list",
            duration_ms=dur,
            status="success",
            rows_returned=len(skills_sorted),
            result_chars=len(result_text),
            intent="skills_list",
        )
        return result_text
    except Exception as exc:
        dur = (time.time() - t0) * 1000
        track_tool_call(
            "skills_list",
            duration_ms=dur,
            status="error",
            error_category=classify_exception(exc),
            error_message=str(exc),
        )
        return f"Error listing skills: {exc}"


@mcp.tool()
def skill_read(skill_name: str = "ai_crawler_radar_skill") -> str:
    """Read a dynamic skill playbook bundled with ai-crawler-radar.

    Args:
        skill_name: Name of the skill to read (e.g. 'ai_crawler_radar_skill').
    """
    t0 = time.time()
    try:
        content, fetch_ok = _load_skill(skill_name)
        if not content:
            msg = f"[INPUT_FIXABLE] Skill '{skill_name}' not found. Use skills_list() to view available playbooks."
            dur = (time.time() - t0) * 1000
            track_tool_call(
                "skill_read",
                duration_ms=dur,
                status="error",
                error_category="NotFoundError",
                error_message=f"Skill '{skill_name}' not found",
            )
            return msg

        dur = (time.time() - t0) * 1000
        track_tool_call(
            "skill_read",
            duration_ms=dur,
            status="success",
            rows_returned=1,
            result_chars=len(content),
            intent=f"Read skill {skill_name}",
        )
        return content
    except Exception as exc:
        dur = (time.time() - t0) * 1000
        track_tool_call(
            "skill_read",
            duration_ms=dur,
            status="error",
            error_category=classify_exception(exc),
            error_message=str(exc),
        )
        return f"Error reading skill {skill_name}: {exc}"


def main():
    """Runs the MCP server over stdio."""
    if hasattr(mcp, "run"):
        try:
            mcp.run()
        except TypeError:
            mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
