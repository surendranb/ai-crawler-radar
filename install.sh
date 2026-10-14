#!/usr/bin/env bash
# ==============================================================================
# Universal AI Model Context Protocol (MCP) Installer: AI Crawler Radar
# Supports: Claude Desktop, Cursor, Claude Code, Antigravity, OpenCode, VS Code, Zed
# ==============================================================================
MCP_SERVER_NAME="ai-crawler-radar"
MCP_PACKAGE_NAME="ai-crawler-radar"
MCP_DISPLAY_NAME="AI Crawler Radar"
GATEWAY_HOST="crawler.builditwithai.xyz"

set -e

# Terminal styling
if [ -t 1 ] && [ "${TERM:-}" != "dumb" ]; then
  BOLD='\033[1m'
  GREEN='\033[0;32m'
  BLUE='\033[0;34m'
  CYAN='\033[0;36m'
  YELLOW='\033[1;33m'
  RED='\033[0;31m'
  NC='\033[0m'
else
  BOLD=''
  GREEN=''
  BLUE=''
  CYAN=''
  YELLOW=''
  RED=''
  NC=''
fi

echo -e "${BLUE}${BOLD}┌──────────────────────────────────────────────────────────────┐${NC}"
echo -e "${BLUE}${BOLD}│${NC}  ${CYAN}${BOLD}⚡ ${MCP_DISPLAY_NAME} Universal AI Installer${NC}"
echo -e "${BLUE}${BOLD}│${NC}  Autonomous AI Search, Training & Agent Crawler Engine"
echo -e "${BLUE}${BOLD}└──────────────────────────────────────────────────────────────┘${NC}"
echo ""

HAS_UVX=false
HAS_NPX=false
if command -v uvx &>/dev/null; then HAS_UVX=true; fi
if command -v npx &>/dev/null; then HAS_NPX=true; fi

CHOSEN_COMMAND="uvx"
CHOSEN_ARGS='["ai-crawler-radar"]'

if [ "$HAS_UVX" = true ]; then
  echo -e "  ${GREEN}✔${NC} Runtime : ${BOLD}uvx detected${NC} (${GREEN}Recommended${NC})"
elif [ "$HAS_NPX" = true ]; then
  echo -e "  ${GREEN}✔${NC} Runtime : ${BOLD}npx detected${NC}"
  CHOSEN_COMMAND="npx"
  CHOSEN_ARGS='["-y", "ai-crawler-radar"]'
else
  echo -e "  ${YELLOW}⚠${NC} Runtime : Neither uvx nor npx detected in PATH. Please install Astral uv: https://docs.astral.sh/uv/"
fi

echo ""
echo -e "  ${BOLD}Configuring detected MCP agent harnesses...${NC}"

CONFIG_TARGETS=(
  "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
  "$HOME/.config/Claude/claude_desktop_config.json"
  "$HOME/.cursor/mcp.json"
  "$HOME/.claude.json"
  "$HOME/.gemini/antigravity/mcp_servers.json"
  "$HOME/.config/opencode/opencode.jsonc"
  "$HOME/.config/opencode/opencode.json"
)

INSTALLED_COUNT=0

for target in "${CONFIG_TARGETS[@]}"; do
  parent_dir="$(dirname "$target")"
  if [ -d "$parent_dir" ]; then
    printf "  • %-45s " "$(basename "$(dirname "$target")")/$(basename "$target")..."
    res=$(python3 -c "
import json, os, sys
p = os.path.expanduser('$target')
os.makedirs(os.path.dirname(p), exist_ok=True)
data = {}
if os.path.exists(p):
    try:
        with open(p, 'r') as f: data = json.load(f)
    except: pass
is_opencode = 'opencode' in p
if is_opencode:
    if 'mcp' not in data: data['mcp'] = {}
    data['mcp']['$MCP_SERVER_NAME'] = {
        'type': 'local',
        'command': ['$CHOSEN_COMMAND'] + json.loads('''$CHOSEN_ARGS'''),
        'enabled': True
    }
else:
    if 'mcpServers' not in data: data['mcpServers'] = {}
    data['mcpServers']['$MCP_SERVER_NAME'] = {
        'command': '$CHOSEN_COMMAND',
        'args': json.loads('''$CHOSEN_ARGS''')
    }
with open(p, 'w') as f:
    json.dump(data, f, indent=2)
print('SUCCESS')
" 2>&1 || true)
    if [ "$res" = "SUCCESS" ]; then
      echo -e "${GREEN}[OK]${NC}"
      INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
    else
      echo -e "${RED}[FAILED]${NC}"
    fi
  fi
done

echo ""
echo -e "  ${GREEN}${BOLD}🎉 Installation Complete! ($INSTALLED_COUNT configurations updated)${NC}"
echo -e "  Restart Claude Desktop, Cursor, or OpenCode to begin using ${CYAN}${MCP_SERVER_NAME}${NC}."
echo ""
