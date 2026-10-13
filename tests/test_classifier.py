# SPDX-License-Identifier: MIT
"""Unit tests for root-cause diagnostic classifier."""

import pytest
from ai_crawler_radar.classifier import (
    detect_waf_block,
    detect_turnstile_and_challenges,
    detect_csr_empty_shell,
    calculate_token_bloat,
    detect_content_negotiation_issues,
    classify_response,
)


def test_waf_hard_block_cloudflare_1020():
    """Verify detection of Cloudflare WAF Error 1020."""
    headers = {"cf-ray": "8e1234567-BOM", "server": "cloudflare"}
    body = "<html><body>Error 1020: Access denied. Cloudflare Ray ID: 8e1234567</body></html>"
    res = detect_waf_block(403, headers, body)
    assert res["is_waf_blocked"] is True
    assert res["vendor"] == "Cloudflare"
    assert res["error_code"] == "1020"


def test_waf_hard_block_aws():
    """Verify detection of AWS WAF blocks."""
    headers = {"x-amzn-waf-action": "BLOCK"}
    body = "<html><body>403 Forbidden: Request blocked by AWS WAF</body></html>"
    res = detect_waf_block(403, headers, body)
    assert res["is_waf_blocked"] is True
    assert res["vendor"] == "AWS WAF"


def test_waf_hard_block_akamai():
    """Verify detection of Akamai Ghost WAF blocks."""
    headers = {"server": "AkamaiGHost"}
    body = "<html><body>Access Denied. Reference #18.123456.789</body></html>"
    res = detect_waf_block(403, headers, body)
    assert res["is_waf_blocked"] is True
    assert res["vendor"] == "Akamai"
    assert res["error_code"] == "18.123456.789"


def test_turnstile_widget_detection():
    """Verify detection of Cloudflare Turnstile widget."""
    headers = {"content-type": "text/html"}
    body = """
    <html>
      <head><script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script></head>
      <body><div class="cf-turnstile" data-sitekey="0x4AAAAAA"></div></body>
    </html>
    """
    res = detect_turnstile_and_challenges(200, headers, body)
    assert res["is_challenge"] is True
    assert res["challenge_type"] == "Cloudflare Turnstile"


def test_turnstile_js_challenge_detection():
    """Verify detection of Cloudflare managed JS challenge interstitial."""
    headers = {"cf-ray": "8e1234567-BOM"}
    body = "<html><title>Just a moment...</title><body>Checking your browser before accessing. Verify you are human.</body></html>"
    res = detect_turnstile_and_challenges(403, headers, body)
    assert res["is_challenge"] is True
    assert res["challenge_type"] == "Cloudflare JS Challenge"


def test_csr_empty_shell_detection():
    """Verify detection of empty Client-Side Rendered (CSR) app shells."""
    body = """
    <!DOCTYPE html>
    <html>
      <head><title>App</title></head>
      <body>
        <div id="root"></div>
        <script src="/static/js/main.1a2b3c.js"></script>
        <script src="/static/js/chunk.4d5e6f.js"></script>
      </body>
    </html>
    """
    res = detect_csr_empty_shell(200, body)
    assert res["is_csr_shell"] is True
    assert res["framework_hint"] == "React"
    assert res["visible_chars"] < 50


def test_csr_not_flagged_on_ssg_or_ssr():
    """Verify that pages with substantive pre-rendered content are not falsely flagged as CSR shells."""
    body = """
    <!DOCTYPE html>
    <html>
      <head><title>Documentation</title></head>
      <body>
        <div id="root">
          <h1>Product Overview</h1>
          <p>Our platform enables autonomous AI agents to interact with secure data lakes in real time. We provide deep telemetry, robust error boundaries, and streaming RPC endpoints.</p>
          <p>Read on to explore installation guides, code samples, and architectural blueprints for production deployment.</p>
        </div>
        <script src="/bundle.js"></script>
      </body>
    </html>
    """
    res = detect_csr_empty_shell(200, body)
    assert res["is_csr_shell"] is False


def test_token_bloat_calculation():
    """Verify token bloat multiplier and severity thresholds."""
    # Build bloated HTML with huge DOM boilerplate around minimal text
    boilerplate = '<div class="wrapper"><span class="icon">' + '<svg><path d="M0 0"/></svg>' * 300 + '</span></div>'
    content = '<h1>Welcome</h1><p>This is substantive content.</p>'
    bloated_html = f"<html><body>{boilerplate}{content}</body></html>"

    bloat = calculate_token_bloat(bloated_html)
    assert bloat["bloat_multiplier"] >= 5.0
    assert bloat["raw_tokens"] > bloat["content_tokens"]
    assert bloat["severity"] in ("CRITICAL", "WARNING")


def test_missing_vary_accept_detection():
    """Verify detection of missing 'Vary: Accept' header when serving content-negotiated responses."""
    # Serving markdown without Vary: Accept -> cache collision danger
    res = detect_content_negotiation_issues(
        status_code=200,
        headers={"content-type": "text/markdown", "server": "cloudflare"},
        requested_accept="text/markdown",
    )
    assert res["is_negotiation_supported"] is True
    assert res["missing_vary_accept"] is True
    assert any("Missing 'Vary: Accept'" in issue for issue in res["issues"])

    # Serving markdown WITH Vary: Accept -> correct
    res_correct = detect_content_negotiation_issues(
        status_code=200,
        headers={"content-type": "text/markdown", "vary": "Accept, User-Agent"},
        requested_accept="text/markdown",
    )
    assert res_correct["is_negotiation_supported"] is True
    assert res_correct["missing_vary_accept"] is False


def test_classify_response_full_report():
    """Verify end-to-end classification returns structured diagnoses."""
    headers = {"cf-ray": "890-BOM", "server": "cloudflare"}
    body = "<html><body>Error 1020: Access denied by Cloudflare</body></html>"
    full_report = classify_response(403, headers, body)

    assert full_report["status"] == "BLOCKED"
    assert len(full_report["diagnoses"]) >= 1
    d = full_report["diagnoses"][0]
    assert d["code"] == "WAF_HARD_BLOCK"
    assert d["severity"] == "CRITICAL"
    assert "Cloudflare" in d["message"]
