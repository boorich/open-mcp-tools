#!/usr/bin/env python3
"""
Rulebook Ingestion Script (LLM-Enhanced)

Extracts structured data from PDF rulebooks using LLM parsing for intelligent extraction.
Falls back to basic extraction if LLM is unavailable.
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
    import pypdfium2 as pypdfium
    HAS_PYPDFIUM = True
except ImportError:
    pass

# Try to import OpenAI/Anthropic for LLM parsing
HAS_OPENAI = False
HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    pass

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extracts text from PDF files using available libraries"""
    
    def __init__(self):
        self.library_priority = []
        if HAS_PDFPLUMBER:
            self.library_priority.append("pdfplumber")
        if HAS_PYPDFIUM:
            self.library_priority.append("pypdfium")
        if HAS_PYPDF2:
            self.library_priority.append("pypdf2")
        
        if not self.library_priority:
            raise ImportError(
                "No PDF library found. Install one of: pdfplumber, pypdfium2, PyPDF2"
            )
        
        logger.info(f"Using PDF libraries (priority): {', '.join(self.library_priority)}")
    
    def extract_text(self, pdf_path: Path) -> str:
        """Extract all text from PDF"""
        for library in self.library_priority:
            try:
                if library == "pdfplumber":
                    return self._extract_with_pdfplumber(pdf_path)
                elif library == "pypdfium":
                    return self._extract_with_pypdfium(pdf_path)
                elif library == "pypdf2":
                    return self._extract_with_pypdf2(pdf_path)
            except Exception as e:
                logger.warning(f"Failed to extract with {library}: {e}")
                continue
        
        raise RuntimeError(f"Failed to extract text from {pdf_path} with any library")
    
    def _extract_with_pdfplumber(self, pdf_path: Path) -> str:
        """Extract text using pdfplumber"""
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)
    
    def _extract_with_pypdfium(self, pdf_path: Path) -> str:
        """Extract text using pypdfium"""
        pdf = pypdfium.PdfDocument(pdf_path)
        text_parts = []
        for page_num in range(len(pdf)):
            page = pdf.get_page(page_num)
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            if text:
                text_parts.append(text)
        pdf.close()
        return "\n".join(text_parts)
    
    def _extract_with_pypdf2(self, pdf_path: Path) -> str:
        """Extract text using PyPDF2"""
        text_parts = []
        with open(pdf_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)


class LLMParser:
    """Uses LLM to intelligently parse rulebook text into structured data"""
    
    def __init__(self, provider: str = "openai"):
        self.provider = provider
        self.api_key = None
        
        if provider == "openai" and HAS_OPENAI:
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                logger.warning("OPENAI_API_KEY not set, LLM parsing disabled")
                self.provider = None
        elif provider == "anthropic" and HAS_ANTHROPIC:
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                logger.warning("ANTHROPIC_API_KEY not set, LLM parsing disabled")
                self.provider = None
        else:
            self.provider = None
    
    def parse(self, text: str, pdf_name: str) -> Dict:
        """Parse text using LLM"""
        if not self.provider:
            return None
        
        # Truncate text if too long (keep first ~50k chars for context)
        text_sample = text[:50000] if len(text) > 50000 else text
        
        prompt = f"""Extract structured information from this tabletop game rulebook PDF.

PDF filename: {pdf_name}

Extracted text (first portion):
{text_sample}

Extract the following information and return as JSON:
{{
  "name": "game-id-in-kebab-case",
  "title": "Full Game Title",
  "edition": "Edition info if available, else null",
  "player_count": {{"min": number, "max": number}} or null,
  "playtime": {{"min": minutes, "max": minutes}} or null,
  "complexity": "light|medium|heavy|very-heavy" or null,
  "language": "en|de|fr|es" etc,
  "author": "Publisher/author name" or null,
  "description": "Brief description of the game",
  "tags": ["tag1", "tag2", ...],
  "components": ["component1", "component2", ...],
  "toc": [
    {{"title": "Section title", "section": "Section name", "page": number}}
  ],
  "phases": [
    {{"name": "Phase name", "description": "Brief description", "order": number}}
  ],
  "setup_steps": ["step1", "step2", ...]
}}

Guidelines:
- Use the actual game title from the PDF, not random text
- Generate a clean game-id from the title (lowercase, hyphens)
- Extract real components, not layout text
- Only include actual game phases, not random sentences
- Extract real setup steps, not fragments
- Be accurate with player counts and playtime
- Detect language correctly
- Include relevant tags (cooperative, competitive, solo, deck-building, worker-placement, etc.)

Return ONLY valid JSON, no markdown formatting."""

        try:
            if self.provider == "openai":
                return self._parse_with_openai(prompt)
            elif self.provider == "anthropic":
                return self._parse_with_anthropic(prompt)
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return None
    
    def _parse_with_openai(self, prompt: str) -> Dict:
        """Parse using OpenAI API"""
        client = openai.OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use cheaper model for parsing
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts structured data from game rulebooks. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Low temperature for consistent extraction
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        return json.loads(result_text)
    
    def _parse_with_anthropic(self, prompt: str) -> Dict:
        """Parse using Anthropic API"""
        client = anthropic.Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            temperature=0.1,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        result_text = message.content[0].text
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(result_text)


def ingest_pdf(pdf_path: Path, output_dir: Path, use_llm: bool = True, llm_provider: str = "openai", overwrite: bool = False) -> Path:
    """Ingest a PDF and generate YAML resource file"""
    logger.info(f"Processing: {pdf_path.name}")
    
    # Extract text
    extractor = PDFExtractor()
    text = extractor.extract_text(pdf_path)
    
    if not text or len(text) < 100:
        raise ValueError(f"Failed to extract meaningful text from {pdf_path}")
    
    logger.info(f"Extracted {len(text)} characters from PDF")
    
    # Parse text
    resource_data = None
    
    if use_llm:
        logger.info("Attempting LLM-based parsing...")
        llm_parser = LLMParser(provider=llm_provider)
        resource_data = llm_parser.parse(text, pdf_path.name)
        
        if resource_data:
            logger.info("✅ LLM parsing successful")
        else:
            logger.warning("LLM parsing failed, falling back to basic extraction")
    
    # Fallback to basic extraction if LLM failed or disabled
    if not resource_data:
        logger.warning("LLM parsing unavailable or failed. Install openai or anthropic package and set API key.")
        logger.warning("Example: pip install openai && export OPENAI_API_KEY=your-key")
        raise ValueError("LLM parsing required for quality extraction. Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable.")
    
    # Add metadata
    resource_data["version"] = resource_data.get("version", "1.0.0")
    resource_data["category"] = "rulebooks"
    resource_data["created_at"] = datetime.now().isoformat()
    
    # Generate output filename
    game_id = resource_data["name"]
    version = resource_data["version"]
    output_file = output_dir / f"{game_id}-v{version}.yaml"
    
    if output_file.exists() and not overwrite:
        logger.warning(f"File exists: {output_file}. Use --overwrite to replace.")
        return output_file
    
    # Write YAML
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(resource_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    logger.info(f"Created: {output_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(description="Ingest PDF rulebooks and generate YAML resources")
    parser.add_argument(
        "pdf_paths",
        nargs="+",
        type=Path,
        help="PDF files to process"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("resources/rulebooks"),
        help="Output directory for YAML files (default: resources/rulebooks)"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing YAML files"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM parsing, use basic extraction only"
    )
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "anthropic"],
        default="openai",
        help="LLM provider to use (default: openai)"
    )
    
    args = parser.parse_args()
    
    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)
    
    # Process each PDF
    for pdf_path in args.pdf_paths:
        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            continue
        
        try:
            ingest_pdf(pdf_path, args.output, use_llm=not args.no_llm, llm_provider=args.llm_provider, overwrite=args.overwrite)
        except Exception as e:
            logger.error(f"Failed to process {pdf_path}: {e}", exc_info=True)


if __name__ == "__main__":
    main()

