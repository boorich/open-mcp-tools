"""
Business Chapter Lookup Tool

Retrieves chapter details from a business book with PDF fallback.
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


class BusinessLookupChapterParams(MCPModel):
    """Parameters for looking up a chapter"""
    
    book_id: str = Field(description="Book identifier (resource name)")
    chapter_number: Optional[int] = Field(
        default=None,
        description="Chapter number to retrieve (if not specified, returns all chapters)"
    )
    query: Optional[str] = Field(
        default=None,
        description="Optional keyword to search within chapters"
    )


class ChapterDetail(MCPModel):
    """Detailed chapter information"""
    
    number: int = Field(description="Chapter number")
    title: str = Field(description="Chapter title")
    summary: Optional[str] = Field(default=None, description="Chapter summary")
    key_concepts: List[str] = Field(description="Key concepts introduced")
    pdf_excerpt: Optional[str] = Field(
        default=None,
        description="Excerpt from PDF if available"
    )
    pdf_reference: Optional[str] = Field(
        default=None,
        description="Path to source PDF if PDF was used"
    )


class BusinessLookupChapterResult(MCPModel):
    """Result from looking up chapters"""
    
    chapters: List[ChapterDetail] = Field(description="Chapter details")
    book_found: bool = Field(description="Whether the book was found")
    total_chapters: int = Field(description="Total number of chapters in book")


@register_tool
class BusinessLookupChapterTool(Tool[BusinessLookupChapterParams, BusinessLookupChapterResult]):
    """Look up chapter details in a business book"""
    
    name = "business_lookup_chapter"
    description = "Retrieve chapter information from a business book including summaries, key concepts, and optional PDF excerpts. Can retrieve a specific chapter or all chapters."
    params_model = BusinessLookupChapterParams
    result_model = BusinessLookupChapterResult
    
    pricing = ToolPricing(type=PricingType.FREE)
    
    def _get_pdf_excerpt_for_chapter(
        self,
        pdf_path: Path,
        chapter_title: str,
        chapter_number: int
    ) -> Optional[str]:
        """Extract an excerpt from the PDF for a specific chapter"""
        if not HAS_PDFPLUMBER and not HAS_PYPDFIUM:
            return None
        
        try:
            chapter_keywords = [
                chapter_title.lower(),
                f"chapter {chapter_number}",
                f"chapter{chapter_number}"
            ]
            
            text_parts = []
            found_chapter = False
            excerpt_lines = []
            
            if HAS_PDFPLUMBER:
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if not text:
                            continue
                        
                        lines = text.split('\n')
                        for line in lines:
                            line_lower = line.lower()
                            
                            # Check if we found the chapter start
                            if not found_chapter:
                                for keyword in chapter_keywords:
                                    if keyword in line_lower:
                                        found_chapter = True
                                        excerpt_lines.append(line)
                                        break
                            elif found_chapter:
                                # Stop at next chapter or after reasonable amount
                                if len(excerpt_lines) > 50:  # ~50 lines
                                    break
                                    
                                # Check for next chapter marker
                                if any(marker in line_lower for marker in [f"chapter {chapter_number + 1}", "conclusion"]):
                                    break
                                    
                                excerpt_lines.append(line)
                        
                        if len(excerpt_lines) > 50:
                            break
            
            elif HAS_PYPDFIUM:
                pdf = pypdfium.PdfDocument(pdf_path)
                for page_num in range(min(len(pdf), 50)):  # Check first 50 pages
                    page = pdf.get_page(page_num)
                    textpage = page.get_textpage()
                    text = textpage.get_text_range()
                    
                    if text:
                        lines = text.split('\n')
                        for line in lines:
                            line_lower = line.lower()
                            
                            if not found_chapter:
                                for keyword in chapter_keywords:
                                    if keyword in line_lower:
                                        found_chapter = True
                                        excerpt_lines.append(line)
                                        break
                            elif found_chapter:
                                if len(excerpt_lines) > 50:
                                    break
                                    
                                if any(marker in line_lower for marker in [f"chapter {chapter_number + 1}", "conclusion"]):
                                    break
                                    
                                excerpt_lines.append(line)
                    
                    page.close()
                    if len(excerpt_lines) > 50:
                        break
                
                pdf.close()
            
            if excerpt_lines:
                excerpt = '\n'.join(excerpt_lines)
                # Limit to ~1500 characters
                if len(excerpt) > 1500:
                    excerpt = excerpt[:1500] + "..."
                return excerpt
            
        except Exception as e:
            logger.error(f"PDF excerpt extraction failed: {e}")
        
        return None
    
    async def execute(
        self,
        ctx: ToolContext[BusinessLookupChapterParams, BusinessLookupChapterResult]
    ):
        registry = get_registry()
        
        # Find the book
        book_resource = None
        for resource in registry.list_resources(category=ResourceCategory.BUSINESS_BOOK):
            if isinstance(resource, BusinessBookResource) and resource.name == ctx.params.book_id:
                book_resource = resource
                break
        
        if not book_resource:
            yield ctx.structured(BusinessLookupChapterResult(
                chapters=[],
                book_found=False,
                total_chapters=0
            ))
            return
        
        content = book_resource.get_content()
        source_pdf = getattr(book_resource, 'source_pdf', None)
        
        all_chapters = content.get("chapters", [])
        total = len(all_chapters)
        
        # Filter chapters
        chapters_to_return = []
        
        for chapter in all_chapters:
            ch_num = chapter.get("number")
            ch_title = chapter.get("title", "")
            ch_summary = chapter.get("summary")
            ch_concepts = chapter.get("key_concepts", [])
            
            # Apply filters
            if ctx.params.chapter_number is not None and ch_num != ctx.params.chapter_number:
                continue
            
            if ctx.params.query:
                query_lower = ctx.params.query.lower()
                if query_lower not in ch_title.lower() and \
                   (not ch_summary or query_lower not in ch_summary.lower()) and \
                   not any(query_lower in str(c).lower() for c in ch_concepts):
                    continue
            
            chapter_detail = ChapterDetail(
                number=ch_num,
                title=ch_title,
                summary=ch_summary,
                key_concepts=ch_concepts
            )
            
            # If this is a specific chapter request and we have PDF, get excerpt
            if ctx.params.chapter_number is not None and source_pdf:
                pdf_path = Path(source_pdf)
                if pdf_path.exists():
                    logger.info(f"Extracting PDF excerpt for chapter {ch_num}")
                    excerpt = self._get_pdf_excerpt_for_chapter(pdf_path, ch_title, ch_num)
                    if excerpt:
                        chapter_detail.pdf_excerpt = excerpt
                        chapter_detail.pdf_reference = str(pdf_path)
            
            chapters_to_return.append(chapter_detail)
        
        result = BusinessLookupChapterResult(
            chapters=chapters_to_return,
            book_found=True,
            total_chapters=total
        )
        
        yield ctx.structured(result)

