/**
 * Cloudflare Worker Edge Gateway for ai-crawler-radar
 * Standard Fleet Architecture (Schema v2)
 *
 * Responsibilities:
 * 1. Streamable Remote HTTP MCP Endpoint (/mcp & JSON-RPC POST)
 * 2. Universal 1-Line Curl Installer (/install & curl detection)
 * 3. Edge Telemetry Relay (/e -> PostHog /capture/)
 * 4. Health Check (/health)
 */

const GATEWAY_VERSION = "2";
const SERVER_NAME = "ai-crawler-radar";
const PACKAGE_NAME = "ai-crawler-radar";
const CLI_CMD = "ai-crawler-radar";
const DISPLAY_NAME = "AI Crawler Radar";
const DESCRIPTION = "Autonomous AI Search, Training & Agent Crawler Diagnostic Engine";
const DOCS_URL = "https://github.com/surendranb/ai-crawler-radar#readme";
const RUNTIME_PREF = "uvx";
const DEFAULT_ENV = "{}";

const CORS_HEADERS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "content-type, authorization, x-requested-with",
};

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    const pathname = url.pathname.toLowerCase();
    const userAgent = request.headers.get("user-agent") || "";
    const clientIp = request.headers.get("cf-connecting-ip") || request.headers.get("x-real-ip") || "";
    const isCurl = userAgent.toLowerCase().includes("curl") || userAgent.toLowerCase().includes("wget");
    const dnt = request.headers.get("dnt") === "1" || request.headers.get("sec-gpc") === "1";

    const cf = request.cf || {};
    const country = cf.country || "unknown";
    const city = cf.city || "unknown";
    const continent = cf.continent || "unknown";
    const timezone = cf.timezone || "unknown";
    const asn = cf.asn || 0;
    const asOrganization = cf.asOrganization || "unknown";

    const meta = {
      clientIp,
      userAgent,
      country,
      city,
      continent,
      timezone,
      asn,
      asOrganization,
      dnt,
    };

    // Route 0: Health Check
    if (pathname === "/health") {
      return new Response(JSON.stringify({
        status: "ok",
        server: SERVER_NAME,
        gateway_version: GATEWAY_VERSION,
        timestamp: new Date().toISOString(),
      }), {
        headers: { ...CORS_HEADERS, "content-type": "application/json" },
      });
    }

    // Route 1: Telemetry Ingestion (Client MCP Server events via /e)
    if (request.method === "POST" && pathname === "/e") {
      if (dnt) {
        return new Response(JSON.stringify({ recorded: false, reason: "dnt" }), {
          headers: { ...CORS_HEADERS, "content-type": "application/json" },
        });
      }

      let body;
      try {
        body = await request.json();
      } catch (e) {
        return new Response(JSON.stringify({ recorded: false, reason: "invalid_json" }), {
          status: 400,
          headers: { ...CORS_HEADERS, "content-type": "application/json" },
        });
      }

      const eventName = typeof body.event === "string" && body.event ? body.event.slice(0, 200) : "malformed_event";
      let props = (body.properties && typeof body.properties === "object") ? body.properties : {};

      if (clientIp) props.$ip = clientIp;
      props.as_organization = asOrganization;
      props.asn = asn;
      props.cf_country = country;
      props.cf_timezone = timezone;
      props.via_gateway = true;
      props.gateway_version = GATEWAY_VERSION;
      props.mcp_server_name = SERVER_NAME;

      ctx.waitUntil(sendPostHogEvent(env, {
        event: eventName,
        distinct_id: String(body.distinct_id || `anon_${crypto.randomUUID()}`).slice(0, 200),
        properties: props,
      }));

      return new Response(JSON.stringify({ recorded: true }), {
        headers: { ...CORS_HEADERS, "content-type": "application/json" },
      });
    }

    // Route 2: Post-Install Completion Ping (/telemetry)
    if (request.method === "POST" && pathname === "/telemetry") {
      try {
        const body = await request.json();
        if (!dnt) {
          ctx.waitUntil(
            sendPostHogEvent(env, {
              event: "install_completed",
              distinct_id: body.anonymous_id || `anon_${crypto.randomUUID()}`,
              properties: {
                $ip: clientIp || null,
                as_organization: asOrganization,
                asn: asn,
                cf_country: country,
                cf_timezone: timezone,
                via_gateway: true,
                gateway_version: GATEWAY_VERSION,
                mcp_server_name: SERVER_NAME,
                ...body,
              },
            })
          );
        }
        return new Response(JSON.stringify({ recorded: true }), {
          headers: { ...CORS_HEADERS, "content-type": "application/json" },
        });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), { status: 400 });
      }
    }

    // Route 3: Streamable Remote HTTP MCP Endpoint (/mcp or POST /)
    if (request.method === "POST" && (pathname === "/mcp" || (pathname === "/" && request.headers.get("content-type")?.includes("json")))) {
      return await handleMCPJsonRpc(request, env, ctx, meta);
    }

    // Route 4: Install Script Serving (curl -fsSL https://<host>/install | bash)
    const isInstallerRequest = isCurl || pathname === "/install" || pathname === "/install.sh" || (pathname === "/" && isCurl);
    if (isInstallerRequest) {
      if (!dnt) {
        ctx.waitUntil(
          sendPostHogEvent(env, {
            event: "install_intent",
            distinct_id: `anon_${crypto.randomUUID()}`,
            properties: {
              $ip: clientIp || null,
              via_gateway: true,
              gateway_version: GATEWAY_VERSION,
              mcp_server_name: SERVER_NAME,
              user_agent: userAgent,
              cf_country: country,
              cf_city: city,
              as_organization: asOrganization,
              asn: asn,
            },
          })
        );
      }
      return new Response(getInstallerScript(url.hostname, SERVER_NAME, PACKAGE_NAME, CLI_CMD, DISPLAY_NAME, DESCRIPTION, DOCS_URL, RUNTIME_PREF, DEFAULT_ENV), {
        headers: {
          ...CORS_HEADERS,
          "content-type": "text/plain; charset=utf-8",
          "cache-control": "no-cache",
        },
      });
    }

    // Default: Redirect browser to documentation / GitHub
    return Response.redirect(env.DOCS_URL || "https://github.com/surendranb/ai-crawler-radar#readme", 302);
  },
};

async function handleMCPJsonRpc(request, env, ctx, meta) {
  let body;
  try {
    body = await request.json();
  } catch (e) {
    return new Response(JSON.stringify({
      jsonrpc: "2.0",
      id: null,
      error: { code: -32700, message: "Parse error: Invalid JSON" },
    }), { status: 400, headers: { ...CORS_HEADERS, "content-type": "application/json" } });
  }

  const id = body.id !== undefined ? body.id : null;
  const method = body.method;
  const params = body.params || {};

  switch (method) {
    case "initialize": {
      return new Response(JSON.stringify({
        jsonrpc: "2.0",
        id,
        result: {
          protocolVersion: "2024-11-05",
          serverInfo: {
            name: SERVER_NAME,
            version: "0.1.0",
          },
          capabilities: {
            tools: { listChanged: false },
            prompts: { listChanged: false },
            resources: { listChanged: false },
          },
          instructions: DESCRIPTION,
        },
      }), { headers: { ...CORS_HEADERS, "content-type": "application/json" } });
    }

    case "tools/list": {
      return new Response(JSON.stringify({
        jsonrpc: "2.0",
        id,
        result: {
          tools: [
            {
              name: "probe_url",
              description: "Probe a URL with authentic AI bot headers to diagnose WAF hard-blocks, Turnstile challenges, CSR empty shells, and token bloat multipliers.",
              inputSchema: {
                type: "object",
                properties: {
                  url: { type: "string", description: "Target URL to inspect" },
                  tier: { type: "string", description: "Bot tier: 'all', 'training', 'search', or 'live_fetch'", default: "all" },
                  check_markdown_twin: { type: "boolean", description: "Test content negotiation and /llms.txt", default: true },
                },
                required: ["url"],
              },
            },
            {
              name: "audit_robots",
              description: "Fetch and audit a domain's robots.txt across Training, Search, and Live Fetch AI bot tiers with strategic guidance.",
              inputSchema: {
                type: "object",
                properties: {
                  domain: { type: "string", description: "Domain to audit (e.g. 'stripe.com')" },
                  categories: { type: "string", description: "Tier filter: 'all', 'training', 'search', 'live_fetch'", default: "all" },
                },
                required: ["domain"],
              },
            },
            {
              name: "compare_readiness",
              description: "Compare AI crawler readiness and token bloat across multiple domains side-by-side.",
              inputSchema: {
                type: "object",
                properties: {
                  urls: { type: "array", items: { type: "string" }, description: "List of URLs to benchmark" },
                },
                required: ["urls"],
              },
            },
            {
              name: "bot_directory",
              description: "Search 758 verified bots from Cloudflare Radar Bot Directory.",
              inputSchema: {
                type: "object",
                properties: {
                  query: { type: "string", description: "Search query", default: "" },
                  category: { type: "string", description: "Category filter (e.g. 'AI_CRAWLER', 'AI_SEARCH')", default: "all" },
                },
              },
            },
            {
              name: "generate_llms_txt",
              description: "Validate existing /llms.txt or generate a compliant CommonMark V2 template.",
              inputSchema: {
                type: "object",
                properties: {
                  domain: { type: "string", description: "Target domain" },
                },
                required: ["domain"],
              },
            },
            {
              name: "skills_list",
              description: "List operational skills and playbooks available in ai-crawler-radar.",
              inputSchema: { type: "object", properties: {} },
            },
            {
              name: "skill_read",
              description: "Read an operational skill playbook.",
              inputSchema: {
                type: "object",
                properties: {
                  skill_name: { type: "string", default: "ai_crawler_radar_skill" },
                },
              },
            },
          ],
        },
      }), { headers: { ...CORS_HEADERS, "content-type": "application/json" } });
    }

    case "tools/call": {
      const toolName = params.name;
      const toolArgs = params.arguments || {};

      if (toolName === "skills_list") {
        return new Response(JSON.stringify({
          jsonrpc: "2.0",
          id,
          result: {
            content: [{ type: "text", text: "Available skills: ai_crawler_radar_skill" }],
          },
        }), { headers: { ...CORS_HEADERS, "content-type": "application/json" } });
      }

      if (toolName === "generate_llms_txt") {
        const domain = (toolArgs.domain || "example.com").replace(/^https?:\/\//, "");
        const starter = `# ${domain}\n\n> AI documentation index for ${domain}\n\n## Documentation\n\n- [Overview](https://${domain}/docs/overview): Platform architecture\n- [Quickstart](https://${domain}/docs/quickstart): Developer setup\n`;
        return new Response(JSON.stringify({
          jsonrpc: "2.0",
          id,
          result: {
            content: [{ type: "text", text: starter }],
          },
        }), { headers: { ...CORS_HEADERS, "content-type": "application/json" } });
      }

      // Probing is executed locally via stdio / CLI for user privacy and direct origin reachability
      return new Response(JSON.stringify({
        jsonrpc: "2.0",
        id,
        result: {
          content: [{
            type: "text",
            text: `[LOCAL_FIRST_DIRECTIVE] To preserve client IP privacy and prevent bot-detection blocking against cloud proxies, run tool '${toolName}' natively via local CLI:\n\n\`\`\`bash\nuvx ai-crawler-radar ${toolName === "probe_url" ? "probe " + (toolArgs.url || "") : toolName === "audit_robots" ? "audit " + (toolArgs.domain || "") : toolName}\n\`\`\``
          }],
        },
      }), { headers: { ...CORS_HEADERS, "content-type": "application/json" } });
    }

    case "prompts/list":
    case "resources/list":
      return new Response(JSON.stringify({
        jsonrpc: "2.0",
        id,
        result: { prompts: [], resources: [] },
      }), { headers: { ...CORS_HEADERS, "content-type": "application/json" } });

    default:
      return new Response(JSON.stringify({
        jsonrpc: "2.0",
        id,
        error: { code: -32601, message: `Method not found: ${method}` },
      }), { status: 404, headers: { ...CORS_HEADERS, "content-type": "application/json" } });
  }
}

async function sendPostHogEvent(env, payload) {
  try {
    const posthogHost = env.POSTHOG_HOST || "https://us.i.posthog.com";
    await fetch(`${posthogHost}/capture/`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        api_key: env.POSTHOG_API_KEY,
        event: payload.event,
        distinct_id: payload.distinct_id,
        properties: payload.properties,
        timestamp: new Date().toISOString(),
      }),
    });
  } catch (err) {
    // Fail silently
  }
}

function getInstallerScript(hostname, serverName, packageName, cliCmd, displayName, description, docsUrl, runtimePref, defaultEnv) {
  const host = hostname || "crawler.builditwithai.xyz";
  return `#!/usr/bin/env bash
# ==============================================================================
# Universal AI Model Context Protocol (MCP) Installer: ${displayName}
# Supports: Claude Desktop, Cursor, Claude Code, Antigravity, OpenCode, VS Code, Zed
# ==============================================================================
MCP_SERVER_NAME="${serverName}"
MCP_PACKAGE_NAME="${packageName}"
MCP_CLI_CMD="${cliCmd}"
MCP_DISPLAY_NAME="${displayName}"
GATEWAY_HOST="${host}"

set -e

echo "⚡ Installing \${MCP_DISPLAY_NAME} into AI agent harnesses..."

HAS_UVX=false
HAS_NPX=false
if command -v uvx &>/dev/null; then HAS_UVX=true; fi
if command -v npx &>/dev/null; then HAS_NPX=true; fi

CHOSEN_COMMAND="uvx"
CHOSEN_ARGS='["\${MCP_PACKAGE_NAME}"]'

if [ "$HAS_UVX" = false ] && [ "$HAS_NPX" = true ]; then
  CHOSEN_COMMAND="npx"
  CHOSEN_ARGS='["-y", "@surendranb/\${MCP_PACKAGE_NAME}"]'
fi

CONFIG_TARGETS=(
  "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
  "$HOME/.config/Claude/claude_desktop_config.json"
  "$HOME/.cursor/mcp.json"
  "$HOME/.claude.json"
  "$HOME/.gemini/antigravity/mcp_servers.json"
  "$HOME/.config/opencode/opencode.jsonc"
)

for target in "\${CONFIG_TARGETS[@]}"; do
  parent_dir="\$(dirname "$target")"
  if [ -d "$parent_dir" ]; then
    echo "• Configuring: $target"
    python3 -c "
import json, os, sys
p = os.path.expanduser('$target')
os.makedirs(os.path.dirname(p), exist_ok=True)
data = {}
if os.path.exists(p):
    try:
        with open(p, 'r') as f: data = json.load(f)
    except: pass
if 'mcpServers' not in data: data['mcpServers'] = {}
data['mcpServers']['$serverName'] = {
    'command': '$CHOSEN_COMMAND',
    'args': json.loads('''$CHOSEN_ARGS''')
}
with open(p, 'w') as f:
    json.dump(data, f, indent=2)
print('  [OK] Installed $serverName')
" 2>/dev/null || true
  fi
done

echo ""
echo "🎉 Setup complete! Restart your agent harness to use \${MCP_DISPLAY_NAME}."
`;
}
