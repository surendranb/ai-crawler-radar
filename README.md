# ⚡ ai-crawler-radar

[![CI](https://github.com/surendranb/ai-crawler-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/surendranb/ai-crawler-radar/actions)
[![PyPI version](https://img.shields.io/pypi/v/ai-crawler-radar.svg?style=flat-square&color=blue)](https://pypi.org/project/ai-crawler-radar/)
[![NPM version](https://img.shields.io/npm/v/ai-crawler-radar.svg?style=flat-square&color=green)](https://www.npmjs.com/package/ai-crawler-radar)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

> **Autonomous AI Search, Training & Agent Crawler Diagnostic Engine.**  
> Probes live web pages with authentic AI bot signatures, audits `robots.txt` across 3 tiers, identifies WAF hard-blocks & Turnstile challenges, calculates token bloat multipliers, and validates `/llms.txt`.

Available in **two architectural deployment variants** designed for maximum flexibility and privacy:
1. **Local MCP (stdio)**: Zero-auth, runs on your machine via `uvx` / `npx`, cold boot < 50ms.
2. **Remote MCP (Streamable HTTP / SSE)**: Hosted edge gateway (`https://crawler.builditwithai.xyz/mcp`) delivering continuous tool, schema, prompt, and playbook updates without needing PyPI/NPM package upgrades. Data never leaves your computer; zero cloud compute burden.

---

## ⚡ 1-Line Universal Installer

Automatically detects and configures all installed AI agent harnesses (Claude Desktop, Cursor, Claude Code, Antigravity, OpenCode, Zed, Windsurf):

```bash
curl -fsSL https://crawler.builditwithai.xyz/install | bash
```

---

## 🛠️ MCP Configuration: Choose Your Variant

### Variant A: Remote MCP (Streamable HTTP / SSE)
> **Recommended for instant edge updates**: Tools, schemas, prompts, and operational playbooks update dynamically at the edge without requiring package reinstallations or PyPI/NPM updates. Zero cloud compute burden; data never leaves your computer.

#### 🤖 Claude Desktop / Claude Code
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "ai-crawler-radar": {
      "url": "https://crawler.builditwithai.xyz/mcp"
    }
  }
}
```

#### 💻 Cursor / Windsurf / Antigravity
Add to your IDE MCP settings:
```json
{
  "mcpServers": {
    "ai-crawler-radar": {
      "url": "https://crawler.builditwithai.xyz/mcp"
    }
  }
}
```

#### 🌐 OpenCode
Add to `opencode.jsonc`:
```jsonc
{
  "mcp": {
    "ai-crawler-radar": {
      "type": "remote",
      "url": "https://crawler.builditwithai.xyz/mcp",
      "enabled": true
    }
  }
}
```

---

### Variant B: Local MCP (stdio)
> **Recommended for offline / air-gapped environments**: Runs natively on your machine via Python (`uvx`) or Node (`npx`). Zero dependencies, cold boot < 50ms.

#### 🤖 Claude Desktop / Claude Code
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

#### 💻 Cursor / Windsurf / Antigravity
Add to your IDE MCP settings:
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

#### 🌐 OpenCode
Add to `opencode.jsonc`:
```jsonc
{
  "mcp": {
    "ai-crawler-radar": {
      "type": "local",
      "command": ["uvx", "ai-crawler-radar"],
      "enabled": true
    }
  }
}
```

*(Node.js users can substitute `uvx ai-crawler-radar` with `npx -y ai-crawler-radar`)*

---

## 🧭 The 3-Tier AI Bot Model

`ai-crawler-radar` categorizes and evaluates crawler access across three distinct operational tiers:

| Tier | Primary Crawlers | Strategic Purpose | Typical Posture |
| :--- | :--- | :--- | :--- |
| **Tier 1: Model Pre-Training** | `GPTBot`, `ClaudeBot`, `Google-Extended`, `Meta-ExternalAgent`, `Bytespider`, `CCBot` | Bulk offline data harvesting to train foundation models | Block if protecting proprietary intellectual property |
| **Tier 2: AI Search Indexing** | `OAI-SearchBot`, `PerplexityBot`, `Claude-SearchBot`, `Applebot`, `Bingbot` | Real-time indexing to power SearchGPT, Perplexity & Siri citations | **Allow** to drive citations and conversational discovery |
| **Tier 3: Live User Fetchers** | `ChatGPT-User`, `Claude-User`, `Perplexity-User` | Real-time URL fetching triggered by an active human chat prompt | **Allow** for link previews and interactive agent assistance |

---

## 📡 Available Tools & Prompts

### Tools
| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `probe_url` | `url`, `tier`, `check_markdown_twin` | Probes URL using authentic headers across bot tiers; diagnoses WAF hard-blocks, Turnstile challenges, CSR empty shells, and token bloat multipliers. |
| `audit_robots` | `domain`, `categories` | RFC 9309 rules parser evaluating permissions across Training, Search, and Live Fetch tiers with strategic recommendations. |
| `compare_readiness` | `urls` | Multi-domain side-by-side benchmark comparing AI crawler readiness, token efficiency, and `/llms.txt` adoption. |
| `bot_directory` | `query`, `category` | Search and inspect 758 verified bots from Cloudflare Radar Bot Directory. |
| `generate_llms_txt` | `domain` | Validates existing `/llms.txt` against CommonMark V2 standard, or generates a compliant starter specification. |
| `skill_read` | `skill_name` | Read bundled operational playbooks dynamically. |
| `skills_list` | *(none)* | List available operational skills. |

### Dynamic Prompts (Remote Variant)
- `audit_domain_ai_posture`: Comprehensive 3-tier crawler readiness and robots.txt audit.
- `diagnose_crawler_block`: Root-cause investigation into WAF, Turnstile, or CSR blocks.
- `generate_llms_specification`: Automated generation of CommonMark V2 `/llms.txt` and `/llms-full.txt`.

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

Data never leaves your computer. In both local and remote variants, private target data is never stored on external servers.

To opt out of anonymous usage telemetry:
```bash
export DO_NOT_TRACK=1
# or
export AI_CRAWLER_RADAR_TELEMETRY=off
```

---

## 📄 License

MIT License. Free and open source forever for all developers and AI agents.
