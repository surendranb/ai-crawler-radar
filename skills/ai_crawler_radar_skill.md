---
name: ai-crawler-radar
description: Operational playbook for auditing and optimizing websites for AI search engines, training scrapers, and autonomous agents.
---

# AI Crawler Radar Operational Playbook

## 1. Executive Overview

Modern AI engines interact with web properties across three distinct operational tiers:

1. **Tier 1: Model Pre-Training Crawlers** (`GPTBot`, `ClaudeBot`, `Google-Extended`, `Meta-ExternalAgent`, `Bytespider`, `CCBot`)
   - High volume batch scrapers ingesting entire domains to train next-generation foundation models.
   - Typical business decision: Many publishers block this tier via `robots.txt` to protect proprietary intellectual property from uncompensated training.

2. **Tier 2: Real-Time AI Search Indexers** (`OAI-SearchBot`, `PerplexityBot`, `Claude-SearchBot`, `Applebot`, `Bingbot`)
   - Targeted crawlers refreshing indices for immediate search grounding (ChatGPT Search, Perplexity Search, Siri Intelligence).
   - Typical business decision: Publishers want this tier **allowed** to drive citations, referral traffic, and brand visibility in conversational search.

3. **Tier 3: Live User Fetchers** (`ChatGPT-User`, `Claude-User`, `Perplexity-User`)
   - Interactive retrieval triggered in real-time when an end-user pastes a link or asks an agent to browse a specific URL.
   - Typical business decision: Should be permitted unless the page is behind authentication.

---

## 2. The 5 Root-Cause Failure Modes

When an AI engine fails to cite or browse a page, it is rarely a model hallucination. It is almost always one of these 5 infrastructure flaws:

### Failure Mode 1: WAF Hard-Block (Cloudflare, AWS WAF, Akamai)
- **Symptom**: HTTP 403 Forbidden with `cf-ray`, `Error 1020`, or AWS WAF headers.
- **Root Cause**: Edge firewall has default bot-management rules active that block non-browser ASNs or synthetic User-Agents.
- **Remediation**: Create a WAF Custom Exception Rule allowing verified bots matching `OAI-SearchBot` or `PerplexityBot`.

### Failure Mode 2: Turnstile / JavaScript Soft-Challenge
- **Symptom**: HTTP 200 or 403 returning `<div class="cf-turnstile">` or Cloudflare challenge interstitial (`Just a moment...`).
- **Root Cause**: Turnstile or JS challenge intercepts requests before server content renders. AI bots do not execute interactive CAPTCHAs.
- **Remediation**: Exclude AI search user agents from interactive challenge actions.

### Failure Mode 3: CSR Empty Shell (`<div id="root">`)
- **Symptom**: Clean 200 OK response, but visible content length is < 150 characters, accompanied by heavy JavaScript script bundles.
- **Root Cause**: Pure Client-Side Rendering without Server-Side Rendering (SSR) or Static Site Generation (SSG). AI search bots cannot parse dynamic single-page applications efficiently.
- **Remediation**: Implement SSG/SSR or publish pre-rendered Markdown equivalents.

### Failure Mode 4: Severe Token Bloat Multiplier
- **Symptom**: 25,000 raw HTML tokens yielding only 600 tokens of substantive reading content (> 40x bloat).
- **Root Cause**: Massive inline SVG icons, inline JSON data blobs, mega-navigation headers, and nested un-semantic `<div>` wrappers.
- **Remediation**: Support content negotiation (`Accept: text/markdown`) or deploy `/llms.txt`.

### Failure Mode 5: Missing `Vary: Accept`
- **Symptom**: Content negotiation works locally, but production users intermittently receive cached HTML when requesting Markdown.
- **Root Cause**: Edge CDN caches do not vary cache keys on the `Accept` header.
- **Remediation**: Ensure upstream origin sends `Vary: Accept` whenever serving differentiated responses.

---

## 3. Recommended robots.txt Configuration

To allow AI search discovery while protecting proprietary data from foundation model training:

```txt
# Block AI model pre-training & data harvesting
User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: Meta-ExternalAgent
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: CCBot
Disallow: /

# Allow AI Search & Conversational Discovery
User-agent: OAI-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Claude-SearchBot
Allow: /

User-agent: Applebot
Allow: /

# Standard baseline
User-agent: *
Disallow: /admin/
Disallow: /private/

Sitemap: https://yourdomain.com/sitemap.xml
```
