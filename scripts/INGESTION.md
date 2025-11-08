# PDF Rulebook Ingestion (LLM-Enhanced)

Automatically extract structured data from PDF rulebooks using LLM-powered parsing for intelligent extraction.

## Why LLM Parsing?

PDFs are unstructured documents with wildly varying layouts. Regex-based parsing fails because:
- Different publishers use different formats
- Text extraction quality varies
- Layout information is lost
- Components/phases are formatted inconsistently

**LLM parsing solves this** by understanding context and extracting structured data intelligently.

## Installation

Install dependencies:

```bash
# Using pip
pip install pdfplumber openai

# Or using uv with dependency groups
uv sync --group ingestion
```

## Setup

Set your OpenAI API key:

```bash
export OPENAI_API_KEY=your-api-key-here
```

Or use Anthropic:

```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

## Usage

Process PDFs with LLM parsing (recommended):

```bash
# Single PDF
python scripts/ingest_rulebooks.py resources/game.pdf

# Multiple PDFs
python scripts/ingest_rulebooks.py resources/*.pdf

# Use Anthropic instead of OpenAI
python scripts/ingest_rulebooks.py resources/game.pdf --llm-provider anthropic

# Disable LLM (falls back to basic extraction - not recommended)
python scripts/ingest_rulebooks.py resources/game.pdf --no-llm
```

## What It Extracts

The LLM intelligently extracts:
- **Title** - Actual game title (not random text)
- **Game ID** - Clean kebab-case identifier
- **Edition** - Version/edition information
- **Player Count** - Min/max players
- **Playtime** - Duration range in minutes
- **Complexity** - Light/medium/heavy/very-heavy
- **Language** - Detected language
- **Components** - Clean list of game components
- **Table of Contents** - TOC with page numbers
- **Phases** - Actual game phases (not fragments)
- **Setup Steps** - Real setup instructions
- **Source PDF Reference** - Automatically stores path to original PDF for fallback access

## Quality

LLM parsing produces **much higher quality** results than regex-based extraction:
- ✅ Correct game titles
- ✅ Clean component lists
- ✅ Real phases, not sentence fragments
- ✅ Proper setup steps
- ✅ Accurate metadata

## Cost

**OpenAI GPT-4o-mini:**
- ~$0.15 per 1M input tokens
- ~$0.60 per 1M output tokens
- Typical rulebook: ~$0.01-0.05 per PDF

**Anthropic Claude Sonnet:**
- ~$3 per 1M input tokens
- ~$15 per 1M output tokens
- Typical rulebook: ~$0.05-0.15 per PDF

Anthropic is more expensive but often produces higher quality results.

## Fallback

If LLM parsing fails or is disabled, the script will error (basic extraction is too unreliable). For best results, always use LLM parsing.

## Output

Generated YAML files are saved to `resources/rulebooks/` by default:
- Filename: `{game-id}-v{version}.yaml`
- Format: Matches `schemas/resource.schema.json`
- Includes `source_pdf` field pointing to original PDF
- Ready to use with minimal or no manual editing

## PDF Fallback

The `source_pdf` field enables MCP tools to fall back to the original PDF when YAML content is insufficient:
- Tools can extract additional context from PDF pages
- Page references link back to the original document
- Seamless integration between structured YAML and full PDF content


