"""
Tabletop Lookup Rule Tool

Searches for rules in a specific game's rulebook with citations.
Falls back to PDF extraction when YAML content is insufficient.
"""

import logging
from pathlib import Path
from typing import List, Optional

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.resources.registry import get_registry
from ...core.resources.base import ResourceCategory
from ...core.types.models import MCPModel

logger = logging.getLogger(__name__)

# Try to import PDF libraries for fallback
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import pypdfium2 as pypdfium
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False


class TabletopLookupRuleParams(MCPModel):
    """Parameters for looking up a rule"""
    
    game_id: str = Field(description="Game identifier (resource name)")
    query: str = Field(description="Search query for the rule")
    section: Optional[str] = Field(
        default=None,
        description="Optional section name to narrow search"
    )


class RuleMatch(MCPModel):
    """A matching rule with citation"""
    
    title: str = Field(description="Rule title or section name")
    content: str = Field(description="Rule content/text")
    section: Optional[str] = Field(default=None, description="Section name")
    page: Optional[int] = Field(default=None, description="Page number if available")
    pdf_reference: Optional[str] = Field(
        default=None,
        description="Path to source PDF if PDF was used for extraction"
    )
    relevance_score: float = Field(
        description="Relevance score (0-1)",
        ge=0.0,
        le=1.0
    )


class TabletopLookupRuleResult(MCPModel):
    """Result from looking up a rule"""
    
    matches: List[RuleMatch] = Field(description="Matching rules")
    game_found: bool = Field(description="Whether the game was found")
    query: str = Field(description="The search query used")


@register_tool
class TabletopLookupRuleTool(Tool[TabletopLookupRuleParams, TabletopLookupRuleResult]):
    """Look up rules in a tabletop game's rulebook"""
    
    name = "tabletop_lookup_rule"
    description = "Search for rules in a tabletop game's rulebook. Returns matching rules with citations and relevance scores."
    params_model = TabletopLookupRuleParams
    result_model = TabletopLookupRuleResult
    
    pricing = ToolPricing(type=PricingType.FREE)
    
    def _has_sufficient_content(self, content: dict, query: str) -> bool:
        """Check if YAML content has sufficient information for the query"""
        # Check if we have detailed content (chapters with full text)
        chapters = content.get("chapters", [])
        if chapters:
            # Check if any chapter has substantial content
            for chapter in chapters:
                chapter_content = chapter.get("content", "")
                if len(chapter_content) > 500:  # Substantial content
                    return True
        
        # Check TOC - if we only have TOC entries without content, PDF might be better
        toc = content.get("toc", [])
        if toc and not chapters:
            return False
        
        # If we have phases/setup_steps, that's usually sufficient for basic queries
        if content.get("phases") or content.get("setup_steps"):
            return True
        
        return False
    
    def _search_content(self, content: dict, query: str, section: Optional[str] = None) -> List[RuleMatch]:
        """Search for rules in content"""
        query_lower = query.lower()
        matches = []
        
        # Search in chapters if available
        chapters = content.get("chapters", [])
        for chapter in chapters:
            chapter_title = chapter.get("title", "")
            
            # Check if section filter matches
            if section and section.lower() not in chapter_title.lower():
                continue
            
            # Search in chapter content
            chapter_content = chapter.get("content", "")
            if query_lower in chapter_content.lower():
                matches.append(RuleMatch(
                    title=chapter_title,
                    content=chapter_content[:500] + "..." if len(chapter_content) > 500 else chapter_content,
                    section=chapter_title,
                    page=None,
                    relevance_score=0.8 if query_lower in chapter_title.lower() else 0.6
                ))
            
            # Search in sections
            sections = chapter.get("sections", [])
            for sec in sections:
                sec_title = sec.get("title", "")
                sec_content = sec.get("content", "")
                
                if query_lower in sec_content.lower() or query_lower in sec_title.lower():
                    score = 1.0 if query_lower in sec_title.lower() else 0.7
                    if section and section.lower() in sec_title.lower():
                        score += 0.2
                    
                    matches.append(RuleMatch(
                        title=sec_title,
                        content=sec_content[:500] + "..." if len(sec_content) > 500 else sec_content,
                        section=chapter_title,
                        page=None,
                        relevance_score=min(score, 1.0)
                    ))
        
        # Search in TOC for page references
        toc = content.get("toc", [])
        for entry in toc:
            entry_title = entry.get("title", "")
            entry_section = entry.get("section", "")
            
            if query_lower in entry_title.lower() or query_lower in entry_section.lower():
                if section and section.lower() not in entry_title.lower() and section.lower() not in entry_section.lower():
                    continue
                
                matches.append(RuleMatch(
                    title=entry_title,
                    content=f"See section: {entry_section}",
                    section=entry_section,
                    page=entry.get("page"),
                    relevance_score=0.9 if query_lower in entry_title.lower() else 0.7
                ))
        
        # Sort by relevance
        matches.sort(key=lambda m: m.relevance_score, reverse=True)
        
        return matches[:10]  # Return top 10 matches
    
    def _search_pdf(self, pdf_path: Path, query: str, section: Optional[str] = None) -> List[RuleMatch]:
        """Search for rules in PDF file"""
        if not HAS_PDFPLUMBER and not HAS_PYPDFIUM:
            logger.warning("No PDF library available for PDF search")
            return []
        
        query_lower = query.lower()
        matches = []
        
        try:
            # Extract text from PDF
            text_parts = []
            page_numbers = []
            
            if HAS_PDFPLUMBER:
                with pdfplumber.open(pdf_path) as pdf:
                    for page_num, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
                            page_numbers.append(page_num)
            elif HAS_PYPDFIUM:
                pdf = pypdfium.PdfDocument(pdf_path)
                for page_num in range(len(pdf)):
                    page = pdf.get_page(page_num)
                    textpage = page.get_textpage()
                    text = textpage.get_text_range()
                    if text:
                        text_parts.append(text)
                        page_numbers.append(page_num + 1)
                pdf.close()
            
            # Search through pages
            for page_text, page_num in zip(text_parts, page_numbers):
                # Skip if section filter doesn't match
                if section and section.lower() not in page_text.lower():
                    continue
                
                # Check if query appears in this page
                if query_lower in page_text.lower():
                    # Extract context around matches
                    lines = page_text.split('\n')
                    matching_lines = []
                    for i, line in enumerate(lines):
                        if query_lower in line.lower():
                            # Get context (previous and next lines)
                            start = max(0, i - 2)
                            end = min(len(lines), i + 3)
                            context = '\n'.join(lines[start:end])
                            matching_lines.append(context)
                    
                    if matching_lines:
                        # Use first matching context
                        content = matching_lines[0]
                        # Try to extract a title (first non-empty line or section header)
                        title = "Page " + str(page_num)
                        for line in lines[:10]:  # Check first 10 lines for title
                            if line.strip() and len(line.strip()) < 100:
                                if any(keyword in line.lower() for keyword in ['section', 'chapter', 'phase', 'rule']):
                                    title = line.strip()
                                    break
                        
                        score = 0.8 if query_lower in title.lower() else 0.6
                        matches.append(RuleMatch(
                            title=title,
                            content=content[:500] + "..." if len(content) > 500 else content,
                            section=section,
                            page=page_num,
                            pdf_reference=str(pdf_path),
                            relevance_score=score
                        ))
            
            # Sort by relevance and page number
            matches.sort(key=lambda m: (m.relevance_score, -m.page if m.page else 0), reverse=True)
            return matches[:5]  # Return top 5 PDF matches
            
        except Exception as e:
            logger.error(f"Error searching PDF {pdf_path}: {e}")
            return []
    
    async def execute(
        self,
        ctx: ToolContext[TabletopLookupRuleParams, TabletopLookupRuleResult]
    ):
        """Execute the lookup rule tool"""
        registry = get_registry()
        
        # Find the game resource
        resources = registry.list_resources(category=ResourceCategory.RULEBOOK)
        game_resource = None
        
        for resource in resources:
            if resource.name == ctx.params.game_id:
                game_resource = resource
                break
        
        if not game_resource:
            result = TabletopLookupRuleResult(
                matches=[],
                game_found=False,
                query=ctx.params.query
            )
            yield ctx.structured(result)
            return
        
        content = game_resource.get_content()
        
        # Get source_pdf from resource (stored as attribute by loader)
        source_pdf = getattr(game_resource, 'source_pdf', None)
        
        # Search in YAML content first
        matches = self._search_content(content, ctx.params.query, ctx.params.section)
        
        # If YAML content is insufficient or we have few matches, try PDF fallback
        use_pdf_fallback = False
        if source_pdf:
            if not self._has_sufficient_content(content, ctx.params.query):
                logger.info(f"YAML content insufficient, falling back to PDF: {source_pdf}")
                use_pdf_fallback = True
            elif len(matches) < 3:  # Few matches found
                logger.info(f"Few matches in YAML, supplementing with PDF: {source_pdf}")
                use_pdf_fallback = True
        
        if use_pdf_fallback and source_pdf:
            pdf_path = Path(source_pdf)
            if pdf_path.exists():
                pdf_matches = self._search_pdf(pdf_path, ctx.params.query, ctx.params.section)
                # Merge PDF matches with YAML matches, prioritizing YAML
                # Add PDF matches that don't duplicate YAML content
                existing_titles = {m.title.lower() for m in matches}
                for pdf_match in pdf_matches:
                    if pdf_match.title.lower() not in existing_titles:
                        matches.append(pdf_match)
                # Re-sort all matches
                matches.sort(key=lambda m: m.relevance_score, reverse=True)
                matches = matches[:10]  # Keep top 10
            else:
                logger.warning(f"PDF file not found: {source_pdf}")
        
        result = TabletopLookupRuleResult(
            matches=matches,
            game_found=True,
            query=ctx.params.query
        )
        
        yield ctx.structured(result)

