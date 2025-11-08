# Tabletop Rulebook MCP Server – Planning Notes

## Vision
Transform the DAML-focused Canton MCP server into a tabletop rulebook assistant that surfaces game rules, quick-start guides, and player aids via MCP tools. Target users should be able to fetch a rulebook, learn the basics, and resolve rules questions without reading the full PDF.

---

## High-Level Goals
- Parse and structure rulebooks for the following titles:
  - Dungeons & Dragons SRD / OGL content
  - Mage Knight Ultimate Edition
  - On Mars
  - Mombasa
  - Voidfall
- Provide MCP tools that act like game masters:
  - quick-start walkthroughs
  - rule lookup / citations
  - player-role cheat sheets
  - setup & turn reminders
- Keep infrastructure light: FastAPI server, resource registry, optional streaming, existing pricing/DCAP hooks.

---

## Deliverables & Milestones

### 1. Repository Reset
- Rebrand README and package metadata
- Remove DAML-specific resources; replace with tabletop content
- Optionally reinitialize git history for cleaner start

### 2. Resource Schema & Sample Data
- Define `resources/rulebooks/` with `rulebook.schema.json`
  - metadata: title, edition, player count, playtime, complexity, tags
  - content: TOC, components, phases, setup steps
  - optional `chapters/` sub-docs for larger rulesets (e.g. D&D)
- Create initial YAML stubs for each game using downloaded PDFs
- Add validator/tests for the new schema

### 3. Ingestion Pipeline
- `scripts/ingest_rulebooks.py`:
  - Accept local PDF paths
  - Extract text (PyPDF / pypdfium / pdfplumber) into structured sections (appendices, phase guides, glossary)
  - Generate YAML + preprocessed markdown chunks
  - Build search index metadata (keywords, sections with page refs)
- Plan for manual post-processing where OCR is messy

### 4. Core Library Updates
- Update `resource_loader` and registry to support new `rulebook` category
- Adjust `resource_recommender` to categorize by game genre, playtime, complexity
- Introduce helper utilities (`search_index.py`, `toc_utils.py`)

### 5. MCP Tools (first batch)
- `list_tabletop_resources`
  - Returns catalog by play style, complexity, duration
- `generate_quickstart`
  - Inputs: game id, player count, experience level
  - Output: components checklist + setup flow + first round script
- `lookup_rule`
  - Inputs: game id, query string, optional section
  - Output: best matches with page/section citations and quoted text
- `player_role_cheatsheet`
  - Inputs: game id, role/faction
  - Output: asymmetric abilities, reminders, key scoring conditions
- Tests for each tool covering happy path + no matches + bad ids

### 6. Optional Enhancements
- Caching of extracted sections for faster lookup
- Integration with embeddings (if we add lightweight vector search later)
- Stream progress updates while scanning large rulebooks
- Pricing adjustments (likely keep tools FREE for now)

---

## File/Directory Checklist
- `README.md` (updated branding)
- `schemas/rulebook.schema.json`
- `resources/rulebooks/*.yaml` (one per game)
- `scripts/ingest_rulebooks.py` + helper modules
- `src/canton_mcp_server/core/resources/` updates
- `src/canton_mcp_server/tools/` new tool implementations
- `tests/tools/test_tabletop_tools.py` (or similar)
- `tests/resources/test_rulebook_schema.py`

---

## Open Questions
- Do we want to store large rule sections inline in YAML or in separate `.md` files?
- Should we support multiple languages? (Current PDFs are German/English—plan for metadata flag.)
- Will we expose player aids for expansions separately or bundle into base rulebooks?
- How much of the ingestion will be automated vs. manually curated?

---

## Next Steps
1. Commit the downloaded PDFs (if allowed) or reference local storage paths.
2. Draft `rulebook.schema.json` and create one hand-written YAML resource (e.g. Mage Knight) to validate the loader.
3. Modify loader/registry to recognize `rulebook` category and run unit tests.
4. Start on `list_tabletop_resources` tool to confirm end-to-end flow before tackling heavier ingestion.