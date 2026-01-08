"""
CHAINGUARD MCP Server - Docstring Parser Module

Parses Python docstrings in various formats and extracts structured information.

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.

Supported Formats:
- Google Style (most common in modern Python)
- NumPy Style (common in scientific Python)
- reStructuredText/Sphinx Style (older standard)
- Raises (exception type, description)
- Examples (code examples)
- Attributes (for classes)
- Notes, Warnings, See Also
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import re


# =============================================================================
# Data Classes
# =============================================================================

class DocstringStyle(str, Enum):
    """Detected docstring style."""
    GOOGLE = "google"
    NUMPY = "numpy"
    RST = "restructuredtext"
    PLAIN = "plain"
    UNKNOWN = "unknown"


@dataclass
class ParamInfo:
    """Information about a function parameter."""
    name: str
    type_hint: str = ""
    description: str = ""
    default: str = ""
    optional: bool = False

    def to_string(self) -> str:
        """Convert to readable string."""
        parts = [self.name]
        if self.type_hint:
            parts.append(f"({self.type_hint})")
        if self.description:
            parts.append(f": {self.description}")
        if self.optional:
            parts.append("[optional]")
        return " ".join(parts)


@dataclass
class ReturnInfo:
    """Information about return value."""
    type_hint: str = ""
    description: str = ""

    def to_string(self) -> str:
        """Convert to readable string."""
        parts = []
        if self.type_hint:
            parts.append(self.type_hint)
        if self.description:
            parts.append(self.description)
        return ": ".join(parts) if parts else ""


@dataclass
class RaisesInfo:
    """Information about raised exceptions."""
    exception_type: str
    description: str = ""

    def to_string(self) -> str:
        """Convert to readable string."""
        if self.description:
            return f"{self.exception_type}: {self.description}"
        return self.exception_type


@dataclass
class ParsedDocstring:
    """Fully parsed docstring with all extracted information."""
    raw: str = ""
    style: DocstringStyle = DocstringStyle.UNKNOWN
    summary: str = ""
    description: str = ""
    params: List[ParamInfo] = field(default_factory=list)
    returns: Optional[ReturnInfo] = None
    yields: Optional[ReturnInfo] = None
    raises: List[RaisesInfo] = field(default_factory=list)
    attributes: List[ParamInfo] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    notes: str = ""
    warnings: str = ""
    see_also: List[str] = field(default_factory=list)
    deprecated: str = ""

    def to_memory_content(self) -> str:
        """
        Generate rich content for memory storage.

        Creates a searchable, semantic description that captures
        the full meaning of the documented code.
        """
        parts = []

        # Summary is most important
        if self.summary:
            parts.append(self.summary)

        # Extended description (truncated)
        if self.description:
            desc = self.description[:300]
            if len(self.description) > 300:
                desc += "..."
            parts.append(desc)

        # Parameters with descriptions
        if self.params:
            param_strs = []
            for p in self.params[:5]:  # Limit to 5 params
                if p.description:
                    param_strs.append(f"{p.name}: {p.description[:100]}")
                else:
                    param_strs.append(p.name)
            parts.append(f"Parameters: {', '.join(param_strs)}")

        # Return value
        if self.returns and (self.returns.type_hint or self.returns.description):
            ret_str = self.returns.to_string()
            if ret_str:
                parts.append(f"Returns: {ret_str[:150]}")

        # Exceptions
        if self.raises:
            raise_strs = [r.exception_type for r in self.raises[:3]]
            parts.append(f"Raises: {', '.join(raise_strs)}")

        # Deprecation warning (important!)
        if self.deprecated:
            parts.append(f"DEPRECATED: {self.deprecated[:100]}")

        return ". ".join(parts)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "style": self.style.value,
            "summary": self.summary,
            "description": self.description[:500] if self.description else "",
            "params": [{"name": p.name, "type": p.type_hint, "desc": p.description}
                      for p in self.params],
            "returns": {"type": self.returns.type_hint, "desc": self.returns.description}
                      if self.returns else None,
            "raises": [{"type": r.exception_type, "desc": r.description}
                      for r in self.raises],
            "deprecated": self.deprecated,
        }

    def is_empty(self) -> bool:
        """Check if docstring has any meaningful content."""
        return not (self.summary or self.description or self.params or
                   self.returns or self.raises)


# =============================================================================
# Parser Implementation
# =============================================================================

class DocstringParser:
    """
    Multi-format docstring parser.

    Auto-detects the docstring style and extracts structured information.
    """

    # Regex patterns for style detection (allow leading whitespace)
    GOOGLE_SECTION_PATTERN = re.compile(
        r'^\s*(Args|Arguments|Parameters|Params|Returns|Return|Yields|Yield|'
        r'Raises|Raise|Attributes|Example|Examples|Note|Notes|Warning|'
        r'Warnings|See Also|References|Todo):?\s*$',
        re.MULTILINE | re.IGNORECASE
    )

    NUMPY_SECTION_PATTERN = re.compile(
        r'^\s*(Parameters|Returns|Yields|Raises|Attributes|Examples|Notes|'
        r'Warnings|See Also|References)\s*\n\s*[-=]+\s*$',
        re.MULTILINE
    )

    RST_PATTERN = re.compile(
        r':(?:param|type|returns|rtype|raises|var|ivar|cvar)\s',
        re.MULTILINE
    )

    @classmethod
    def parse(cls, docstring: str) -> ParsedDocstring:
        """
        Parse a docstring and extract structured information.

        Args:
            docstring: The raw docstring text.

        Returns:
            ParsedDocstring with all extracted information.
        """
        if not docstring or not docstring.strip():
            return ParsedDocstring()

        # Clean up the docstring
        docstring = cls._clean_docstring(docstring)

        # Detect style
        style = cls._detect_style(docstring)

        # Parse based on style
        if style == DocstringStyle.GOOGLE:
            result = cls._parse_google(docstring)
        elif style == DocstringStyle.NUMPY:
            result = cls._parse_numpy(docstring)
        elif style == DocstringStyle.RST:
            result = cls._parse_rst(docstring)
        else:
            result = cls._parse_plain(docstring)

        result.raw = docstring
        result.style = style
        return result

    @classmethod
    def _clean_docstring(cls, docstring: str) -> str:
        """Clean and normalize docstring."""
        # Remove leading/trailing quotes if present
        docstring = docstring.strip()
        if docstring.startswith('"""') or docstring.startswith("'''"):
            docstring = docstring[3:]
        if docstring.endswith('"""') or docstring.endswith("'''"):
            docstring = docstring[:-3]

        # Normalize whitespace
        lines = docstring.split('\n')

        # Find minimum indentation (excluding empty lines)
        min_indent = float('inf')
        for line in lines[1:]:  # Skip first line
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                min_indent = min(min_indent, indent)

        # Remove common indentation
        if min_indent < float('inf'):
            cleaned_lines = [lines[0]]  # First line as-is
            for line in lines[1:]:
                if line.strip():
                    cleaned_lines.append(line[min_indent:] if len(line) >= min_indent else line)
                else:
                    cleaned_lines.append('')
            docstring = '\n'.join(cleaned_lines)

        return docstring.strip()

    @classmethod
    def _detect_style(cls, docstring: str) -> DocstringStyle:
        """Detect the docstring style."""
        # Check for NumPy style (sections with underlines)
        if cls.NUMPY_SECTION_PATTERN.search(docstring):
            return DocstringStyle.NUMPY

        # Check for reStructuredText style
        if cls.RST_PATTERN.search(docstring):
            return DocstringStyle.RST

        # Check for Google style (section headers)
        if cls.GOOGLE_SECTION_PATTERN.search(docstring):
            return DocstringStyle.GOOGLE

        # Default to plain
        return DocstringStyle.PLAIN

    @classmethod
    def _parse_google(cls, docstring: str) -> ParsedDocstring:
        """Parse Google-style docstring."""
        result = ParsedDocstring()

        # Split into sections
        sections = cls._split_google_sections(docstring)

        # Extract summary and description from preamble
        if 'preamble' in sections:
            result.summary, result.description = cls._extract_summary_desc(sections['preamble'])

        # Parse Args/Parameters
        for key in ['args', 'arguments', 'parameters', 'params']:
            if key in sections:
                result.params = cls._parse_google_params(sections[key])
                break

        # Parse Returns
        for key in ['returns', 'return']:
            if key in sections:
                result.returns = cls._parse_google_returns(sections[key])
                break

        # Parse Yields
        for key in ['yields', 'yield']:
            if key in sections:
                result.yields = cls._parse_google_returns(sections[key])
                break

        # Parse Raises
        for key in ['raises', 'raise']:
            if key in sections:
                result.raises = cls._parse_google_raises(sections[key])
                break

        # Parse Attributes
        if 'attributes' in sections:
            result.attributes = cls._parse_google_params(sections['attributes'])

        # Parse Examples
        for key in ['example', 'examples']:
            if key in sections:
                result.examples = [sections[key].strip()]
                break

        # Parse Notes
        for key in ['note', 'notes']:
            if key in sections:
                result.notes = sections[key].strip()
                break

        # Parse Warnings
        for key in ['warning', 'warnings']:
            if key in sections:
                result.warnings = sections[key].strip()
                break

        return result

    @classmethod
    def _split_google_sections(cls, docstring: str) -> Dict[str, str]:
        """Split docstring into Google-style sections."""
        sections = {}
        current_section = 'preamble'
        current_content = []

        lines = docstring.split('\n')

        for line in lines:
            # Check if this is a section header
            stripped = line.strip()
            header_match = re.match(r'^(Args|Arguments|Parameters|Params|Returns|Return|'
                                   r'Yields|Yield|Raises|Raise|Attributes|Example|Examples|'
                                   r'Note|Notes|Warning|Warnings|See Also|Todo):?\s*$',
                                   stripped, re.IGNORECASE)

            if header_match:
                # Save previous section
                if current_content:
                    sections[current_section.lower()] = '\n'.join(current_content)

                # Start new section
                current_section = header_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section.lower()] = '\n'.join(current_content)

        return sections

    @classmethod
    def _parse_google_params(cls, section: str) -> List[ParamInfo]:
        """Parse Google-style parameter section."""
        params = []
        current_param = None
        current_desc = []

        # Find the base indentation of the section
        lines = section.split('\n')
        base_indent = float('inf')
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                base_indent = min(base_indent, indent)
        if base_indent == float('inf'):
            base_indent = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Calculate relative indentation
            current_indent = len(line) - len(line.lstrip())
            relative_indent = current_indent - base_indent

            # Check for parameter definition: "name (type): description" or "name: description"
            param_match = re.match(r'^(\w+)\s*(?:\(([^)]+)\))?\s*:\s*(.*)$', stripped)

            # New param if at base indentation and matches pattern
            if param_match and relative_indent <= 0:
                # Save previous param
                if current_param:
                    current_param.description = ' '.join(current_desc).strip()
                    params.append(current_param)

                # Start new param
                name = param_match.group(1)
                type_hint = param_match.group(2) or ""
                desc_start = param_match.group(3) or ""

                optional = 'optional' in type_hint.lower() if type_hint else False
                current_param = ParamInfo(name=name, type_hint=type_hint, optional=optional)
                current_desc = [desc_start] if desc_start else []
            elif current_param and relative_indent > 0:
                # Continuation of description (indented more than base)
                current_desc.append(stripped)

        # Save last param
        if current_param:
            current_param.description = ' '.join(current_desc).strip()
            params.append(current_param)

        return params

    @classmethod
    def _parse_google_returns(cls, section: str) -> ReturnInfo:
        """Parse Google-style returns section."""
        lines = [l.strip() for l in section.split('\n') if l.strip()]
        if not lines:
            return ReturnInfo()

        # Check for "type: description" format
        first_line = lines[0]
        type_match = re.match(r'^(\w[\w\[\], ]*?):\s*(.*)$', first_line)

        if type_match:
            type_hint = type_match.group(1)
            desc_parts = [type_match.group(2)] + lines[1:]
            description = ' '.join(desc_parts).strip()
        else:
            type_hint = ""
            description = ' '.join(lines).strip()

        return ReturnInfo(type_hint=type_hint, description=description)

    @classmethod
    def _parse_google_raises(cls, section: str) -> List[RaisesInfo]:
        """Parse Google-style raises section."""
        raises = []
        current_exc = None
        current_desc = []

        # Find the base indentation of the section
        lines = section.split('\n')
        base_indent = float('inf')
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                base_indent = min(base_indent, indent)
        if base_indent == float('inf'):
            base_indent = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Calculate relative indentation
            current_indent = len(line) - len(line.lstrip())
            relative_indent = current_indent - base_indent

            # Check for exception definition: "ExceptionType: description"
            exc_match = re.match(r'^(\w+(?:\.\w+)?)\s*:\s*(.*)$', stripped)

            if exc_match and relative_indent <= 0:
                # Save previous
                if current_exc:
                    current_exc.description = ' '.join(current_desc).strip()
                    raises.append(current_exc)

                # Start new
                current_exc = RaisesInfo(exception_type=exc_match.group(1))
                current_desc = [exc_match.group(2)] if exc_match.group(2) else []
            elif current_exc and relative_indent > 0:
                current_desc.append(stripped)

        # Save last
        if current_exc:
            current_exc.description = ' '.join(current_desc).strip()
            raises.append(current_exc)

        return raises

    @classmethod
    def _parse_numpy(cls, docstring: str) -> ParsedDocstring:
        """Parse NumPy-style docstring."""
        result = ParsedDocstring()

        # Split into sections based on underlined headers
        sections = cls._split_numpy_sections(docstring)

        # Extract summary and description
        if 'preamble' in sections:
            result.summary, result.description = cls._extract_summary_desc(sections['preamble'])

        # Parse Parameters
        if 'parameters' in sections:
            result.params = cls._parse_numpy_params(sections['parameters'])

        # Parse Returns
        if 'returns' in sections:
            result.returns = cls._parse_numpy_returns(sections['returns'])

        # Parse Yields
        if 'yields' in sections:
            result.yields = cls._parse_numpy_returns(sections['yields'])

        # Parse Raises
        if 'raises' in sections:
            result.raises = cls._parse_numpy_raises(sections['raises'])

        # Parse Attributes
        if 'attributes' in sections:
            result.attributes = cls._parse_numpy_params(sections['attributes'])

        # Parse Examples
        if 'examples' in sections:
            result.examples = [sections['examples'].strip()]

        # Parse Notes
        if 'notes' in sections:
            result.notes = sections['notes'].strip()

        return result

    @classmethod
    def _split_numpy_sections(cls, docstring: str) -> Dict[str, str]:
        """Split docstring into NumPy-style sections."""
        sections = {}
        current_section = 'preamble'
        current_content = []

        lines = docstring.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Check if next line is underline (indicates section header)
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if stripped and re.match(r'^[-=]+$', next_line) and len(next_line) >= len(stripped):
                    # This is a section header
                    if current_content:
                        sections[current_section.lower()] = '\n'.join(current_content)

                    current_section = stripped
                    current_content = []
                    i += 2  # Skip header and underline
                    continue

            current_content.append(line)
            i += 1

        # Save last section
        if current_content:
            sections[current_section.lower()] = '\n'.join(current_content)

        return sections

    @classmethod
    def _parse_numpy_params(cls, section: str) -> List[ParamInfo]:
        """Parse NumPy-style parameter section."""
        params = []
        current_param = None
        current_desc = []

        for line in section.split('\n'):
            stripped = line.strip()
            if not stripped:
                if current_desc:
                    current_desc.append('')
                continue

            # Check for parameter definition: "name : type" or just "name"
            param_match = re.match(r'^(\w+)\s*(?::\s*(.+))?$', stripped)

            if param_match and not line.startswith('    '):
                # Save previous param
                if current_param:
                    current_param.description = ' '.join(current_desc).strip()
                    params.append(current_param)

                # Start new param
                name = param_match.group(1)
                type_hint = param_match.group(2) or ""

                optional = 'optional' in type_hint.lower() if type_hint else False
                current_param = ParamInfo(name=name, type_hint=type_hint, optional=optional)
                current_desc = []
            elif current_param and line.startswith('    '):
                # Description line
                current_desc.append(stripped)

        # Save last param
        if current_param:
            current_param.description = ' '.join(current_desc).strip()
            params.append(current_param)

        return params

    @classmethod
    def _parse_numpy_returns(cls, section: str) -> ReturnInfo:
        """Parse NumPy-style returns section."""
        lines = section.split('\n')
        type_hint = ""
        desc_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            if i == 0 or (not line.startswith('    ') and ':' not in stripped):
                # Type line
                type_hint = stripped
            elif line.startswith('    '):
                # Description line
                desc_lines.append(stripped)

        return ReturnInfo(type_hint=type_hint, description=' '.join(desc_lines).strip())

    @classmethod
    def _parse_numpy_raises(cls, section: str) -> List[RaisesInfo]:
        """Parse NumPy-style raises section."""
        raises = []
        current_exc = None
        current_desc = []

        for line in section.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue

            if not line.startswith('    '):
                # Exception type
                if current_exc:
                    current_exc.description = ' '.join(current_desc).strip()
                    raises.append(current_exc)

                current_exc = RaisesInfo(exception_type=stripped)
                current_desc = []
            else:
                # Description
                current_desc.append(stripped)

        if current_exc:
            current_exc.description = ' '.join(current_desc).strip()
            raises.append(current_exc)

        return raises

    @classmethod
    def _parse_rst(cls, docstring: str) -> ParsedDocstring:
        """Parse reStructuredText/Sphinx-style docstring."""
        result = ParsedDocstring()

        # Extract summary and description (everything before first :param/:returns/etc)
        rst_start = re.search(r':(?:param|type|returns|rtype|raises|var|ivar|cvar)\s', docstring)
        if rst_start:
            preamble = docstring[:rst_start.start()]
            result.summary, result.description = cls._extract_summary_desc(preamble)
        else:
            result.summary, result.description = cls._extract_summary_desc(docstring)
            return result

        # Extract parameters
        result.params = cls._parse_rst_params(docstring)

        # Extract returns
        result.returns = cls._parse_rst_returns(docstring)

        # Extract raises
        result.raises = cls._parse_rst_raises(docstring)

        return result

    @classmethod
    def _parse_rst_params(cls, docstring: str) -> List[ParamInfo]:
        """Parse reStructuredText parameter definitions."""
        params = {}

        # Extract :param name: description
        for match in re.finditer(r':param\s+(\w+):\s*([^\n:]+(?:\n(?!\s*:)[^\n]+)*)', docstring):
            name = match.group(1)
            desc = ' '.join(match.group(2).split())
            if name not in params:
                params[name] = ParamInfo(name=name)
            params[name].description = desc

        # Extract :type name: type
        for match in re.finditer(r':type\s+(\w+):\s*([^\n]+)', docstring):
            name = match.group(1)
            type_hint = match.group(2).strip()
            if name not in params:
                params[name] = ParamInfo(name=name)
            params[name].type_hint = type_hint

        return list(params.values())

    @classmethod
    def _parse_rst_returns(cls, docstring: str) -> Optional[ReturnInfo]:
        """Parse reStructuredText returns definition."""
        # Extract :returns: description
        returns_match = re.search(r':returns?:\s*([^\n:]+(?:\n(?!\s*:)[^\n]+)*)', docstring)
        desc = ' '.join(returns_match.group(1).split()) if returns_match else ""

        # Extract :rtype: type
        rtype_match = re.search(r':rtype:\s*([^\n]+)', docstring)
        type_hint = rtype_match.group(1).strip() if rtype_match else ""

        if desc or type_hint:
            return ReturnInfo(type_hint=type_hint, description=desc)
        return None

    @classmethod
    def _parse_rst_raises(cls, docstring: str) -> List[RaisesInfo]:
        """Parse reStructuredText raises definitions."""
        raises = []

        # Extract :raises ExceptionType: description
        for match in re.finditer(r':raises?\s+(\w+(?:\.\w+)?):\s*([^\n:]+(?:\n(?!\s*:)[^\n]+)*)', docstring):
            exc_type = match.group(1)
            desc = ' '.join(match.group(2).split())
            raises.append(RaisesInfo(exception_type=exc_type, description=desc))

        return raises

    @classmethod
    def _parse_plain(cls, docstring: str) -> ParsedDocstring:
        """Parse plain/simple docstring (just text)."""
        result = ParsedDocstring()
        result.summary, result.description = cls._extract_summary_desc(docstring)
        return result

    @classmethod
    def _extract_summary_desc(cls, text: str) -> Tuple[str, str]:
        """Extract summary (first sentence/paragraph) and description."""
        text = text.strip()
        if not text:
            return "", ""

        # Split into paragraphs
        paragraphs = re.split(r'\n\s*\n', text)

        if not paragraphs:
            return "", ""

        # First paragraph is summary
        summary = ' '.join(paragraphs[0].split())

        # If summary is very long, try to extract first sentence
        if len(summary) > 200:
            # Find first sentence end
            sentence_end = re.search(r'[.!?]\s', summary)
            if sentence_end and sentence_end.start() < 200:
                summary = summary[:sentence_end.start() + 1]

        # Rest is description
        if len(paragraphs) > 1:
            description = '\n\n'.join(paragraphs[1:])
        else:
            description = ""

        return summary, description


# =============================================================================
# Convenience Functions
# =============================================================================

def parse_docstring(docstring: str) -> ParsedDocstring:
    """
    Parse a docstring and extract structured information.

    This is the main entry point for docstring parsing.

    Args:
        docstring: The raw docstring text.

    Returns:
        ParsedDocstring with all extracted information.

    Example:
        >>> doc = parse_docstring('''Calculate sum of numbers.
        ...
        ... Args:
        ...     a: First number.
        ...     b: Second number.
        ...
        ... Returns:
        ...     int: The sum of a and b.
        ... ''')
        >>> doc.summary
        'Calculate sum of numbers.'
        >>> doc.params[0].name
        'a'
    """
    return DocstringParser.parse(docstring)


def extract_docstring_from_code(code: str, start_line: int = 0) -> Optional[str]:
    """
    Extract docstring from code starting at a given line.

    Looks for triple-quoted string immediately following function/class definition.

    Args:
        code: Source code.
        start_line: Line number where function/class starts (0-indexed).

    Returns:
        The docstring if found, None otherwise.
    """
    lines = code.split('\n')

    # Look for docstring in the next few lines
    for i in range(start_line, min(start_line + 5, len(lines))):
        line = lines[i].strip()

        # Check for docstring start
        if line.startswith('"""') or line.startswith("'''"):
            quote = line[:3]

            # Single-line docstring
            if line.count(quote) >= 2 and line.endswith(quote) and len(line) > 6:
                return line[3:-3]

            # Multi-line docstring
            docstring_lines = [line[3:]]  # Remove opening quotes
            for j in range(i + 1, len(lines)):
                end_line = lines[j]
                if quote in end_line:
                    # Found closing quotes
                    idx = end_line.index(quote)
                    docstring_lines.append(end_line[:idx])
                    return '\n'.join(docstring_lines)
                else:
                    docstring_lines.append(end_line)

            # No closing found
            return None

    return None


# =============================================================================
# Global Parser Instance
# =============================================================================

docstring_parser = DocstringParser()
