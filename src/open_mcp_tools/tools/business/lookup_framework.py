"""
Business Framework Lookup Tool

Searches for frameworks/models in a business book with PDF fallback.
"""

import logging
from pathlib import Path
from typing import List, Optional

from pydantic import Field

from ...core import Tool, ToolContext, register_tool
from ...core.pricing import PricingType, ToolPricing
from ...core.resources.registry import get_registry
from ...core.resources.base import ResourceCategory, BusinessBookResource
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


class BusinessLookupFrameworkParams(MCPModel):
    """Parameters for looking up a framework"""
    
    book_id: str = Field(description="Book identifier (resource name)")
    query: str = Field(description="Framework name or keyword to search for")
    chapter: Optional[int] = Field(
        default=None,
        description="Optional chapter number to narrow search"
    )


class FrameworkMatch(MCPModel):
    """A matching framework with details"""
    
    name: str = Field(description="Framework name")
    description: str = Field(description="Framework description")
    components: List[str] = Field(description="Framework components/steps")
    application: Optional[str] = Field(default=None, description="How to apply")
    chapter: Optional[int] = Field(default=None, description="Chapter number")
    pdf_context: Optional[str] = Field(
        default=None,
        description="Additional context from PDF if used"
    )
    pdf_reference: Optional[str] = Field(
        default=None,
        description="Path to source PDF if PDF was used"
    )
    relevance_score: float = Field(
        description="Relevance score (0-1)",
        ge=0.0,
        le=1.0
    )


class BusinessLookupFrameworkResult(MCPModel):
    """Result from looking up a framework"""
    
    matches: List[FrameworkMatch] = Field(description="Matching frameworks")
    book_found: bool = Field(description="Whether the book was found")
    query: str = Field(description="The search query used")


@register_tool
class BusinessLookupFrameworkTool(Tool[BusinessLookupFrameworkParams, BusinessLookupFrameworkResult]):
    """Look up frameworks and models in a business book"""
    
    name = "business_lookup_framework"
    description = "Search for frameworks, models, and methodologies in a business book. Returns matching frameworks with descriptions, components, and application guidance. Falls back to PDF search for additional context."
    params_model = BusinessLookupFrameworkParams
    result_model = BusinessLookupFrameworkResult
    
    pricing = ToolPricing(type=PricingType.FREE)
    
    def _search_yaml_frameworks(
        self,
        content: dict,
        query: str,
        chapter_filter: Optional[int] = None
    ) -> List[FrameworkMatch]:
        """Search for frameworks in YAML content"""
        query_lower = query.lower()
        matches = []
        
        frameworks = content.get("frameworks", [])
        for fw in frameworks:
            name = fw.get("name", "")
            description = fw.get("description", "")
            components = fw.get("components", [])
            application = fw.get("application")
            fw_chapter = fw.get("chapter")
            
            # Apply chapter filter
            if chapter_filter is not None and fw_chapter != chapter_filter:
                continue
            
            # Check relevance
            name_match = query_lower in name.lower()
            desc_match = query_lower in description.lower()
            comp_match = any(query_lower in str(c).lower() for c in components)
            
            if name_match or desc_match or comp_match:
                # Calculate relevance score
                score = 0.0
                if name_match:
                    score += 1.0
                if desc_match:
                    score += 0.5
                if comp_match:
                    score += 0.3
                
                score = min(score, 1.0)
                
                matches.append(FrameworkMatch(
                    name=name,
                    description=description,
                    components=components,
                    application=application,
                    chapter=fw_chapter,
                    relevance_score=score
                ))
        
        # Sort by relevance
        matches.sort(key=lambda m: m.relevance_score, reverse=True)
        
        return matches
    
    def _search_pdf_for_framework(
        self,
        pdf_path: Path,
        query: str,
        chapter_filter: Optional[int] = None
    ) -> List[str]:
        """Search PDF for additional framework context"""
        if not HAS_PDFPLUMBER and not HAS_PYPDFIUM:
            logger.warning("No PDF library available for PDF search")
            return []
        
        query_lower = query.lower()
        contexts = []
        
        try:
            text_parts = []
            
            if HAS_PDFPLUMBER:
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
            elif HAS_PYPDFIUM:
                pdf = pypdfium.PdfDocument(pdf_path)
                for page_num in range(len(pdf)):
                    page = pdf.get_page(page_num)
                    textpage = page.get_textpage()
                    text = textpage.get_text_range()
                    if text:
                        text_parts.append(text)
                    page.close()
                pdf.close()
            
            # Search through pages
            for page_text in text_parts:
                if query_lower in page_text.lower():
                    # Extract context around matches
                    lines = page_text.split('\n')
                    for i, line in enumerate(lines):
                        if query_lower in line.lower():
                            # Get context (5 lines before and after)
                            start = max(0, i - 5)
                            end = min(len(lines), i + 6)
                            context_lines = lines[start:end]
                            context = '\n'.join(context_lines)
                            
                            if len(context) > 100:  # Only meaningful contexts
                                contexts.append(context[:800])  # Limit context size
                                
                                if len(contexts) >= 3:  # Max 3 contexts
                                    break
                
                if len(contexts) >= 3:
                    break
            
        except Exception as e:
            logger.error(f"PDF search failed: {e}")
        
        return contexts
    
    async def execute(
        self,
        ctx: ToolContext[BusinessLookupFrameworkParams, BusinessLookupFrameworkResult]
    ):
        registry = get_registry()
        
        # Find the book
        book_resource = None
        for resource in registry.list_resources(category=ResourceCategory.BUSINESS_BOOK):
            if isinstance(resource, BusinessBookResource) and resource.name == ctx.params.book_id:
                book_resource = resource
                break
        
        if not book_resource:
            yield ctx.structured(BusinessLookupFrameworkResult(
                matches=[],
                book_found=False,
                query=ctx.params.query
            ))
            return
        
        content = book_resource.get_content()
        source_pdf = getattr(book_resource, 'source_pdf', None)
        
        # Search in YAML first
        matches = self._search_yaml_frameworks(content, ctx.params.query, ctx.params.chapter)
        
        # If we have few matches and a PDF source, enrich with PDF context
        if source_pdf and len(matches) < 3:
            logger.info(f"Enriching with PDF context from: {source_pdf}")
            pdf_path = Path(source_pdf)
            
            if pdf_path.exists():
                pdf_contexts = self._search_pdf_for_framework(
                    pdf_path,
                    ctx.params.query,
                    ctx.params.chapter
                )
                
                # Add PDF context to existing matches or create new ones
                if matches and pdf_contexts:
                    # Add context to first match
                    matches[0].pdf_context = pdf_contexts[0]
                    matches[0].pdf_reference = str(pdf_path)
                elif not matches and pdf_contexts:
                    # Create match from PDF context
                    for context in pdf_contexts[:2]:  # Max 2 PDF-only matches
                        matches.append(FrameworkMatch(
                            name=f"Framework related to '{ctx.params.query}'",
                            description="Found in source PDF",
                            components=[],
                            pdf_context=context,
                            pdf_reference=str(pdf_path),
                            relevance_score=0.5
                        ))
            else:
                logger.warning(f"PDF file not found: {source_pdf}")
        
        result = BusinessLookupFrameworkResult(
            matches=matches[:5],  # Top 5 matches
            book_found=True,
            query=ctx.params.query
        )
        
        yield ctx.structured(result)

