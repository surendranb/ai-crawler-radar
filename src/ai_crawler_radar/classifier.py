# SPDX-License-Identifier: MIT
"""Root-cause diagnostic classifier for AI crawler readiness."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple


class TextExtractor(HTMLParser):
    """Fast, zero-dependency HTML to structured markdown/text converter."""

    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self._ignore_tags = {
            "script", "style", "svg", "noscript", "head", "iframe",
            "canvas", "nav", "footer"
        }
        self._current_tag_stack: List[str] = []
        self._pieces: List[str] = []
        self._in_link = False
        self._link_href = ""
        self._link_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        self._current_tag_stack.append(t)
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(t[1])
            self._pieces.append(f"\n\n{'#' * level} ")
        elif t in ("p", "div", "section", "article"):
            self._pieces.append("\n\n")
        elif t == "br":
            self._pieces.append("\n")
        elif t == "li":
            self._pieces.append("\n- ")
        elif t == "a":
            href = attr_dict.get("href", "")
            if href and not href.startswith(("#", "javascript:", "mailto:")):
                self._in_link = True
                self._link_href = href
                self._link_text = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if self._current_tag_stack and self._current_tag_stack[-1] == t:
            self._current_tag_stack.pop()
        elif t in self._current_tag_stack:
            self._current_tag_stack.remove(t)

        if t == "a" and self._in_link:
            text = "".join(self._link_text).strip()
            if text:
                self._pieces.append(f"[{text}]({self._link_href})")
            elif self._link_href:
                self._pieces.append(self._link_href)
            self._in_link = False
            self._link_href = ""
            self._link_text = []
        elif t in ("p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if any(ignored in self._current_tag_stack for ignored in self._ignore_tags):
            return
        if self._in_link:
            self._link_text.append(data)
        else:
            self._pieces.append(data)

    def get_text(self) -> str:
        raw = "".join(self._pieces)
        lines = [line.strip() for line in raw.splitlines()]
        cleaned = []
        consecutive_blank = 0
        for line in lines:
            if not line:
                consecutive_blank += 1
                if consecutive_blank <= 1:
                    cleaned.append("")
            else:
                consecutive_blank = 0
                cleaned.append(line)
        return "\n".join(cleaned).strip()


def extract_markdown_from_html(html_content: str) -> str:
    """Extract clean markdown-like text from raw HTML using standard library parser."""
    if not html_content:
        return ""
    try:
        extractor = TextExtractor()
        extractor.feed(html_content)
        return extractor.get_text()
    except Exception:
        # Fallback to regex tag stripping
        clean = re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", " ", clean)
        return " ".join(clean.split())


def calculate_token_bloat(raw_html: str, extracted_markdown: Optional[str] = None) -> Dict[str, Any]:
    """Calculates the token bloat multiplier between raw HTML and extracted readable content."""
    if extracted_markdown is None:
        extracted_markdown = extract_markdown_from_html(raw_html)

    # Standard BPE token approximation: ~4 characters per token
    raw_chars = len(raw_html)
    raw_tokens = max(1, raw_chars // 4)

    content_chars = len(extracted_markdown)
    content_tokens = max(1, content_chars // 4)

    bloat_multiplier = round(raw_tokens / content_tokens, 2)

    if bloat_multiplier >= 10.0:
        severity = "CRITICAL"
        description = (
            f"Severe token bloat ({bloat_multiplier}x): {raw_tokens:,} raw HTML tokens "
            f"compress down to {content_tokens:,} content tokens. AI crawlers burn {round((1 - 1/bloat_multiplier)*100, 1)}% "
            f"of context window on DOM boilerplate."
        )
    elif bloat_multiplier >= 4.0:
        severity = "WARNING"
        description = (
            f"Moderate token bloat ({bloat_multiplier}x): {raw_tokens:,} raw HTML tokens "
            f"vs {content_tokens:,} content tokens."
        )
    else:
        severity = "INFO"
        description = (
            f"Optimal content density ({bloat_multiplier}x): {raw_tokens:,} HTML tokens "
            f"vs {content_tokens:,} content tokens."
        )

    return {
        "raw_chars": raw_chars,
        "raw_tokens": raw_tokens,
        "content_chars": content_chars,
        "content_tokens": content_tokens,
        "bloat_multiplier": bloat_multiplier,
        "severity": severity,
        "description": description,
    }


def detect_waf_block(
    status_code: int,
    headers: Dict[str, str],
    body_text: str,
) -> Dict[str, Any]:
    """Detects WAF hard-blocks (Cloudflare, AWS WAF, Akamai, Imperva, etc.)."""
    headers_lower = {k.lower(): v.lower() for k, v in headers.items()}
    body_lower = body_text.lower()

    is_blocked = False
    vendor = None
    error_code = None
    details = ""

    # Cloudflare hard blocks
    cf_ray = headers_lower.get("cf-ray", "")
    server = headers_lower.get("server", "")

    if "cf-error-code" in body_lower or "error 1020" in body_lower or "1020: access denied" in body_lower:
        is_blocked = True
        vendor = "Cloudflare"
        error_code = "1020"
        details = "Cloudflare WAF Error 1020: Access Denied. Firewall rule explicitly blocks this user agent or ASN."
    elif "error 1015" in body_lower or "rate limited" in body_lower and "cloudflare" in body_lower:
        is_blocked = True
        vendor = "Cloudflare"
        error_code = "1015"
        details = "Cloudflare WAF Error 1015: Rate limited by edge firewall."
    elif status_code in (403, 503) and cf_ray and ("cloudflare" in server or "attention required! | cloudflare" in body_lower):
        is_blocked = True
        vendor = "Cloudflare"
        match = re.search(r"error\s*code\s*[:\s]*(\d+)", body_lower)
        if match:
            error_code = match.group(1)
        details = f"Cloudflare Edge Hard-Block (Status {status_code}, CF-Ray: {cf_ray})."

    # AWS WAF
    elif "x-amzn-waf-action" in headers_lower or "aws waf" in body_lower and status_code in (403, 405):
        is_blocked = True
        vendor = "AWS WAF"
        action = headers_lower.get("x-amzn-waf-action", "BLOCK")
        details = f"AWS WAF blocked request (Action: {action}, Status: {status_code})."

    # Akamai WAF
    elif status_code == 403 and ("reference #" in body_lower or "akamai" in server or "x-akamai-transformed" in headers_lower):
        is_blocked = True
        vendor = "Akamai"
        ref_match = re.search(r"reference\s*#\s*([0-9a-f.]+)", body_lower)
        if ref_match:
            error_code = ref_match.group(1)
        details = f"Akamai Ghost WAF blocked request (Status 403{f', Ref: {error_code}' if error_code else ''})."

    # Imperva / Incapsula
    elif "_incapsula_resource" in body_lower or "incapsula incident id" in body_lower:
        is_blocked = True
        vendor = "Imperva Incapsula"
        details = "Imperva / Incapsula bot mitigation blocked request."

    # DataDome
    elif "datadome" in headers_lower.get("x-datadome-response", "") or "datadome.co" in body_lower:
        is_blocked = True
        vendor = "DataDome"
        details = "DataDome bot protection blocked request."

    # Generic HTTP 403/401/406 with generic block
    elif status_code in (403, 406):
        is_blocked = True
        vendor = "Generic WAF / Gateway"
        details = f"HTTP {status_code} Forbidden: Access blocked by server or security gateway."

    return {
        "is_waf_blocked": is_blocked,
        "vendor": vendor,
        "error_code": error_code,
        "details": details,
    }


def detect_turnstile_and_challenges(
    status_code: int,
    headers: Dict[str, str],
    body_text: str,
) -> Dict[str, Any]:
    """Detects Cloudflare Turnstile soft-challenges, JS puzzles, and CAPTCHAs."""
    body_lower = body_text.lower()
    headers_lower = {k.lower(): v.lower() for k, v in headers.items()}

    is_challenge = False
    challenge_type = None
    details = ""

    # Cloudflare Turnstile
    if (
        "challenges.cloudflare.com/turnstile" in body_lower
        or "cf-turnstile" in body_lower
        or 'class="cf-turnstile"' in body_lower
    ):
        is_challenge = True
        challenge_type = "Cloudflare Turnstile"
        details = "Cloudflare Turnstile CAPTCHA widget detected. AI crawlers cannot execute Turnstile challenges and will fail to proceed."

    # Cloudflare JavaScript challenge
    elif (
        "cf-chl-widget" in body_lower
        or "cf_chl_opt" in body_lower
        or "cf-browser-verification" in body_lower
        or ("just a moment..." in body_lower and ("cloudflare" in body_lower or headers_lower.get("cf-ray")))
        or ("verify you are human" in body_lower and headers_lower.get("cf-ray"))
    ):
        is_challenge = True
        challenge_type = "Cloudflare JS Challenge"
        details = "Cloudflare Managed/Interactive JS Challenge detected. Standard HTTP crawler cannot solve the client challenge."

    # hCaptcha
    elif "hcaptcha.com" in body_lower or 'class="h-captcha"' in body_lower:
        is_challenge = True
        challenge_type = "hCaptcha"
        details = "hCaptcha interactive challenge detected."

    # Google reCAPTCHA
    elif "recaptcha/api.js" in body_lower or 'class="g-recaptcha"' in body_lower:
        is_challenge = True
        challenge_type = "Google reCAPTCHA"
        details = "Google reCAPTCHA verification challenge detected."

    return {
        "is_challenge": is_challenge,
        "challenge_type": challenge_type,
        "details": details,
    }


def detect_csr_empty_shell(
    status_code: int,
    body_text: str,
) -> Dict[str, Any]:
    """Detects Client-Side Rendered (CSR) empty HTML shells (<div id="root">)."""
    if status_code != 200 or not body_text:
        return {"is_csr_shell": False, "framework_hint": None, "visible_chars": 0, "details": ""}

    body_lower = body_text.lower()

    # Common SPA mounting containers
    spa_mounts = [
        ('<div id="root">', "React"),
        ('<div id="app">', "Vue / SPA"),
        ('<div id="__next">', "Next.js (Unrendered CSR)"),
        ('<div id="__nuxt">', "Nuxt (Unrendered CSR)"),
        ('<app-root>', "Angular"),
        ('<div id="mount">', "SPA"),
    ]

    matched_mount = None
    framework = None
    for mount_tag, fw in spa_mounts:
        if mount_tag in body_lower:
            matched_mount = mount_tag
            framework = fw
            break

    # Extract visible text length
    visible_text = extract_markdown_from_html(body_text)
    visible_chars = len(visible_text)

    # Detect scripts
    has_script_tags = "<script" in body_lower
    has_js_bundles = bool(re.search(r'\b(chunk|bundle|main|app)\.[a-z0-9]+\.js\b', body_lower))

    is_csr = False
    details = ""

    if matched_mount:
        # Check if the shell is empty or near-empty (< 200 characters of readable content)
        if visible_chars < 200 and has_script_tags:
            is_csr = True
            details = (
                f"Client-Side Rendering (CSR) empty shell detected ({framework} mounting container '{matched_mount}'). "
                f"Page payload contains only {visible_chars} visible text characters with JS bundles. "
                f"AI crawlers that do not execute headless JavaScript will index an empty page."
            )
    elif "you need to enable javascript to run this app" in body_lower and visible_chars < 150:
        is_csr = True
        framework = "SPA Shell"
        details = (
            "Static HTML fallback warning detected ('You need to enable JavaScript to run this app'). "
            "No pre-rendered HTML content is available for search or crawler agents."
        )

    return {
        "is_csr_shell": is_csr,
        "framework_hint": framework if is_csr else None,
        "visible_chars": visible_chars,
        "details": details,
    }


def detect_content_negotiation_issues(
    status_code: int,
    headers: Dict[str, str],
    requested_accept: str = "text/markdown",
    returned_body: str = "",
) -> Dict[str, Any]:
    """Detects missing Vary: Accept and content negotiation failures."""
    headers_lower = {k.lower(): v for k, v in headers.items()}
    content_type = headers_lower.get("content-type", "").lower()
    vary_header = headers_lower.get("vary", "").lower()

    is_negotiation_supported = (
        "text/markdown" in content_type
        or "text/x-markdown" in content_type
        or "text/plain" in content_type
    )

    vary_tokens = [t.strip() for t in vary_header.split(",") if t.strip()]
    has_vary_accept = "accept" in vary_tokens or "*" in vary_tokens

    issues: List[str] = []

    # If the server returned markdown, it MUST include Vary: Accept to avoid CDN poisoning
    missing_vary_accept = False
    if is_negotiation_supported and not has_vary_accept:
        missing_vary_accept = True
        issues.append(
            "Missing 'Vary: Accept' header on negotiated markdown response. "
            "CDN/edge caches (Cloudflare, Fastly) may cache markdown for browsers or HTML for AI crawlers."
        )

    # If markdown was requested but server returned HTML without error
    markdown_rejected = False
    if "text/markdown" in requested_accept.lower() and status_code == 200 and "text/html" in content_type:
        markdown_rejected = True
        issues.append(
            "Content negotiation ignored: 'Accept: text/markdown' was sent, but server returned 'text/html'. "
            "No native markdown twin served via content negotiation."
        )

    return {
        "content_type": content_type,
        "vary_header": vary_header,
        "is_negotiation_supported": is_negotiation_supported,
        "has_vary_accept": has_vary_accept,
        "missing_vary_accept": missing_vary_accept,
        "markdown_rejected": markdown_rejected,
        "issues": issues,
    }


def classify_response(
    status_code: int,
    headers: Dict[str, str],
    body_text: str,
    requested_accept: str = "text/html",
) -> Dict[str, Any]:
    """Complete root-cause classification of an HTTP response for an AI crawler."""
    waf = detect_waf_block(status_code, headers, body_text)
    turnstile = detect_turnstile_and_challenges(status_code, headers, body_text)
    csr = detect_csr_empty_shell(status_code, body_text)
    bloat = calculate_token_bloat(body_text)
    cneg = detect_content_negotiation_issues(status_code, headers, requested_accept, body_text)

    # Determine overall status
    if waf["is_waf_blocked"]:
        status = "BLOCKED"
        primary_issue = waf["details"]
    elif turnstile["is_challenge"]:
        status = "CHALLENGED"
        primary_issue = turnstile["details"]
    elif status_code >= 400:
        status = "ERROR"
        primary_issue = f"HTTP {status_code} Error."
    elif csr["is_csr_shell"]:
        status = "DEGRADED"
        primary_issue = csr["details"]
    elif bloat["severity"] == "CRITICAL":
        status = "BLOATED"
        primary_issue = bloat["description"]
    else:
        status = "ALLOWED"
        primary_issue = "Crawler successfully retrieved readable content."

    diagnoses = []
    if waf["is_waf_blocked"]:
        diagnoses.append({
            "code": "WAF_HARD_BLOCK",
            "severity": "CRITICAL",
            "message": waf["details"],
            "remediation": f"Whitelist the crawler's User-Agent or IP ranges in {waf['vendor'] or 'WAF'} firewall rules.",
        })
    if turnstile["is_challenge"]:
        diagnoses.append({
            "code": "TURNSTILE_SOFT_CHALLENGE",
            "severity": "CRITICAL",
            "message": turnstile["details"],
            "remediation": "Create a WAF Custom Rule bypassing Turnstile/Managed Challenges for verified AI crawlers.",
        })
    if csr["is_csr_shell"]:
        diagnoses.append({
            "code": "CSR_EMPTY_SHELL",
            "severity": "WARNING",
            "message": csr["details"],
            "remediation": "Enable Server-Side Rendering (SSR), Static Site Generation (SSG), or serve pre-rendered markdown twin.",
        })
    if bloat["severity"] in ("CRITICAL", "WARNING"):
        diagnoses.append({
            "code": "TOKEN_BLOAT",
            "severity": bloat["severity"],
            "message": bloat["description"],
            "remediation": "Provide clean semantic HTML, support 'Accept: text/markdown', or publish a '/llms.txt' file.",
        })
    if cneg["missing_vary_accept"]:
        diagnoses.append({
            "code": "MISSING_VARY_ACCEPT",
            "severity": "WARNING",
            "message": "Missing 'Vary: Accept' header when serving content-negotiated responses.",
            "remediation": "Add 'Vary: Accept' to edge cache response headers to prevent CDN cache collisions.",
        })

    return {
        "status": status,
        "primary_issue": primary_issue,
        "status_code": status_code,
        "waf": waf,
        "turnstile": turnstile,
        "csr": csr,
        "token_bloat": bloat,
        "content_negotiation": cneg,
        "diagnoses": diagnoses,
    }
