#!/usr/bin/env python3
"""
Rulebook Ingestion Script

Extracts structured data from PDF rulebooks and generates YAML resource files.
Supports multiple PDF libraries (PyPDF2, pdfplumber, pypdfium) with fallback.
"""

import argparse
import logging
import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Try to import PDF libraries (with fallback)
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


class RulebookParser:
    """Parses extracted PDF text to extract structured rulebook data"""
    
    def __init__(self, text: str, pdf_name: str):
        self.text = text
        self.pdf_name = pdf_name
        self.lines = text.split("\n")
    
    def parse(self) -> Dict:
        """Parse the text and extract structured data"""
        # Extract basic metadata
        title = self._extract_title()
        game_id = self._generate_game_id(title)
        
        # Extract structured content
        content = {
            "title": title,
            "edition": self._extract_edition(),
            "player_count": self._extract_player_count(),
            "playtime": self._extract_playtime(),
            "complexity": self._extract_complexity(),
            "language": self._detect_language(),
            "components": self._extract_components(),
            "toc": self._extract_toc(),
            "phases": self._extract_phases(),
            "setup_steps": self._extract_setup_steps(),
        }
        
        # Build full resource structure
        resource = {
            "name": game_id,
            "version": "1.0.0",
            "description": self._generate_description(title, content),
            "tags": self._generate_tags(content),
            "category": "rulebooks",
            "author": self._extract_author(),
            "created_at": datetime.now().isoformat(),
            **content
        }
        
        return resource
    
    def _extract_title(self) -> str:
        """Extract game title from PDF"""
        # Try to find title in first few lines
        for i, line in enumerate(self.lines[:20]):
            line = line.strip()
            if len(line) > 3 and len(line) < 100:
                # Skip common headers/footers
                if line.lower() not in ["spielanleitung", "rulebook", "rules", "manual"]:
                    # Check if it looks like a title (capitalized, not all caps)
                    if line[0].isupper() and not line.isupper():
                        return line
        
        # Fallback: use PDF filename
        name = Path(self.pdf_name).stem
        # Clean up filename
        name = re.sub(r"[-_]", " ", name)
        name = re.sub(r"\s+", " ", name)
        return name.title()
    
    def _generate_game_id(self, title: str) -> str:
        """Generate game ID from title"""
        # Convert to lowercase, replace spaces with hyphens
        game_id = title.lower()
        game_id = re.sub(r"[^a-z0-9]+", "-", game_id)
        game_id = re.sub(r"^-+|-+$", "", game_id)
        return game_id
    
    def _extract_edition(self) -> Optional[str]:
        """Extract edition information"""
        text_lower = self.text.lower()
        
        # Look for edition patterns
        edition_patterns = [
            r"edition[:\s]+([^\n]+)",
            r"version[:\s]+([^\n]+)",
            r"v(\d+\.\d+)",
        ]
        
        for pattern in edition_patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_player_count(self) -> Optional[Dict[str, int]]:
        """Extract player count range"""
        text_lower = self.text.lower()
        
        # Look for player count patterns
        patterns = [
            r"(\d+)\s*[-–]\s*(\d+)\s*players?",
            r"(\d+)\s*to\s*(\d+)\s*players?",
            r"(\d+)\s*players?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                if len(match.groups()) == 2:
                    return {"min": int(match.group(1)), "max": int(match.group(2))}
                else:
                    num = int(match.group(1))
                    return {"min": num, "max": num}
        
        return None
    
    def _extract_playtime(self) -> Optional[Dict[str, int]]:
        """Extract playtime range in minutes"""
        text_lower = self.text.lower()
        
        # Look for playtime patterns
        patterns = [
            r"(\d+)\s*[-–]\s*(\d+)\s*minutes?",
            r"(\d+)\s*to\s*(\d+)\s*minutes?",
            r"(\d+)\s*minutes?",
            r"(\d+)\s*[-–]\s*(\d+)\s*min",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                if len(match.groups()) == 2:
                    return {"min": int(match.group(1)), "max": int(match.group(2))}
                else:
                    num = int(match.group(1))
                    return {"min": num, "max": num}
        
        return None
    
    def _extract_complexity(self) -> Optional[str]:
        """Extract complexity level"""
        text_lower = self.text.lower()
        
        complexity_map = {
            "light": ["light", "easy", "simple", "leicht"],
            "medium": ["medium", "moderate", "mittel"],
            "heavy": ["heavy", "complex", "schwer"],
            "very-heavy": ["very heavy", "very complex", "sehr schwer"],
        }
        
        for level, keywords in complexity_map.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return level
        
        return None
    
    def _detect_language(self) -> str:
        """Detect language from text"""
        # Simple heuristic: check for German words
        german_words = ["der", "die", "das", "und", "ist", "für", "auf", "mit"]
        text_lower = self.text.lower()
        
        german_count = sum(1 for word in german_words if word in text_lower)
        if german_count > 5:
            return "de"
        
        return "en"
    
    def _extract_components(self) -> List[str]:
        """Extract game components list"""
        components = []
        
        # Look for components section
        text_lower = self.text.lower()
        component_keywords = ["components", "contents", "inhalte", "material"]
        
        for keyword in component_keywords:
            # Find section
            pattern = rf"{keyword}[:\s]*\n((?:.*\n){{0,50}})"
            match = re.search(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
            if match:
                section = match.group(1)
                # Extract list items
                lines = section.split("\n")
                for line in lines[:30]:  # Limit search
                    line = line.strip()
                    # Look for numbered or bulleted items
                    if re.match(r"^[\d•\-\*]\s+", line):
                        component = re.sub(r"^[\d•\-\*]\s+", "", line)
                        if len(component) > 3:
                            components.append(component)
                    elif len(line) > 5 and len(line) < 100:
                        components.append(line)
                
                if components:
                    break
        
        return components[:20]  # Limit to 20 components
    
    def _extract_toc(self) -> List[Dict]:
        """Extract table of contents"""
        toc = []
        
        # Look for TOC section
        toc_keywords = ["contents", "table of contents", "inhalt", "inhaltsverzeichnis"]
        
        for keyword in toc_keywords:
            # Find TOC section (usually early in document)
            pattern = rf"{keyword}[:\s]*\n((?:.*\n){{0,100}})"
            match = re.search(pattern, self.text, re.IGNORECASE | re.MULTILINE)
            if match:
                section = match.group(1)
                lines = section.split("\n")
                
                for line in lines:
                    line = line.strip()
                    # Look for page numbers
                    page_match = re.search(r"(\d+)\s*$", line)
                    if page_match:
                        page_num = int(page_match.group(1))
                        title = re.sub(r"\s+\d+\s*$", "", line).strip()
                        if title:
                            toc.append({
                                "title": title,
                                "section": title,
                                "page": page_num
                            })
                
                if toc:
                    break
        
        return toc[:50]  # Limit to 50 entries
    
    def _extract_phases(self) -> List[Dict]:
        """Extract game phases"""
        phases = []
        
        # Look for phase/round keywords
        phase_keywords = ["phase", "round", "turn", "runde", "phase"]
        
        for keyword in phase_keywords:
            # Find phases section
            pattern = rf"{keyword}[:\s]*\n((?:.*\n){{0,50}})"
            matches = re.finditer(pattern, self.text, re.IGNORECASE | re.MULTILINE)
            
            for match in list(matches)[:5]:  # Limit matches
                section = match.group(1)
                lines = section.split("\n")
                
                for i, line in enumerate(lines[:20]):
                    line = line.strip()
                    if len(line) > 5 and len(line) < 100:
                        phases.append({
                            "name": line,
                            "description": "",
                            "order": len(phases) + 1
                        })
        
        return phases[:10]  # Limit to 10 phases
    
    def _extract_setup_steps(self) -> List[str]:
        """Extract setup instructions"""
        setup_steps = []
        
        # Look for setup section
        setup_keywords = ["setup", "preparation", "vorbereitung", "aufbau"]
        
        for keyword in setup_keywords:
            # Find setup section
            pattern = rf"{keyword}[:\s]*\n((?:.*\n){{0,50}})"
            match = re.search(pattern, self.text, re.IGNORECASE | re.MULTILINE)
            if match:
                section = match.group(1)
                lines = section.split("\n")
                
                for line in lines:
                    line = line.strip()
                    # Look for numbered steps
                    step_match = re.match(r"^(\d+)[\.\)]\s+(.+)$", line)
                    if step_match:
                        setup_steps.append(step_match.group(2))
                    elif len(line) > 10 and len(line) < 200:
                        setup_steps.append(line)
                
                if setup_steps:
                    break
        
        return setup_steps[:20]  # Limit to 20 steps
    
    def _extract_author(self) -> Optional[str]:
        """Extract author/publisher"""
        # Look for common publisher patterns
        publishers = ["z-man", "fantasy flight", "eagle gryphon", "stronghold"]
        text_lower = self.text.lower()
        
        for publisher in publishers:
            if publisher in text_lower:
                return publisher.title()
        
        return None
    
    def _generate_description(self, title: str, content: Dict) -> str:
        """Generate description from extracted data"""
        parts = [f"Rulebook for {title}"]
        
        if content.get("player_count"):
            pc = content["player_count"]
            parts.append(f"for {pc['min']}-{pc['max']} players")
        
        if content.get("playtime"):
            pt = content["playtime"]
            parts.append(f"({pt['min']}-{pt['max']} minutes)")
        
        return ". ".join(parts) + "."
    
    def _generate_tags(self, content: Dict) -> List[str]:
        """Generate tags from content"""
        tags = []
        
        if content.get("complexity"):
            tags.append(content["complexity"])
        
        if content.get("language"):
            tags.append(content["language"])
        
        # Add genre tags based on title/content
        text_lower = self.text.lower()
        genre_keywords = {
            "cooperative": ["cooperative", "kooperativ"],
            "competitive": ["competitive", "wettkampf"],
            "solo": ["solo", "single player"],
            "deck-building": ["deck building", "deckbau"],
            "worker-placement": ["worker placement", "arbeiter"],
        }
        
        for tag, keywords in genre_keywords.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(tag)
        
        if not tags:
            tags.append("tabletop")
        
        return tags


def ingest_pdf(pdf_path: Path, output_dir: Path, overwrite: bool = False) -> Path:
    """Ingest a PDF and generate YAML resource file"""
    logger.info(f"Processing: {pdf_path.name}")
    
    # Extract text
    extractor = PDFExtractor()
    text = extractor.extract_text(pdf_path)
    
    if not text or len(text) < 100:
        raise ValueError(f"Failed to extract meaningful text from {pdf_path}")
    
    logger.info(f"Extracted {len(text)} characters from PDF")
    
    # Parse text
    parser = RulebookParser(text, pdf_path.name)
    resource_data = parser.parse()
    
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
    
    args = parser.parse_args()
    
    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)
    
    # Process each PDF
    for pdf_path in args.pdf_paths:
        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            continue
        
        try:
            ingest_pdf(pdf_path, args.output, args.overwrite)
        except Exception as e:
            logger.error(f"Failed to process {pdf_path}: {e}", exc_info=True)


if __name__ == "__main__":
    main()

