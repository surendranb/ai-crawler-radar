# SPDX-License-Identifier: MIT
"""Bot catalog loader and search engine for Cloudflare Radar verified bots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_FILE = Path(__file__).resolve().parent / "data" / "bots.json"
_CACHED_BOTS: Optional[List[Dict[str, Any]]] = None
_CACHED_CATEGORIES: Optional[List[str]] = None


def load_bot_directory() -> List[Dict[str, Any]]:
    """Loads and caches the 758 verified bots from Cloudflare Radar dataset."""
    global _CACHED_BOTS, _CACHED_CATEGORIES
    if _CACHED_BOTS is not None:
        return _CACHED_BOTS

    if not _DATA_FILE.exists():
        raise FileNotFoundError(f"Bot directory data file not found at {_DATA_FILE}")

    with open(_DATA_FILE, "r", encoding="utf-8") as f:
        bots = json.load(f)

    _CACHED_BOTS = bots
    cats = sorted({b.get("category") for b in bots if b.get("category")})
    _CACHED_CATEGORIES = cats
    return _CACHED_BOTS


def get_categories() -> List[str]:
    """Returns all distinct bot categories in the directory."""
    global _CACHED_CATEGORIES
    if _CACHED_CATEGORIES is None:
        load_bot_directory()
    return _CACHED_CATEGORIES or []


def get_bot_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Look up a bot by its unique slug."""
    bots = load_bot_directory()
    slug_lower = slug.strip().lower()
    for b in bots:
        if (b.get("slug") or "").lower() == slug_lower:
            return b
    return None


def search_bots(
    query: str = "",
    category: str = "all",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Search and filter bots by text query and category.

    Args:
        query: Substring match against name, slug, operator, description, or user agents.
        category: Exact category or category filter (e.g. 'all', 'AI_CRAWLER', 'ai').
        limit: Maximum number of bot records to return.
    """
    bots = load_bot_directory()
    q = query.strip().lower()
    cat_filter = category.strip().upper()

    results: List[Dict[str, Any]] = []

    for b in bots:
        b_cat = (b.get("category") or "").upper()
        if cat_filter != "ALL":
            if cat_filter == "AI":
                if not ("AI" in b_cat or "CRAWLER" in b_cat or "SEARCH" in b_cat):
                    continue
            elif cat_filter != b_cat:
                continue

        if not q:
            results.append(b)
        else:
            name = (b.get("name") or "").lower()
            slug = (b.get("slug") or "").lower()
            operator = (b.get("operator") or "").lower()
            desc = (b.get("description") or "").lower()
            uas = [ua.lower() for ua in (b.get("userAgents") or [])]
            patterns = [p.lower() for p in (b.get("userAgentPatterns") or [])]

            if (
                q in name
                or q in slug
                or q in operator
                or q in desc
                or any(q in ua for ua in uas)
                or any(q in p for p in patterns)
            ):
                results.append(b)

        if limit > 0 and len(results) >= limit:
            break

    return results


def find_matching_bots_for_ua(user_agent: str) -> List[Dict[str, Any]]:
    """Finds bot catalog entries whose user agent pattern matches the given User-Agent string."""
    bots = load_bot_directory()
    ua_lower = user_agent.lower()
    matches = []

    for b in bots:
        patterns = b.get("userAgentPatterns") or []
        user_agents = b.get("userAgents") or []

        matched = False
        for p in patterns:
            if p.lower() in ua_lower:
                matched = True
                break
        if not matched:
            for u in user_agents:
                if u.lower() in ua_lower:
                    matched = True
                    break

        if matched:
            matches.append(b)

    return matches
