# ⚡ ai-crawler-radar

[![CI](https://github.com/surendranb/ai-crawler-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/surendranb/ai-crawler-radar/actions)
[![PyPI version](https://img.shields.io/pypi/v/ai-crawler-radar.svg?style=flat-square&color=blue)](https://pypi.org/project/ai-crawler-radar/)
[![NPM version](https://img.shields.io/npm/v/@surendranb/ai-crawler-radar.svg?style=flat-square&color=green)](https://www.npmjs.com/package/@surendranb/ai-crawler-radar)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

> **Autonomous AI Search, Training & Agent Crawler Diagnostic Engine.**  
> Probes live web pages with authentic AI bot signatures, audits `robots.txt` across 3 tiers, identifies WAF hard-blocks & Turnstile challenges, calculates token bloat multipliers, and validates `/llms.txt`.

**Zero API keys. Zero cloud dependencies. 100% Local-first probe execution.**

---

## 🚀 Quick Start

### ⚡ Option 1: Universal 1-Line Installer
```bash
curl -fsSL https://crawler.builditwithai.xyz/install | bash
```

### 🐍 Option 2: Run via Python (`uvx`)
```bash
# Launch interactive MCP stdio server
uvx ai-crawler-radar

# Or run CLI directly
uvx ai-crawler-radar probe https://example.com
uvx ai-crawler-radar audit stripe.com
```

### 📦 Option 3: Run via Node (`npx`)
```bash
npx @surendranb/ai-crawler-radar probe https://example.com
```

---

## 🛠️ Model Context Protocol (MCP) Setup

Add `ai-crawler-radar` directly to your favorite agent harness:

### 🤖 Claude Desktop / Claude Code
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "ai-crawler-radar": {
      "command": "uvx",
      "args": ["ai-crawler-radar"]
    }
  }
}
```

### 💻 Cursor / Windsurf / Antigravity / OpenCode
Add to your IDE MCP configuration:
```json
{
  "mcpServers": {
    "ai-crawler-radar": {
      "command": "uvx",
      "args": ["ai-crawler-radar"]
    }
  }
}
```

---

## 🧭 The 3-Tier AI Bot Model

`ai-crawler-radar` evaluates crawler posture across three distinct operational tiers:

| Tier | Primary Crawlers | Strategic Purpose | Typical Recommendation |
| :--- | :--- | :--- | :--- |
| **Tier 1: Model Pre-Training** | `GPTBot`, `ClaudeBot`, `Google-Extended`, `Meta-ExternalAgent`, `Bytespider`, `CCBot` | Bulk offline data harvesting to pre-train foundation models | Block if protecting proprietary intellectual property |
| **Tier 2: AI Search Indexing** | `OAI-SearchBot`, `PerplexityBot`, `Claude-SearchBot`, `Applebot`, `Bingbot` | Real-time indexing to power SearchGPT, Perplexity & Siri citations | **Allow** to drive citations and conversational discovery |
| **Tier 3: Live User Fetchers** | `ChatGPT-User`, `Claude-User`, `Perplexity-User` | Real-time URL fetching triggered by an active human chat prompt | **Allow** for link previews and interactive agent assistance |

---

## 📡 Available MCP Tools

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `probe_url` | `url`, `tier`, `check_markdown_twin` | Probes URL using authentic headers across bot tiers; diagnoses WAF hard-blocks, Turnstile challenges, CSR empty shells, and token bloat multipliers. |
| `audit_robots` | `domain`, `categories` | RFC 9309 rules parser evaluating permissions across Training, Search, and Live Fetch tiers with strategic recommendations. |
| `compare_readiness` | `urls` | Multi-domain side-by-side benchmark comparing AI crawler readiness, token efficiency, and `/llms.txt` adoption. |
| `bot_directory` | `query`, `category` | Search and inspect 758 verified bots from Cloudflare Radar Bot Directory. |
| `generate_llms_txt` | `domain` | Validates existing `/llms.txt` against CommonMark V2 standard, or generates a compliant starter specification. |
| `skill_read` | `skill_name` | Read bundled operational playbooks dynamically. |
| `skills_list` | *(none)* | List available operational skills. |

---

## 🖥️ Command Line (CLI) Usage

```bash
# Probe URL with authentic AI bot signatures
ai-crawler-radar probe https://docs.anthropic.com

# Audit domain robots.txt across 3 bot tiers
ai-crawler-radar audit github.com

# Search Cloudflare Radar Bot Directory (758 verified bots)
ai-crawler-radar bots --query openai
ai-crawler-radar bots --category AI_SEARCH

# Validate or generate CommonMark V2 /llms.txt
ai-crawler-radar llmstxt https://fastmcp.org
ai-crawler-radar llmstxt example.com --generate

# Output pure JSON for automated CI/CD pipelines
ai-crawler-radar probe https://example.com --json
```

---

## 🔬 Diagnostic Engine Architecture

1. **WAF Hard-Blocks**: Identifies Cloudflare (`CF-Ray`, Error 1020), AWS WAF, Akamai Ghost, and Imperva access blocks.
2. **Turnstile & Challenges**: Detects Cloudflare Turnstile widgets, managed JS puzzles, and interactive CAPTCHAs that halt crawlers.
3. **CSR Empty Shells**: Flags single-page apps (`<div id="root">`, `<div id="app">`) where dynamic JavaScript rendering leaves initial HTML blank for crawlers.
4. **Token Bloat Multiplier**: Computes ratio of raw DOM tokens to extracted readable content tokens (e.g. 35x bloat) to measure LLM ingestion efficiency.
5. **Content Negotiation & Cache Poisoning**: Detects missing `Vary: Accept` headers on markdown twin responses that cause CDN cache collisions.

---

## 🔒 Telemetry & Privacy

All network probing, token parsing, and analysis executes **locally on your machine**. 

To opt out of anonymous usage telemetry:
```bash
export DO_NOT_TRACK=1
# or
export AI_CRAWLER_RADAR_TELEMETRY=off
```

---

## 📄 License

MIT License. Free and open source forever for all developers and AI agents.
