"""
Tests for chainguard.docstring_parser module.

Tests docstring parsing for Google, NumPy, and reStructuredText formats.
"""

import pytest


class TestDocstringStyle:
    """Tests for DocstringStyle enum."""

    def test_import(self):
        """Test that DocstringStyle can be imported."""
        from chainguard.docstring_parser import DocstringStyle
        assert DocstringStyle is not None

    def test_enum_values(self):
        """Test all expected styles exist."""
        from chainguard.docstring_parser import DocstringStyle

        assert DocstringStyle.GOOGLE.value == "google"
        assert DocstringStyle.NUMPY.value == "numpy"
        assert DocstringStyle.RST.value == "restructuredtext"
        assert DocstringStyle.PLAIN.value == "plain"


class TestParamInfo:
    """Tests for ParamInfo dataclass."""

    def test_create_param(self):
        """Test creating a ParamInfo."""
        from chainguard.docstring_parser import ParamInfo

        param = ParamInfo(
            name="file_path",
            type_hint="str",
            description="Path to the file",
            optional=False
        )

        assert param.name == "file_path"
        assert param.type_hint == "str"
        assert param.description == "Path to the file"
        assert param.optional is False

    def test_to_string(self):
        """Test ParamInfo.to_string()."""
        from chainguard.docstring_parser import ParamInfo

        param = ParamInfo(
            name="count",
            type_hint="int",
            description="Number of items",
            optional=True
        )

        result = param.to_string()
        assert "count" in result
        assert "int" in result
        assert "Number of items" in result
        assert "optional" in result.lower()


class TestParsedDocstring:
    """Tests for ParsedDocstring dataclass."""

    def test_create_empty(self):
        """Test creating empty ParsedDocstring."""
        from chainguard.docstring_parser import ParsedDocstring

        doc = ParsedDocstring()
        assert doc.summary == ""
        assert doc.params == []
        assert doc.is_empty() is True

    def test_is_empty(self):
        """Test is_empty() method."""
        from chainguard.docstring_parser import ParsedDocstring

        empty = ParsedDocstring()
        assert empty.is_empty() is True

        with_summary = ParsedDocstring(summary="Hello")
        assert with_summary.is_empty() is False

    def test_to_memory_content(self):
        """Test to_memory_content() generates searchable text."""
        from chainguard.docstring_parser import ParsedDocstring, ParamInfo, ReturnInfo

        doc = ParsedDocstring(
            summary="Calculate the sum of two numbers.",
            params=[
                ParamInfo(name="a", type_hint="int", description="First number"),
                ParamInfo(name="b", type_hint="int", description="Second number"),
            ],
            returns=ReturnInfo(type_hint="int", description="The sum")
        )

        content = doc.to_memory_content()

        assert "Calculate the sum" in content
        assert "a:" in content or "a" in content
        assert "Returns" in content

    def test_to_dict(self):
        """Test to_dict() serialization."""
        from chainguard.docstring_parser import ParsedDocstring, DocstringStyle

        doc = ParsedDocstring(
            summary="Test function",
            style=DocstringStyle.GOOGLE
        )

        d = doc.to_dict()
        assert d["summary"] == "Test function"
        assert d["style"] == "google"


class TestGoogleStyleParsing:
    """Tests for Google-style docstring parsing."""

    def test_simple_google_docstring(self):
        """Test parsing simple Google-style docstring."""
        from chainguard.docstring_parser import parse_docstring, DocstringStyle

        docstring = """
        Calculate the sum of two numbers.

        Args:
            a: First number.
            b: Second number.

        Returns:
            int: The sum of a and b.
        """

        result = parse_docstring(docstring)

        assert result.style == DocstringStyle.GOOGLE
        assert "sum" in result.summary.lower()
        assert len(result.params) == 2
        assert result.params[0].name == "a"
        assert result.params[1].name == "b"
        assert result.returns is not None
        assert "int" in result.returns.type_hint.lower()

    def test_google_with_types(self):
        """Test Google-style with explicit types."""
        from chainguard.docstring_parser import parse_docstring

        docstring = """
        Process a file.

        Args:
            path (str): Path to the file.
            encoding (str, optional): File encoding.

        Returns:
            bool: True if successful.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If encoding is invalid.
        """

        result = parse_docstring(docstring)

        assert len(result.params) == 2
        assert result.params[0].name == "path"
        assert result.params[0].type_hint == "str"
        assert result.params[1].optional is True

        assert len(result.raises) == 2
        assert result.raises[0].exception_type == "FileNotFoundError"

    def test_google_with_examples(self):
        """Test Google-style with Examples section."""
        from chainguard.docstring_parser import parse_docstring

        docstring = """
        Add two numbers.

        Args:
            a: First number.
            b: Second number.

        Example:
            >>> add(1, 2)
            3
        """

        result = parse_docstring(docstring)

        assert len(result.examples) == 1
        assert "add(1, 2)" in result.examples[0]

    def test_google_multiline_description(self):
        """Test Google-style with multiline param descriptions."""
        from chainguard.docstring_parser import parse_docstring

        docstring = """
        Complex function.

        Args:
            config: Configuration dictionary that contains
                all settings for the operation including
                timeout and retry options.
        """

        result = parse_docstring(docstring)

        assert len(result.params) == 1
        assert "timeout" in result.params[0].description.lower()


class TestNumPyStyleParsing:
    """Tests for NumPy-style docstring parsing."""

    def test_simple_numpy_docstring(self):
        """Test parsing simple NumPy-style docstring."""
        from chainguard.docstring_parser import parse_docstring, DocstringStyle

        docstring = """
        Calculate the mean of an array.

        Parameters
        ----------
        values : array_like
            Input values.
        weights : array_like, optional
            Weights for each value.

        Returns
        -------
        float
            The weighted mean.
        """

        result = parse_docstring(docstring)

        assert result.style == DocstringStyle.NUMPY
        assert "mean" in result.summary.lower()
        assert len(result.params) == 2
        assert result.params[0].name == "values"
        assert "array_like" in result.params[0].type_hint
        assert result.returns is not None

    def test_numpy_with_raises(self):
        """Test NumPy-style with Raises section."""
        from chainguard.docstring_parser import parse_docstring

        docstring = """
        Divide two numbers.

        Parameters
        ----------
        a : float
            Dividend.
        b : float
            Divisor.

        Returns
        -------
        float
            Result of division.

        Raises
        ------
        ZeroDivisionError
            If b is zero.
        """

        result = parse_docstring(docstring)

        assert len(result.raises) == 1
        assert result.raises[0].exception_type == "ZeroDivisionError"


class TestRstStyleParsing:
    """Tests for reStructuredText/Sphinx-style docstring parsing."""

    def test_simple_rst_docstring(self):
        """Test parsing simple rST-style docstring."""
        from chainguard.docstring_parser import parse_docstring, DocstringStyle

        docstring = """
        Process a file and return contents.

        :param file_path: Path to the file.
        :type file_path: str
        :param encoding: File encoding.
        :returns: File contents.
        :rtype: str
        :raises FileNotFoundError: If file doesn't exist.
        """

        result = parse_docstring(docstring)

        assert result.style == DocstringStyle.RST
        assert len(result.params) == 2
        assert result.params[0].name == "file_path"
        assert result.params[0].type_hint == "str"
        assert result.returns is not None
        assert "str" in result.returns.type_hint
        assert len(result.raises) == 1

    def test_rst_without_types(self):
        """Test rST-style without explicit type definitions."""
        from chainguard.docstring_parser import parse_docstring

        docstring = """
        Simple function.

        :param name: User name.
        :returns: Greeting message.
        """

        result = parse_docstring(docstring)

        assert len(result.params) == 1
        assert result.params[0].name == "name"
        assert result.returns is not None


class TestPlainDocstring:
    """Tests for plain/simple docstring parsing."""

    def test_single_line_docstring(self):
        """Test parsing single-line docstring."""
        from chainguard.docstring_parser import parse_docstring, DocstringStyle

        result = parse_docstring("Return the current timestamp.")

        assert result.style == DocstringStyle.PLAIN
        assert "timestamp" in result.summary.lower()

    def test_multiline_plain_docstring(self):
        """Test parsing multiline plain docstring."""
        from chainguard.docstring_parser import parse_docstring

        docstring = """
        This is the summary line.

        This is a longer description that provides
        more details about the function.
        """

        result = parse_docstring(docstring)

        assert "summary" in result.summary.lower()
        assert "longer description" in result.description.lower()


class TestStyleDetection:
    """Tests for automatic style detection."""

    def test_detect_google_style(self):
        """Test detecting Google-style docstring."""
        from chainguard.docstring_parser import DocstringParser, DocstringStyle

        docstring = """
        Summary.

        Args:
            x: Value.
        """

        style = DocstringParser._detect_style(docstring)
        assert style == DocstringStyle.GOOGLE

    def test_detect_numpy_style(self):
        """Test detecting NumPy-style docstring."""
        from chainguard.docstring_parser import DocstringParser, DocstringStyle

        docstring = """
        Summary.

        Parameters
        ----------
        x : int
            Value.
        """

        style = DocstringParser._detect_style(docstring)
        assert style == DocstringStyle.NUMPY

    def test_detect_rst_style(self):
        """Test detecting rST-style docstring."""
        from chainguard.docstring_parser import DocstringParser, DocstringStyle

        docstring = """
        Summary.

        :param x: Value.
        """

        style = DocstringParser._detect_style(docstring)
        assert style == DocstringStyle.RST


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_docstring(self):
        """Test parsing empty docstring."""
        from chainguard.docstring_parser import parse_docstring

        result = parse_docstring("")
        assert result.is_empty() is True

        result = parse_docstring(None)
        assert result.is_empty() is True

    def test_whitespace_only_docstring(self):
        """Test parsing whitespace-only docstring."""
        from chainguard.docstring_parser import parse_docstring

        result = parse_docstring("   \n\n   ")
        assert result.is_empty() is True

    def test_docstring_with_quotes(self):
        """Test parsing docstring with triple quotes."""
        from chainguard.docstring_parser import parse_docstring

        docstring = '"""This is a test."""'
        result = parse_docstring(docstring)

        assert "test" in result.summary.lower()

    def test_very_long_docstring(self):
        """Test parsing very long docstring."""
        from chainguard.docstring_parser import parse_docstring

        long_desc = "This is a very long description. " * 100
        docstring = f"Summary.\n\n{long_desc}"

        result = parse_docstring(docstring)

        assert result.summary == "Summary."
        # Description should be truncated in to_memory_content
        content = result.to_memory_content()
        assert len(content) < 1000


class TestIntegration:
    """Integration tests with AST analyzer."""

    def test_codesymbol_with_docstring(self):
        """Test CodeSymbol uses parsed docstring."""
        from chainguard.ast_analyzer import CodeSymbol, SymbolType

        symbol = CodeSymbol(
            name="validate_file",
            type=SymbolType.FUNCTION,
            file_path="validators.py",
            line_start=10,
            line_end=20,
            docstring="""
            Validate a file's syntax.

            Args:
                file_path: Path to the file.
                strict: Enable strict mode.

            Returns:
                bool: True if valid.

            Raises:
                FileNotFoundError: If file missing.
            """
        )

        # Test parsed_docstring property
        parsed = symbol.parsed_docstring
        assert parsed is not None
        assert len(parsed.params) == 2
        assert parsed.returns is not None

        # Test to_memory_content uses parsed info
        content = symbol.to_memory_content()
        assert "validate" in content.lower()
        assert "file_path" in content or "Path to the file" in content

    def test_codesymbol_semantic_category(self):
        """Test semantic category inference."""
        from chainguard.ast_analyzer import CodeSymbol, SymbolType

        # Validation function
        sym = CodeSymbol(
            name="validate_json",
            type=SymbolType.FUNCTION,
            file_path="test.py",
            line_start=1,
            line_end=5
        )
        assert sym.get_semantic_category() == "validation"

        # Handler
        sym = CodeSymbol(
            name="handle_request",
            type=SymbolType.FUNCTION,
            file_path="test.py",
            line_start=1,
            line_end=5
        )
        assert sym.get_semantic_category() == "event_handler"

        # Manager class
        sym = CodeSymbol(
            name="ProjectManager",
            type=SymbolType.CLASS,
            file_path="test.py",
            line_start=1,
            line_end=50
        )
        assert sym.get_semantic_category() == "management"


class TestMemoryContent:
    """Tests for memory content generation."""

    def test_rich_memory_content(self):
        """Test that memory content is rich and searchable."""
        from chainguard.docstring_parser import ParsedDocstring, ParamInfo, ReturnInfo, RaisesInfo

        doc = ParsedDocstring(
            summary="Validates PHP syntax using external linter.",
            description="Runs php -l command and parses output.",
            params=[
                ParamInfo(name="file_path", type_hint="str",
                         description="Absolute path to PHP file to validate"),
            ],
            returns=ReturnInfo(type_hint="ValidationResult",
                              description="Contains valid flag and error details"),
            raises=[
                RaisesInfo(exception_type="FileNotFoundError",
                          description="If the file doesn't exist")
            ]
        )

        content = doc.to_memory_content()

        # Should be searchable
        assert "PHP" in content
        assert "syntax" in content.lower() or "linter" in content.lower()
        assert "file_path" in content or "path" in content.lower()
        assert "ValidationResult" in content
        assert "FileNotFoundError" in content

    def test_deprecated_in_content(self):
        """Test that deprecated warning appears in content."""
        from chainguard.docstring_parser import ParsedDocstring

        doc = ParsedDocstring(
            summary="Old function.",
            deprecated="Use new_function() instead."
        )

        content = doc.to_memory_content()
        assert "DEPRECATED" in content
        assert "new_function" in content
