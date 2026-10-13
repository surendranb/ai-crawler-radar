# SPDX-License-Identifier: MIT
"""Asynchronous HTTP prober for AI search, training, and live user fetchers."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

import httpx

from ai_crawler_radar.classifier import classify_response

# Authentic User-Agent Strings & Header Profiles
BOT_PROFILES: Dict[str, Dict[str, Any]] = {
    "GPTBot": {
        "tier": "training",
        "operator": "OpenAI",
        "user_agent": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    "ClaudeBot": {
        "tier": "training",
        "operator": "Anthropic",
        "user_agent": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ClaudeBot/1.0; +https://anthropic.com/claudebot",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    "OAI-SearchBot": {
        "tier": "search",
        "operator": "OpenAI",
        "user_agent": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    "PerplexityBot": {
        "tier": "search",
        "operator": "Perplexity AI",
        "user_agent": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; PerplexityBot/1.0; +https://docs.perplexity.ai/docs/perplexitybot",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    "ChatGPT-User": {
        "tier": "live_fetch",
        "operator": "OpenAI",
        "user_agent": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    "Claude-User": {
        "tier": "live_fetch",
        "operator": "Anthropic",
        "user_agent": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +claude-user@anthropic.com)",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    "BrowserBaseline": {
        "tier": "baseline",
        "operator": "Standard Chrome Browser",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    },
}


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


async def probe_single_bot(
    client: httpx.AsyncClient,
    url: str,
    bot_name: str,
    profile: Dict[str, Any],
    custom_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Sends an authentic HTTP probe imitating a specific AI bot."""
    headers = {
        "User-Agent": profile["user_agent"],
        "Accept": profile.get("accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    if custom_headers:
        headers.update(custom_headers)

    t0 = time.time()
    try:
        resp = await client.get(url, headers=headers)
        latency_ms = round((time.time() - t0) * 1000, 1)

        resp_headers = dict(resp.headers)
        body_text = resp.text
        status_code = resp.status_code
        final_url = str(resp.url)

        classification = classify_response(
            status_code=status_code,
            headers=resp_headers,
            body_text=body_text,
            requested_accept=headers.get("Accept", "text/html"),
        )

        return {
            "bot": bot_name,
            "tier": profile.get("tier", "unknown"),
            "operator": profile.get("operator", "unknown"),
            "status_code": status_code,
            "latency_ms": latency_ms,
            "final_url": final_url,
            "content_type": resp_headers.get("content-type", ""),
            "content_length": len(resp.content),
            "headers": {
                k: v for k, v in resp_headers.items()
                if k.lower() in ("server", "cf-ray", "cf-cache-status", "content-type", "vary", "x-amzn-waf-action", "x-cache")
            },
            "classification": classification,
            "error": None,
        }

    except httpx.TimeoutException:
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "bot": bot_name,
            "tier": profile.get("tier", "unknown"),
            "operator": profile.get("operator", "unknown"),
            "status_code": 408,
            "latency_ms": latency_ms,
            "final_url": url,
            "content_type": "",
            "content_length": 0,
            "headers": {},
            "classification": {
                "status": "TIMEOUT",
                "primary_issue": "HTTP request timed out before response was received.",
                "diagnoses": [{
                    "code": "REQUEST_TIMEOUT",
                    "severity": "CRITICAL",
                    "message": f"Server failed to respond within timeout for {bot_name}.",
                    "remediation": "Investigate network connectivity, aggressive rate limiting, or connection dropping.",
                }],
            },
            "error": "TimeoutException",
        }
    except Exception as exc:
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "bot": bot_name,
            "tier": profile.get("tier", "unknown"),
            "operator": profile.get("operator", "unknown"),
            "status_code": 0,
            "latency_ms": latency_ms,
            "final_url": url,
            "content_type": "",
            "content_length": 0,
            "headers": {},
            "classification": {
                "status": "CONNECTION_FAILED",
                "primary_issue": f"Connection failed: {str(exc)}",
                "diagnoses": [{
                    "code": "CONNECTION_ERROR",
                    "severity": "CRITICAL",
                    "message": str(exc),
                    "remediation": "Check DNS resolution, TLS certificates, or firewall blocking IP.",
                }],
            },
            "error": str(exc),
        }


async def check_markdown_twin(client: httpx.AsyncClient, base_url: str) -> Dict[str, Any]:
    """Probes whether a markdown twin or content-negotiated markdown is available."""
    twin_results: Dict[str, Any] = {
        "content_negotiation": None,
        "direct_twin_url": None,
        "llms_txt_url": None,
        "has_markdown_twin": False,
        "details": [],
    }

    # 1. Content Negotiation with Accept: text/markdown
    try:
        cneg_resp = await client.get(
            base_url,
            headers={
                "User-Agent": BOT_PROFILES["OAI-SearchBot"]["user_agent"],
                "Accept": "text/markdown, text/x-markdown, text/plain;q=0.9",
            },
        )
        c_type = cneg_resp.headers.get("content-type", "").lower()
        vary = cneg_resp.headers.get("vary", "").lower()
        has_vary = "accept" in vary or "*" in vary

        is_markdown = "text/markdown" in c_type or "text/x-markdown" in c_type
        twin_results["content_negotiation"] = {
            "status_code": cneg_resp.status_code,
            "content_type": c_type,
            "has_vary_accept": has_vary,
            "served_markdown": is_markdown,
        }
        if is_markdown:
            twin_results["has_markdown_twin"] = True
            twin_results["details"].append(
                f"Native Markdown Twin served via Content Negotiation (Status {cneg_resp.status_code}, Type: {c_type})"
            )
            if not has_vary:
                twin_results["details"].append("Warning: Missing 'Vary: Accept' header on negotiated markdown response.")
    except Exception as e:
        twin_results["content_negotiation"] = {"error": str(e)}

    # 2. Check direct URL + .md (e.g. https://example.com/page.md)
    parsed = urlparse(base_url)
    if parsed.path and parsed.path != "/" and not parsed.path.endswith(".md"):
        twin_url = base_url.rstrip("/") + ".md"
        try:
            twin_resp = await client.get(
                twin_url,
                headers={"User-Agent": BOT_PROFILES["OAI-SearchBot"]["user_agent"]},
            )
            if twin_resp.status_code == 200:
                twin_results["direct_twin_url"] = {
                    "url": twin_url,
                    "status_code": 200,
                    "content_length": len(twin_resp.content),
                }
                twin_results["has_markdown_twin"] = True
                twin_results["details"].append(f"Direct markdown twin found at {twin_url}")
        except Exception:
            pass

    # 3. Check /llms.txt at root domain
    root_llms_url = f"{parsed.scheme}://{parsed.netloc}/llms.txt"
    try:
        llms_resp = await client.get(
            root_llms_url,
            headers={"User-Agent": BOT_PROFILES["OAI-SearchBot"]["user_agent"]},
        )
        if llms_resp.status_code == 200:
            twin_results["llms_txt_url"] = {
                "url": root_llms_url,
                "status_code": 200,
                "content_length": len(llms_resp.content),
            }
            twin_results["details"].append(f"Standard /llms.txt discovered at {root_llms_url}")
    except Exception:
        pass

    return twin_results


async def probe_url(
    url: str,
    tier: str = "all",
    check_twin: bool = True,
    timeout: float = 12.0,
) -> Dict[str, Any]:
    """Runs concurrent async HTTP probes across AI bot tiers against a target URL."""
    target_url = _normalize_url(url)
    tier_filter = tier.strip().lower()

    # Filter bot profiles
    selected_profiles = {}
    for name, prof in BOT_PROFILES.items():
        if tier_filter == "all":
            selected_profiles[name] = prof
        elif tier_filter == prof["tier"]:
            selected_profiles[name] = prof

    # Always include BrowserBaseline for differential comparison
    if "BrowserBaseline" not in selected_profiles and tier_filter != "all":
        selected_profiles["BrowserBaseline"] = BOT_PROFILES["BrowserBaseline"]

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(timeout, connect=5.0),
        verify=True,
    ) as client:
        # Fan-out parallel requests
        tasks = [
            probe_single_bot(client, target_url, name, prof)
            for name, prof in selected_profiles.items()
        ]

        twin_task = check_markdown_twin(client, target_url) if check_twin else None

        results = await asyncio.gather(*tasks)
        twin_data = await twin_task if twin_task else None

    # Organize probe results
    bot_results: Dict[str, Any] = {r["bot"]: r for r in results}
    baseline = bot_results.get("BrowserBaseline")

    # Differential analysis (comparing AI bots against BrowserBaseline)
    differential_blocks = []
    if baseline and baseline.get("status_code") == 200:
        for bot_name, r in bot_results.items():
            if bot_name == "BrowserBaseline":
                continue
            if r.get("status_code") in (403, 406, 503) or r.get("classification", {}).get("status") in ("BLOCKED", "CHALLENGED"):
                differential_blocks.append({
                    "bot": bot_name,
                    "tier": r.get("tier"),
                    "browser_status": baseline.get("status_code"),
                    "bot_status": r.get("status_code"),
                    "issue": r.get("classification", {}).get("primary_issue"),
                })

    return {
        "url": target_url,
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bots": bot_results,
        "markdown_twin": twin_data,
        "differential_blocks": differential_blocks,
        "summary": {
            "total_bots_probed": len([b for b in bot_results if b != "BrowserBaseline"]),
            "blocked_count": len([b for b in bot_results.values() if b.get("classification", {}).get("status") == "BLOCKED"]),
            "challenged_count": len([b for b in bot_results.values() if b.get("classification", {}).get("status") == "CHALLENGED"]),
            "allowed_count": len([b for b in bot_results.values() if b.get("classification", {}).get("status") == "ALLOWED"]),
            "has_differential_cloaking": len(differential_blocks) > 0,
        },
    }
