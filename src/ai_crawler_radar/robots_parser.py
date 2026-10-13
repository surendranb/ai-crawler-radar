# SPDX-License-Identifier: MIT
"""RFC 9309 compliant multi-bot 3-tier robots.txt rules parser."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Canonical Bot Tiers
BOT_TIERS: Dict[str, Dict[str, str]] = {
    "training": {
        "GPTBot": "OpenAI Model Training & Fine-Tuning",
        "ClaudeBot": "Anthropic Model Pre-Training",
        "Google-Extended": "Google Gemini Training",
        "Meta-ExternalAgent": "Meta Llama Training",
        "Bytespider": "ByteDance Model Training",
        "CCBot": "Common Crawl Training Dataset",
        "cohere-ai": "Cohere Model Training",
    },
    "search": {
        "OAI-SearchBot": "OpenAI ChatGPT Search Indexer",
        "PerplexityBot": "Perplexity AI Search & Citations",
        "Claude-SearchBot": "Anthropic Claude Search Indexer",
        "Applebot": "Apple Intelligence & Siri Indexer",
        "Bingbot": "Microsoft Bing & Copilot Indexer",
    },
    "live_fetch": {
        "ChatGPT-User": "ChatGPT Real-Time User Prompt Browsing",
        "Claude-User": "Claude Real-Time User Prompt Fetcher",
        "Perplexity-User": "Perplexity Live Query Fetcher",
    },
}


class Rule:
    def __init__(self, is_allow: bool, pattern: str, line_num: int) -> None:
        self.is_allow = is_allow
        self.pattern = pattern
        self.line_num = line_num
        self.regex = self._compile_pattern(pattern)

    @staticmethod
    def _compile_pattern(pattern: str) -> Optional[re.Pattern]:
        if not pattern:
            return None
        # RFC 9309 pattern matching:
        # Wildcard * matches 0 or more chars.
        # $ at the end anchors to the end of URL path.
        parts = []
        i = 0
        n = len(pattern)
        has_end_anchor = pattern.endswith("$")
        pat_clean = pattern[:-1] if has_end_anchor else pattern

        for char in pat_clean:
            if char == "*":
                parts.append(".*")
            else:
                parts.append(re.escape(char))

        regex_str = "^" + "".join(parts)
        if has_end_anchor:
            regex_str += "$"
        else:
            # Prefix match
            regex_str += ".*"

        return re.compile(regex_str)

    def matches(self, path: str) -> bool:
        if not self.pattern:  # Empty Disallow: clears disallows -> does not block
            return False
        if not self.regex:
            return False
        return bool(self.regex.match(path))


class UserAgentGroup:
    def __init__(self, user_agents: List[str]) -> None:
        self.user_agents = [ua.lower() for ua in user_agents]
        self.rules: List[Rule] = []
        self.crawl_delay: Optional[float] = None

    def matches_bot(self, bot_name: str) -> bool:
        b_lower = bot_name.lower()
        for ua in self.user_agents:
            if ua == "*" or ua == b_lower:
                return True
        return False

    def is_exact_match(self, bot_name: str) -> bool:
        b_lower = bot_name.lower()
        return any(ua == b_lower for ua in self.user_agents)


class RobotsTxt:
    """Parser and evaluator for robots.txt files following RFC 9309 rules."""

    def __init__(self, content: str) -> None:
        self.raw_content = content
        self.groups: List[UserAgentGroup] = []
        self.sitemaps: List[str] = []
        self._parse(content)

    def _parse(self, content: str) -> None:
        current_uas: List[str] = []
        current_rules: List[Rule] = []
        current_delay: Optional[float] = None
        in_rule_block = False

        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            # Strip comments
            line = line.split("#", 1)[0].strip()
            if not line:
                continue

            if ":" not in line:
                continue

            directive, value = line.split(":", 1)
            directive = directive.strip().lower()
            value = value.strip()

            if directive == "user-agent":
                if in_rule_block:
                    # Flush previous group
                    if current_uas:
                        grp = UserAgentGroup(current_uas)
                        grp.rules = current_rules
                        grp.crawl_delay = current_delay
                        self.groups.append(grp)
                    current_uas = []
                    current_rules = []
                    current_delay = None
                    in_rule_block = False

                current_uas.append(value)

            elif directive in ("allow", "disallow"):
                in_rule_block = True
                is_allow = (directive == "allow")
                if not is_allow and not value:
                    # RFC 9309: An empty Disallow cancels all previously defined Disallow directives in this group
                    current_rules = [r for r in current_rules if r.is_allow]
                else:
                    current_rules.append(Rule(is_allow=is_allow, pattern=value, line_num=idx))

            elif directive == "crawl-delay":
                in_rule_block = True
                try:
                    current_delay = float(value)
                except ValueError:
                    pass

            elif directive == "sitemap":
                if value and value not in self.sitemaps:
                    self.sitemaps.append(value)

        # Flush last group
        if current_uas:
            grp = UserAgentGroup(current_uas)
            grp.rules = current_rules
            grp.crawl_delay = current_delay
            self.groups.append(grp)

    def evaluate_bot(self, bot_name: str, path: str = "/") -> Dict[str, Any]:
        """Evaluates whether a specific bot is allowed to crawl a given path."""
        # Find matching group: exact match takes precedence over wildcard '*'
        exact_group: Optional[UserAgentGroup] = None
        wildcard_group: Optional[UserAgentGroup] = None

        for grp in self.groups:
            if grp.is_exact_match(bot_name):
                exact_group = grp
                break
            elif "*" in grp.user_agents:
                wildcard_group = grp

        target_group = exact_group or wildcard_group

        if target_group is None:
            return {
                "bot": bot_name,
                "allowed": True,
                "status": "ALLOWED",
                "matched_rule": None,
                "matched_group": "none (default allow)",
                "crawl_delay": None,
            }

        matched_group_name = bot_name if exact_group else "*"

        # RFC 9309 Rule Matching:
        # Longest matching pattern wins.
        # If lengths are equal and there's a conflict, Allow wins.
        best_rule: Optional[Rule] = None
        best_length = -1

        for rule in target_group.rules:
            # Empty Disallow: clears all previous disallows -> means Allow
            if not rule.is_allow and rule.pattern == "":
                if best_length <= 0:
                    best_rule = Rule(is_allow=True, pattern="", line_num=rule.line_num)
                    best_length = 0
                continue

            if rule.matches(path):
                pat_len = len(rule.pattern)
                if pat_len > best_length:
                    best_rule = rule
                    best_length = pat_len
                elif pat_len == best_length:
                    # Tie-break: Allow wins over Disallow
                    if rule.is_allow and (best_rule is not None and not best_rule.is_allow):
                        best_rule = rule

        if best_rule is None:
            # Default allow if no matching rule applies to path
            allowed = True
            rule_str = "No specific path rule matched (default allow)"
        else:
            allowed = best_rule.is_allow
            rule_str = f"{'Allow' if best_rule.is_allow else 'Disallow'}: {best_rule.pattern} (line {best_rule.line_num})"

        status = "ALLOWED" if allowed else "DISALLOWED"

        return {
            "bot": bot_name,
            "allowed": allowed,
            "status": status,
            "matched_rule": rule_str,
            "matched_group": matched_group_name,
            "crawl_delay": target_group.crawl_delay,
        }

    def audit_all_tiers(self, path: str = "/") -> Dict[str, Any]:
        """Audits robots.txt rules across all 3 AI bot tiers."""
        results: Dict[str, Any] = {
            "tier_summary": {},
            "bots": {},
            "sitemaps": self.sitemaps,
            "strategic_recommendations": [],
        }

        tier_counts: Dict[str, Dict[str, int]] = {
            tier: {"allowed": 0, "disallowed": 0, "total": 0}
            for tier in BOT_TIERS
        }

        for tier, bots in BOT_TIERS.items():
            results["bots"][tier] = []
            for bot_name, description in bots.items():
                eval_res = self.evaluate_bot(bot_name, path=path)
                eval_res["description"] = description
                eval_res["tier"] = tier
                results["bots"][tier].append(eval_res)

                tier_counts[tier]["total"] += 1
                if eval_res["allowed"]:
                    tier_counts[tier]["allowed"] += 1
                else:
                    tier_counts[tier]["disallowed"] += 1

            allowed_c = tier_counts[tier]["allowed"]
            total_c = tier_counts[tier]["total"]

            if allowed_c == total_c:
                t_status = "ALL_ALLOWED"
            elif allowed_c == 0:
                t_status = "ALL_BLOCKED"
            else:
                t_status = "MIXED"

            results["tier_summary"][tier] = {
                "status": t_status,
                "allowed_count": allowed_c,
                "disallowed_count": tier_counts[tier]["disallowed"],
                "total_count": total_c,
            }

        # Strategic recommendations
        training_blocked = (results["tier_summary"]["training"]["status"] == "ALL_BLOCKED")
        search_allowed = (results["tier_summary"]["search"]["status"] == "ALL_ALLOWED")
        search_blocked = (results["tier_summary"]["search"]["status"] == "ALL_BLOCKED")

        if training_blocked and search_allowed:
            results["strategic_recommendations"].append(
                "Optimal AI Search Posture: Training bots (GPTBot, ClaudeBot) are blocked from ingesting IP, "
                "while Search bots (OAI-SearchBot, PerplexityBot) are allowed for search discovery and citations."
            )
        elif search_blocked:
            results["strategic_recommendations"].append(
                "AI Search Visibility Warning: Search bots (OAI-SearchBot, PerplexityBot) are blocked. "
                "Your content will not appear in ChatGPT Search answers, Perplexity sources, or Siri AI summaries."
            )
        elif not training_blocked:
            results["strategic_recommendations"].append(
                "Training Ingestion Notice: Frontier AI training bots (GPTBot, ClaudeBot) are currently permitted. "
                "If you wish to prevent AI model training while preserving search citations, explicitly disallow GPTBot and ClaudeBot."
            )

        return results


def parse_robots_txt(content: str) -> RobotsTxt:
    """Convenience helper to instantiate RobotsTxt parser."""
    return RobotsTxt(content)
