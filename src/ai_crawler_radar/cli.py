# SPDX-License-Identifier: MIT
"""Standalone command line interface for ai-crawler-radar."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import List, Optional

from ai_crawler_radar.catalog import search_bots, get_categories
from ai_crawler_radar.llms_txt import fetch_and_validate_llms_txt, generate_llms_txt as build_llms_txt
from ai_crawler_radar.prober import probe_url as run_probe_url
from ai_crawler_radar.robots_parser import parse_robots_txt
import httpx


def _print_error(msg: str):
    sys.stderr.write(f"\033[0;31mError:\033[0m {msg}\n")


def cmd_probe(args: argparse.Namespace):
    url = args.url.strip()
    tier = args.tier
    check_twin = not args.no_twin

    result = asyncio.run(run_probe_url(url, tier=tier, check_twin=check_twin))

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"\n\033[1;36m=== AI Crawler Radar Probe: {result['url']} ===\033[0m")
    print(f"Summary: \033[0;32m{result['summary']['allowed_count']} Allowed\033[0m, "
          f"\033[0;31m{result['summary']['blocked_count']} Blocked\033[0m, "
          f"\033[1;33m{result['summary']['challenged_count']} Challenged\033[0m\n")

    for bot_name, b in result["bots"].items():
        if bot_name == "BrowserBaseline":
            continue
        cls = b.get("classification", {})
        st = cls.get("status", "UNKNOWN")
        status_code = b.get("status_code", 0)
        latency = f"{b.get('latency_ms', 0)}ms"

        if st == "ALLOWED":
            badge = "\033[0;32m[ALLOWED]\033[0m"
        elif st in ("BLOCKED", "CHALLENGED"):
            badge = f"\033[0;31m[{st}]\033[0m"
        else:
            badge = f"\033[1;33m[{st}]\033[0m"

        print(f"• {bot_name:<16} ({b.get('tier'):<10}) -> HTTP {status_code:<3} ({latency:<7}) {badge} {cls.get('primary_issue')}")

    baseline = result["bots"].get("BrowserBaseline")
    if baseline:
        print(f"\nBrowser Control   : HTTP {baseline.get('status_code')} ({baseline.get('latency_ms')}ms)")

    if result.get("differential_blocks"):
        print("\n\033[1;33m⚠️ Differential Blocking Detected:\033[0m Server permits browsers but blocks AI crawlers.")

    twin = result.get("markdown_twin")
    if twin and twin.get("has_markdown_twin"):
        print(f"\n\033[0;32m✔ Markdown Twin Available:\033[0m {', '.join(twin.get('details', []))}")


def cmd_audit(args: argparse.Namespace):
    domain = args.domain.strip()
    if not domain.startswith(("http://", "https://")):
        domain = "https://" + domain

    from urllib.parse import urlparse
    parsed = urlparse(domain)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        resp = httpx.get(robots_url, follow_redirects=True, timeout=10.0)
        raw_robots = resp.text if resp.status_code == 200 else ""
    except Exception as e:
        _print_error(f"Failed to fetch {robots_url}: {e}")
        raw_robots = ""

    parser = parse_robots_txt(raw_robots)
    audit = parser.audit_all_tiers("/")

    if args.json:
        print(json.dumps(audit, indent=2))
        return

    print(f"\n\033[1;36m=== robots.txt 3-Tier AI Audit: {parsed.netloc} ===\033[0m")
    for tier, t_info in audit["tier_summary"].items():
        st = t_info["status"]
        if st == "ALL_ALLOWED":
            color = "\033[0;32m"
        elif st == "ALL_BLOCKED":
            color = "\033[0;31m"
        else:
            color = "\033[1;33m"
        print(f"Tier {tier.upper():<11}: {color}{st:<11}\033[0m ({t_info['allowed_count']} allowed, {t_info['disallowed_count']} disallowed)")

    print("\n\033[1mBot Breakdown:\033[0m")
    for tier, bots in audit["bots"].items():
        for b in bots:
            st = "\033[0;32mALLOWED\033[0m" if b["allowed"] else "\033[0;31mDISALLOWED\033[0m"
            print(f"  [{tier:<10}] {b['bot']:<18} -> {st} ({b['matched_rule'] or 'default allow'})")

    if audit.get("strategic_recommendations"):
        print("\n\033[1;36mStrategic Recommendations:\033[0m")
        for r in audit["strategic_recommendations"]:
            print(f"  • {r}")


def cmd_bots(args: argparse.Namespace):
    query = args.query or ""
    category = args.category or "all"
    bots = search_bots(query=query, category=category, limit=args.limit)

    if args.json:
        print(json.dumps(bots, indent=2))
        return

    print(f"\n\033[1;36m=== Cloudflare Radar Bot Directory ({len(bots)} matching bots) ===\033[0m\n")
    for b in bots:
        operator = b.get("operator") or "Unknown"
        cat = b.get("category") or "OTHER"
        print(f"• \033[1m{b.get('name')}\033[0m ({b.get('slug')}) | Operator: {operator} | Category: \033[0;34m{cat}\033[0m")
        desc = b.get("description")
        if desc:
            print(f"  \033[2m{desc.strip()[:100]}...\033[0m" if len(desc) > 100 else f"  \033[2m{desc.strip()}\033[0m")


def cmd_llmstxt(args: argparse.Namespace):
    domain = args.domain.strip()
    if args.generate:
        from urllib.parse import urlparse
        if not domain.startswith("http"):
            domain = "https://" + domain
        parsed = urlparse(domain)
        txt = build_llms_txt(
            title=parsed.netloc.replace("www.", "").capitalize(),
            summary=f"AI documentation index for {parsed.netloc}",
            domain=domain,
        )
        print(txt)
        return

    res = asyncio.run(fetch_and_validate_llms_txt(domain))
    if args.json:
        print(json.dumps(res, indent=2))
        return

    if res["exists"]:
        val = res["validation"]
        badge = "\033[0;32m[VALID]\033[0m" if val["valid"] else "\033[0;31m[INVALID]\033[0m"
        print(f"\n/llms.txt found at {res['url']} {badge} (Score: {val['score']}/100)")
        print(f"Title: {val.get('title')}")
        print(f"Summary: {val.get('summary')}")
        print(f"Links count: {val.get('links_count')}")
    else:
        print(f"\n/llms.txt NOT found on {domain} ({res.get('error')})")
        print("Run with `--generate` to output a compliant CommonMark V2 template.")


def main():
    parser = argparse.ArgumentParser(
        prog="ai-crawler-radar",
        description="Autonomous AI Search, Training & Agent Crawler Diagnostic Engine (Fleet v2 Standard).",
    )
    parser.add_argument("--mcp", action="store_true", help="Launch the MCP stdio server")
    subparsers = parser.add_subparsers(dest="command")

    # probe
    p_probe = subparsers.add_parser("probe", help="Probe URL with authentic AI bot headers")
    p_probe.add_argument("url", help="Target URL to probe")
    p_probe.add_argument("--tier", default="all", choices=["all", "training", "search", "live_fetch"], help="Bot tier filter")
    p_probe.add_argument("--no-twin", action="store_true", help="Skip markdown twin content negotiation check")
    p_probe.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # audit
    p_audit = subparsers.add_parser("audit", help="Audit domain robots.txt across 3 AI tiers")
    p_audit.add_argument("domain", help="Target domain (e.g. stripe.com)")
    p_audit.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # bots
    p_bots = subparsers.add_parser("bots", help="Search 758 verified Cloudflare Radar bots")
    p_bots.add_argument("--query", "-q", default="", help="Query string")
    p_bots.add_argument("--category", "-c", default="all", help="Category filter")
    p_bots.add_argument("--limit", "-n", type=int, default=50, help="Max results")
    p_bots.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # llmstxt
    p_llms = subparsers.add_parser("llmstxt", help="Validate or generate /llms.txt")
    p_llms.add_argument("domain", help="Target domain")
    p_llms.add_argument("--generate", action="store_true", help="Generate template /llms.txt")
    p_llms.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # serve
    subparsers.add_parser("serve", help="Run MCP stdio server")

    args = parser.parse_args()

    if args.mcp or args.command == "serve" or args.command is None:
        # Default behavior with no arguments or serve is to run FastMCP stdio server
        from ai_crawler_radar.server import main as run_server
        run_server()
        return

    if args.command == "probe":
        cmd_probe(args)
    elif args.command == "audit":
        cmd_audit(args)
    elif args.command == "bots":
        cmd_bots(args)
    elif args.command == "llmstxt":
        cmd_llmstxt(args)


if __name__ == "__main__":
    main()
