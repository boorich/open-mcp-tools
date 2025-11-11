#!/usr/bin/env python3
"""
Business Book Ingestion Script (LLM-Enhanced)

Extracts structured data from business/self-help book PDFs using LLM parsing.
"""

import argparse
import json
import logging
import os
import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Try to import PDF libraries
HAS_PDFPLUMBER = False
HAS_PYPDF2 = False
HAS_PYPDFIUM = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    pass

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    pass

try:
    import pypdfium2
    HAS_PYPDFIUM = True
except ImportError:
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text from PDF files using available libraries."""
    
    def __init__(self):
        if not any([HAS_PDFPLUMBER, HAS_PYPDFIUM, HAS_PYPDF2]):
            raise ImportError(
                "No PDF library found. Install one of: pdfplumber, pypdfium2, PyPDF2"
            )
        
        # Priority order for PDF extraction
        self.extractors = []
        if HAS_PDFPLUMBER:
            self.extractors.append(('pdfplumber', self._extract_with_pdfplumber))
        if HAS_PYPDFIUM:
            self.extractors.append(('pypdfium', self._extract_with_pypdfium))
        if HAS_PYPDF2:
            self.extractors.append(('pypdf2', self._extract_with_pypdf2))
        
        logger.info(f"Using PDF libraries (priority): {', '.join([name for name, _ in self.extractors])}")
    
    def extract(self, pdf_path: Path) -> str:
        """Extract text from PDF."""
        for name, extractor in self.extractors:
            try:
                return extractor(pdf_path)
            except Exception as e:
                logger.warning(f"{name} extraction failed: {e}")
                continue
        
        raise RuntimeError("All PDF extraction methods failed")
    
    def _extract_with_pdfplumber(self, pdf_path: Path) -> str:
        """Extract using pdfplumber."""
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)
    
    def _extract_with_pypdfium(self, pdf_path: Path) -> str:
        """Extract using pypdfium2."""
        import pypdfium2 as pdfium
        text_parts = []
        pdf = pdfium.PdfDocument(pdf_path)
        for page in pdf:
            textpage = page.get_textpage()
            text_parts.append(textpage.get_text_range())
            textpage.close()
            page.close()
        pdf.close()
        return "\n\n".join(text_parts)
    
    def _extract_with_pypdf2(self, pdf_path: Path) -> str:
        """Extract using PyPDF2."""
        text_parts = []
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n\n".join(text_parts)


class LLMParser:
    """Parse book content using LLM."""
    
    def __init__(self, provider: str = None):
        """Initialize LLM parser with specified provider."""
        # Auto-detect provider if not specified
        if provider is None:
            if os.getenv('ANTHROPIC_API_KEY'):
                provider = 'anthropic'
            elif os.getenv('OPENAI_API_KEY'):
                provider = 'openai'
            else:
                raise ValueError("No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
        
        self.provider = provider
        logger.info(f"Auto-detected LLM provider: {provider}")
        
        if provider == 'anthropic':
            import anthropic
            self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        elif provider == 'openai':
            import openai
            self.client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def parse(self, text: str, book_title: str) -> Dict:
        """Parse book text into structured format using LLM."""
        
        prompt = f"""You are parsing a business/self-help book into a structured format.

Book text excerpt (may be truncated):
{text[:50000]}

Extract the following information in JSON format:
{{
  "title": "Full book title",
  "subtitle": "Subtitle if present, else null",
  "author": "Author name(s)",
  "publication_year": year as integer or null,
  "description": "Brief 2-3 sentence description of what the book is about",
  "category": "One of: business, leadership, productivity, entrepreneurship, management, self-help, strategy, marketing, sales, finance",
  "tags": ["keyword1", "keyword2", ...],
  "target_audience": ["Who this book is for", ...],
  "chapters": [
    {{
      "number": 1,
      "title": "Chapter title",
      "summary": "2-3 sentence summary of the chapter",
      "key_concepts": ["concept1", "concept2", ...]
    }},
    ...
  ],
  "frameworks": [
    {{
      "name": "Framework/Model name",
      "description": "What it is and why it matters",
      "chapter": chapter number where introduced,
      "components": ["part1", "part2", ...],
      "application": "How to apply it"
    }},
    ...
  ],
  "key_takeaways": ["Main insight 1", "Main insight 2", ...],
  "action_items": [
    {{
      "action": "What to do",
      "description": "Details about the action",
      "chapter": related chapter number,
      "difficulty": "easy/medium/hard"
    }},
    ...
  ]
}}

Focus on extracting:
1. All chapters with summaries and key concepts
2. Important frameworks, models, and methodologies
3. Actionable items and exercises
4. Main takeaways and insights

Return ONLY valid JSON, no additional text."""

        try:
            logger.info(f"Attempting LLM-based parsing with {self.provider}...")
            
            if self.provider == 'anthropic':
                response = self.client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.content[0].text
            
            elif self.provider == 'openai':
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
            
            # Clean response (remove markdown code blocks if present)
            content = content.strip()
            if content.startswith('```'):
                # Extract JSON from markdown code block
                lines = content.split('\n')
                # Remove first line (```json or ```)
                lines = lines[1:]
                # Remove last line (```)
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                content = '\n'.join(lines)
            
            # Parse JSON response
            data = json.loads(content)
            logger.info("✅ LLM parsing successful")
            return data
            
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            raise


def create_slug(title: str) -> str:
    """Create a URL-friendly slug from title."""
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def ingest_pdf(pdf_path: Path, output_dir: Path, use_llm: bool = True, 
               llm_provider: str = None, overwrite: bool = False):
    """Process a PDF and generate YAML resource."""
    
    # Extract PDF text
    extractor = PDFExtractor()
    text = extractor.extract(pdf_path)
    logger.info(f"Extracted {len(text)} characters from PDF")
    
    # Get book title from filename as fallback
    book_title = pdf_path.stem.replace('_', ' ').replace('-', ' ').title()
    
    if use_llm:
        # Parse with LLM
        parser = LLMParser(provider=llm_provider)
        data = parser.parse(text, book_title)
    else:
        # Basic extraction (no LLM)
        logger.warning("LLM disabled - generating basic structure only")
        data = {
            "title": book_title,
            "author": "Unknown",
            "description": "No description available (LLM parsing disabled)",
            "category": "business",
            "chapters": [],
            "frameworks": [],
            "key_takeaways": [],
            "action_items": []
        }
    
    # Generate resource name
    name = create_slug(data.get('title', book_title))
    
    # Build YAML structure
    resource = {
        'name': name,
        'title': data.get('title', book_title),
        'subtitle': data.get('subtitle'),
        'author': data.get('author', 'Unknown'),
        'publication_year': data.get('publication_year'),
        'isbn': data.get('isbn'),
        'language': data.get('language', 'en'),
        'description': data.get('description', ''),
        'category': data.get('category', 'business'),
        'tags': data.get('tags', []),
        'chapters': data.get('chapters', []),
        'frameworks': data.get('frameworks', []),
        'key_takeaways': data.get('key_takeaways', []),
        'action_items': data.get('action_items', []),
        'target_audience': data.get('target_audience', []),
        'version': '1.0.0',
        'category_type': 'business-books',
        'created_at': datetime.now().isoformat(),
        'source_pdf': str(pdf_path.absolute())
    }
    
    # Save YAML
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}-v1.0.0.yaml"
    
    if output_path.exists() and not overwrite:
        logger.warning(f"File exists: {output_path} (use --overwrite to replace)")
        return
    
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(resource, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    
    logger.info(f"Created: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Ingest business book PDFs and generate YAML resources')
    parser.add_argument('pdf_paths', nargs='+', help='PDF files to process')
    parser.add_argument('-o', '--output', default='resources/business-books',
                       help='Output directory for YAML files (default: resources/business-books)')
    parser.add_argument('--overwrite', action='store_true',
                       help='Overwrite existing YAML files')
    parser.add_argument('--no-llm', action='store_true',
                       help='Disable LLM parsing, use basic extraction only')
    parser.add_argument('--llm-provider', choices=['openai', 'anthropic'],
                       help='LLM provider to use (default: auto-detect from available API keys)')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    
    for pdf_path_str in args.pdf_paths:
        pdf_path = Path(pdf_path_str)
        
        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            continue
        
        logger.info(f"Processing: {pdf_path.name}")
        
        try:
            ingest_pdf(
                pdf_path, 
                output_dir, 
                use_llm=not args.no_llm,
                llm_provider=args.llm_provider,
                overwrite=args.overwrite
            )
        except Exception as e:
            logger.error(f"Failed to process {pdf_path}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    main()

