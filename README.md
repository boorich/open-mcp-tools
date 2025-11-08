# Open MCP Tools

A **general-purpose MCP server** with extensible tool modules. Currently includes tabletop rulebook tools with LLM-powered PDF ingestion.

## Features

### 🎲 **Tabletop Rulebook Tools** (First Tool Module)
- **List Resources**: Browse available rulebooks with filtering by complexity, player count, playtime, tags
- **Generate Quickstart**: Get quick-start guides with components, setup steps, and first-round walkthroughs
- **Lookup Rules**: Search for specific rules with citations and page references
- **Player Role Cheatsheets**: Generate role-specific cheatsheets with abilities, reminders, and tips

### 📚 **LLM-Powered PDF Ingestion**
- **Intelligent Extraction**: Uses Anthropic Claude or OpenAI to extract structured data from PDF rulebooks
- **High-Quality YAML**: Generates clean, structured YAML files ready to use
- **PDF Fallback**: Tools can fall back to original PDFs when YAML content is insufficient
- **Auto-Detection**: Automatically detects available LLM provider from API keys

### 🚀 **Production Infrastructure**
- **DCAP Performance Tracking**: Real-time performance monitoring via DCAP v2 protocol
- **x402 Payment Infrastructure**: Built-in payment support (disabled by default)
- **HTTP+SSE Transport**: Streaming support with Server-Sent Events
- **Type-Safe Tools**: Fully typed parameters and results using Pydantic models
- **Hot Reload**: Automatic reloading during development

## Installation

### Prerequisites

- Python 3.10 or higher
- uv (recommended) or pip

### Using uv (recommended)

```bash
# Clone and install
git clone https://github.com/boorich/open-mcp-tools.git
cd open-mcp-tools
uv sync

# Install ingestion dependencies (for PDF processing)
uv sync --group ingestion

# Run the server
uv run open-mcp-tools serve
```

### Using pip

```bash
# Install from source
pip install -e .

# Install ingestion dependencies
pip install pdfplumber anthropic openai

# Run the server
open-mcp-tools serve
```

### Environment Setup

Copy the example environment file and configure:

```bash
cp .env.example .env
# Edit .env with your configuration
```

**Required for PDF ingestion:**
```bash
# Set one of these (auto-detected)
ANTHROPIC_API_KEY=your-key-here
# OR
OPENAI_API_KEY=your-key-here
```

## Quick Start

### 1. Ingest PDF Rulebooks

Process PDF rulebooks to generate structured YAML:

```bash
# Process a single PDF
python scripts/ingest_rulebooks.py resources/game.pdf

# Process multiple PDFs
python scripts/ingest_rulebooks.py resources/*.pdf

# Use Anthropic (default if ANTHROPIC_API_KEY is set)
python scripts/ingest_rulebooks.py resources/game.pdf --llm-provider anthropic

# Use OpenAI
python scripts/ingest_rulebooks.py resources/game.pdf --llm-provider openai
```

See [scripts/INGESTION.md](scripts/INGESTION.md) for detailed ingestion documentation.

### 2. Start the Server

```bash
# Using uv
uv run open-mcp-tools serve

# Using pip
open-mcp-tools serve

# Or directly
python -m open_mcp_tools.cli serve
```

The server runs on `http://localhost:7284` by default.

### 3. Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector http://localhost:7284/mcp
```

## Using with Claude Desktop

For Claude Desktop, the server runs in stdio mode. Add to your Claude Desktop config:

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "open-mcp-tools": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/open-mcp-tools",
        "open-mcp-tools",
        "stdio"
      ]
    }
  }
}
```

Replace `/path/to/open-mcp-tools` with the actual path to your project directory.

## Using with Cursor

### Quick Install (Recommended)

Click the button below to automatically add the server to Cursor:

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en-US/install-mcp?name=open-mcp-tools&config=eyJ0eXBlIjoic3NlIiwidXJsIjoiaHR0cDovL2xvY2FsaG9zdDo3Mjg0L21jcCJ9)

**Prerequisites:**
1. Make sure the server is running (`uv run open-mcp-tools serve`)
2. The server must be accessible at `http://localhost:7284/mcp`

### Manual Installation

Alternatively, manually add to your Cursor MCP config:

**Location:** `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "open-mcp-tools": {
      "type": "sse",
      "url": "http://localhost:7284/mcp"
    }
  }
}
```

**Note:** The server must be running before Cursor can connect to it.

## Available Tools

### Tabletop Tools

#### `tabletop_list_resources`
List available tabletop rulebook resources with optional filtering.

**Parameters:**
- `play_style` (optional): Filter by play style (e.g., 'cooperative', 'competitive', 'solo')
- `complexity` (optional): Filter by complexity ('light', 'medium', 'heavy', 'very-heavy')
- `min_players` (optional): Minimum player count
- `max_players` (optional): Maximum player count
- `max_playtime` (optional): Maximum playtime in minutes
- `tags` (optional): Filter by tags (any match)

**Example:**
```json
{
  "play_style": "cooperative",
  "complexity": "medium",
  "min_players": 2,
  "max_players": 4
}
```

#### `tabletop_generate_quickstart`
Generate a quick-start guide for a tabletop game.

**Parameters:**
- `game_id` (required): Game identifier (e.g., 'mage-knight', 'voidfall')
- `player_count` (optional): Number of players for the quickstart
- `experience_level` (optional): 'beginner' or 'experienced'

**Example:**
```json
{
  "game_id": "mage-knight",
  "player_count": 1,
  "experience_level": "beginner"
}
```

#### `tabletop_lookup_rule`
Search for specific rules within a game's rulebook.

**Parameters:**
- `game_id` (required): Game identifier
- `query` (required): Rule or topic to search for (e.g., 'movement', 'combat')
- `section` (optional): Optional section to narrow search

**Features:**
- Searches YAML content first (fast)
- Falls back to PDF extraction when YAML is insufficient
- Returns page references and citations

**Example:**
```json
{
  "game_id": "voidfall",
  "query": "combat resolution",
  "section": "Combat"
}
```

#### `tabletop_player_role_cheatsheet`
Generate a cheatsheet for a specific player role or faction.

**Parameters:**
- `game_id` (required): Game identifier
- `role` (required): Role or faction name (e.g., 'Knight', 'Voidfall Imperium')
- `player_name` (optional): Optional player name for personalization

**Example:**
```json
{
  "game_id": "voidfall",
  "role": "Voidfall Imperium",
  "player_name": "Alice"
}
```

## Configuration

The server uses environment variables for configuration. Create a `.env` file:

```bash
# MCP Server Configuration
MCP_SERVER_URL=http://localhost:7284

# LLM API Keys (for PDF ingestion)
ANTHROPIC_API_KEY=your-key-here
# OR
OPENAI_API_KEY=your-key-here

# DCAP (Performance Tracking) - ENABLED by default
DCAP_ENABLED=true
DCAP_MULTICAST_IP=159.89.110.236
DCAP_PORT=10191

# x402 Payment Configuration - DISABLED by default
X402_ENABLED=false
```

See `.env.example` for all available options.

## Project Structure

```
open-mcp-tools/
├── src/open_mcp_tools/
│   ├── tools/
│   │   └── tabletop/          # Tabletop rulebook tools (first tool module)
│   │       ├── list_resources.py
│   │       ├── generate_quickstart.py
│   │       ├── lookup_rule.py
│   │       └── player_role_cheatsheet.py
│   ├── core/                   # Core MCP infrastructure
│   ├── handlers/                # MCP protocol handlers
│   └── server.py               # FastAPI server
├── resources/
│   └── rulebooks/              # Generated YAML rulebook resources
├── scripts/
│   ├── ingest_rulebooks.py     # LLM-powered PDF ingestion
│   └── INGESTION.md            # Ingestion documentation
└── schemas/
    └── resource.schema.json    # Generic resource schema
```

## Adding New Tool Modules

The server is designed to be extensible. To add a new tool module:

1. Create a new directory in `src/open_mcp_tools/tools/` (e.g., `tools/my_module/`)
2. Create tool files following the pattern in `tools/tabletop/`
3. Import tools in `tools/my_module/__init__.py`
4. Add import to `tools/__init__.py`

See existing tabletop tools for examples of the tool pattern.

## Development

```bash
# Install development dependencies
uv sync --dev

# Run server in development mode (with hot-reload)
OPEN_MCP_TOOLS_HOT_RELOAD=true uv run open-mcp-tools serve

# Run tests
pytest

# Format code
ruff format .

# Lint code
ruff check .
```

## Testing MCP Tools

### Using MCP Inspector

```bash
npx @modelcontextprotocol/inspector http://localhost:7284/mcp
```

### Using curl

```bash
# List all tools
curl -X POST http://localhost:7284/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'

# Call a tool
curl -X POST http://localhost:7284/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "tabletop_list_resources",
      "arguments": {
        "complexity": "medium"
      }
    }
  }'
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Related Projects

- [Model Context Protocol](https://modelcontextprotocol.io/) - The MCP specification
- [x402](https://github.com/x402-protocol) - Payment protocol for AI services
- [DCAP](https://github.com/boorich/dcap) - Performance tracking protocol
