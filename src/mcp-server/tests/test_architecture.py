"""
Tests for chainguard.architecture module.

Tests architecture pattern detection and framework recognition.
"""

import pytest
import tempfile
from pathlib import Path


class TestArchitecturePattern:
    """Tests for ArchitecturePattern enum."""

    def test_import(self):
        """Test that ArchitecturePattern can be imported."""
        from chainguard.architecture import ArchitecturePattern
        assert ArchitecturePattern is not None

    def test_enum_values(self):
        """Test that all expected patterns exist."""
        from chainguard.architecture import ArchitecturePattern

        assert ArchitecturePattern.MVC.value == "mvc"
        assert ArchitecturePattern.MVVM.value == "mvvm"
        assert ArchitecturePattern.CLEAN.value == "clean_architecture"
        assert ArchitecturePattern.HEXAGONAL.value == "hexagonal"
        assert ArchitecturePattern.LAYERED.value == "layered"
        assert ArchitecturePattern.API_FIRST.value == "api_first"
        assert ArchitecturePattern.UNKNOWN.value == "unknown"


class TestFrameworkType:
    """Tests for FrameworkType enum."""

    def test_import(self):
        """Test that FrameworkType can be imported."""
        from chainguard.architecture import FrameworkType
        assert FrameworkType is not None

    def test_php_frameworks(self):
        """Test PHP framework types."""
        from chainguard.architecture import FrameworkType

        assert FrameworkType.LARAVEL.value == "laravel"
        assert FrameworkType.SYMFONY.value == "symfony"
        assert FrameworkType.WORDPRESS.value == "wordpress"

    def test_python_frameworks(self):
        """Test Python framework types."""
        from chainguard.architecture import FrameworkType

        assert FrameworkType.DJANGO.value == "django"
        assert FrameworkType.FLASK.value == "flask"
        assert FrameworkType.FASTAPI.value == "fastapi"

    def test_js_frameworks(self):
        """Test JavaScript framework types."""
        from chainguard.architecture import FrameworkType

        assert FrameworkType.REACT.value == "react"
        assert FrameworkType.VUE.value == "vue"
        assert FrameworkType.ANGULAR.value == "angular"
        assert FrameworkType.NEXTJS.value == "nextjs"
        assert FrameworkType.EXPRESS.value == "express"


class TestArchitectureAnalysis:
    """Tests for ArchitectureAnalysis dataclass."""

    def test_create_analysis(self):
        """Test creating an ArchitectureAnalysis."""
        from chainguard.architecture import ArchitectureAnalysis, ArchitecturePattern, FrameworkType

        analysis = ArchitectureAnalysis(
            pattern=ArchitecturePattern.MVC,
            confidence=0.85,
            framework=FrameworkType.LARAVEL,
            detected_layers=["Models", "Controllers", "Views"],
            detected_patterns=["Repository", "Service"],
        )

        assert analysis.pattern == ArchitecturePattern.MVC
        assert analysis.confidence == 0.85
        assert analysis.framework == FrameworkType.LARAVEL
        assert "Models" in analysis.detected_layers

    def test_to_dict(self):
        """Test ArchitectureAnalysis.to_dict()."""
        from chainguard.architecture import ArchitectureAnalysis, ArchitecturePattern

        analysis = ArchitectureAnalysis(
            pattern=ArchitecturePattern.LAYERED,
            confidence=0.7,
            detected_layers=["services", "repositories"],
        )

        d = analysis.to_dict()
        assert d["pattern"] == "layered"
        assert d["confidence"] == 0.7
        assert d["framework"] is None

    def test_to_summary(self):
        """Test generating summary text."""
        from chainguard.architecture import ArchitectureAnalysis, ArchitecturePattern, FrameworkType

        analysis = ArchitectureAnalysis(
            pattern=ArchitecturePattern.MVC,
            confidence=0.9,
            framework=FrameworkType.DJANGO,
            detected_layers=["models", "views"],
        )

        summary = analysis.to_summary()
        assert "mvc" in summary.lower()
        assert "django" in summary.lower()
        assert "90%" in summary


class TestDirectoryPatterns:
    """Tests for DIRECTORY_PATTERNS constant."""

    def test_patterns_defined(self):
        """Test that directory patterns are defined."""
        from chainguard.architecture import DIRECTORY_PATTERNS, ArchitecturePattern

        assert ArchitecturePattern.MVC in DIRECTORY_PATTERNS
        assert ArchitecturePattern.CLEAN in DIRECTORY_PATTERNS
        assert ArchitecturePattern.LAYERED in DIRECTORY_PATTERNS

    def test_mvc_patterns(self):
        """Test MVC directory patterns."""
        from chainguard.architecture import DIRECTORY_PATTERNS, ArchitecturePattern

        mvc_patterns = DIRECTORY_PATTERNS[ArchitecturePattern.MVC]
        assert any("model" in p.lower() for p in mvc_patterns)
        assert any("view" in p.lower() for p in mvc_patterns)
        assert any("controller" in p.lower() for p in mvc_patterns)


class TestFrameworkPatterns:
    """Tests for FRAMEWORK_PATTERNS constant."""

    def test_patterns_defined(self):
        """Test that framework patterns are defined."""
        from chainguard.architecture import FRAMEWORK_PATTERNS, FrameworkType

        assert FrameworkType.LARAVEL in FRAMEWORK_PATTERNS
        assert FrameworkType.DJANGO in FRAMEWORK_PATTERNS
        assert FrameworkType.REACT in FRAMEWORK_PATTERNS

    def test_laravel_patterns(self):
        """Test Laravel detection patterns."""
        from chainguard.architecture import FRAMEWORK_PATTERNS, FrameworkType

        patterns = FRAMEWORK_PATTERNS[FrameworkType.LARAVEL]
        assert "artisan" in patterns.get("files", [])
        assert "app/Http" in patterns.get("dirs", []) or "app/Models" in patterns.get("dirs", [])


class TestArchitectureDetector:
    """Tests for ArchitectureDetector class."""

    def test_import(self):
        """Test that ArchitectureDetector can be imported."""
        from chainguard.architecture import ArchitectureDetector
        assert ArchitectureDetector is not None

    def test_create_detector(self):
        """Test creating an ArchitectureDetector."""
        from chainguard.architecture import ArchitectureDetector

        detector = ArchitectureDetector()
        assert detector is not None

    def test_global_detector_exists(self):
        """Test that global architecture_detector instance exists."""
        from chainguard.architecture import architecture_detector

        assert architecture_detector is not None

    def test_analyze_empty_directory(self):
        """Test analyzing empty directory."""
        from chainguard.architecture import ArchitectureDetector, ArchitecturePattern

        detector = ArchitectureDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            analysis = detector.analyze(tmpdir)

            assert analysis.pattern in [ArchitecturePattern.UNKNOWN, ArchitecturePattern.LAYERED]
            assert analysis.confidence <= 0.5

    def test_analyze_nonexistent_directory(self):
        """Test analyzing nonexistent directory."""
        from chainguard.architecture import ArchitectureDetector, ArchitecturePattern

        detector = ArchitectureDetector()
        analysis = detector.analyze("/nonexistent/path/12345")

        assert analysis.pattern == ArchitecturePattern.UNKNOWN
        assert analysis.confidence == 0.0

    def test_analyze_mvc_structure(self):
        """Test detecting MVC structure."""
        from chainguard.architecture import ArchitectureDetector, ArchitecturePattern

        detector = ArchitectureDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create MVC-like structure
            Path(tmpdir, "models").mkdir()
            Path(tmpdir, "views").mkdir()
            Path(tmpdir, "controllers").mkdir()

            analysis = detector.analyze(tmpdir)

            assert analysis.pattern == ArchitecturePattern.MVC
            assert analysis.confidence > 0.0

    def test_analyze_layered_structure(self):
        """Test detecting layered structure."""
        from chainguard.architecture import ArchitectureDetector, ArchitecturePattern

        detector = ArchitectureDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create layered structure
            Path(tmpdir, "services").mkdir()
            Path(tmpdir, "repositories").mkdir()
            Path(tmpdir, "entities").mkdir()

            analysis = detector.analyze(tmpdir)

            assert analysis.pattern in [ArchitecturePattern.LAYERED, ArchitecturePattern.MVC]

    def test_analyze_api_first_structure(self):
        """Test detecting API-first structure."""
        from chainguard.architecture import ArchitectureDetector, ArchitecturePattern

        detector = ArchitectureDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create API-first structure
            Path(tmpdir, "api").mkdir()
            Path(tmpdir, "api/v1").mkdir()
            Path(tmpdir, "routes").mkdir()
            Path(tmpdir, "handlers").mkdir()

            analysis = detector.analyze(tmpdir)

            assert analysis.pattern in [ArchitecturePattern.API_FIRST, ArchitecturePattern.LAYERED]

    def test_detect_laravel_framework(self):
        """Test detecting Laravel framework."""
        from chainguard.architecture import ArchitectureDetector, FrameworkType

        detector = ArchitectureDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Laravel-like structure
            Path(tmpdir, "artisan").touch()
            Path(tmpdir, "composer.json").write_text('{"require": {"laravel/framework": "^10.0"}}')
            Path(tmpdir, "app").mkdir()
            Path(tmpdir, "app/Http").mkdir()
            Path(tmpdir, "app/Models").mkdir()
            Path(tmpdir, "resources").mkdir()
            Path(tmpdir, "resources/views").mkdir()

            analysis = detector.analyze(tmpdir)

            assert analysis.framework == FrameworkType.LARAVEL

    def test_detect_react_framework(self):
        """Test detecting React framework."""
        from chainguard.architecture import ArchitectureDetector, FrameworkType

        detector = ArchitectureDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create React-like structure
            Path(tmpdir, "package.json").write_text('{"dependencies": {"react": "^18.0"}}')
            Path(tmpdir, "src").mkdir()
            Path(tmpdir, "src/components").mkdir()
            Path(tmpdir, "public").mkdir()

            analysis = detector.analyze(tmpdir)

            assert analysis.framework == FrameworkType.REACT

    def test_detect_design_patterns(self):
        """Test detecting design patterns from file names."""
        from chainguard.architecture import ArchitectureDetector

        detector = ArchitectureDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with pattern names
            Path(tmpdir, "src").mkdir()
            Path(tmpdir, "src/UserRepository.py").touch()
            Path(tmpdir, "src/UserService.py").touch()
            Path(tmpdir, "src/UserFactory.py").touch()
            Path(tmpdir, "src/UserController.py").touch()

            analysis = detector.analyze(tmpdir)

            assert "Repository" in analysis.detected_patterns
            assert "Service" in analysis.detected_patterns
            assert "Factory" in analysis.detected_patterns

    def test_cache_behavior(self):
        """Test that analyzer caches results."""
        from chainguard.architecture import ArchitectureDetector

        detector = ArchitectureDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # First analysis
            analysis1 = detector.analyze(tmpdir)

            # Second analysis (should be cached)
            analysis2 = detector.analyze(tmpdir)

            assert analysis1.pattern == analysis2.pattern
            assert analysis1.confidence == analysis2.confidence

    def test_clear_cache(self):
        """Test clearing the cache."""
        from chainguard.architecture import ArchitectureDetector

        detector = ArchitectureDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            detector.analyze(tmpdir)
            assert tmpdir in detector._cache

            detector.clear_cache(tmpdir)
            assert tmpdir not in detector._cache

    def test_generate_suggestions(self):
        """Test generating architecture suggestions."""
        from chainguard.architecture import ArchitectureDetector

        detector = ArchitectureDetector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal structure (no tests)
            Path(tmpdir, "src").mkdir()
            Path(tmpdir, "src/app.py").touch()

            analysis = detector.analyze(tmpdir)

            # Should suggest adding tests
            assert any("test" in s.lower() for s in analysis.suggestions)


class TestProjectStructure:
    """Tests for ProjectStructure dataclass."""

    def test_import(self):
        """Test that ProjectStructure can be imported."""
        from chainguard.architecture import ProjectStructure
        assert ProjectStructure is not None

    def test_create_structure(self):
        """Test creating a ProjectStructure."""
        from chainguard.architecture import ProjectStructure

        structure = ProjectStructure(
            root_path="/project",
            directories=["src", "tests"],
            files=["main.py", "setup.py"],
            languages={"python": 10, "javascript": 5}
        )

        assert structure.root_path == "/project"
        assert "src" in structure.directories
        assert structure.languages["python"] == 10
