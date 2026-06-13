# Inside your project Makefile
.PHONY: agent-search
agent-search:
	copilot -sp "$(prompt)" --additional-mcp-config="@.mcp.json" --allow-tool="playwright"

.PHONY: with-playwright
with-playwright:
copilot -sp "$(prompt)" --additional-mcp-config="@.mcp.json" --allow-tool="playwright"

.PHONY: playwright-workflow
playwright-workflow:
# Orchestrates work between CLI and IDE via MCP
@echo "Starting Playwright MCP workflow..."
@echo "✅ GitHub Copilot CLI: playwright available via --additional-mcp-config"
@echo "⚠  Claude Code (IDE): Requires .claude/settings.json update"
