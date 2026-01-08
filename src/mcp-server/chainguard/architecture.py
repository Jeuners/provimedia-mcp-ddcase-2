"""
CHAINGUARD MCP Server - Architecture Detection Module

Automatic detection of architectural patterns in codebases.

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.

Detection is based on:
- Directory structure
- File naming conventions
- Class/interface patterns
- Import relationships
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Tuple
from pathlib import Path
from enum import Enum
import re

from .config import logger


# =============================================================================
# Architecture Patterns
# =============================================================================

class ArchitecturePattern(str, Enum):
    """Recognized architectural patterns."""
    MVC = "mvc"
    MVVM = "mvvm"
    CLEAN = "clean_architecture"
    HEXAGONAL = "hexagonal"
    MICROSERVICES = "microservices"
    MODULAR_MONOLITH = "modular_monolith"
    LAYERED = "layered"
    API_FIRST = "api_first"
    EVENT_DRIVEN = "event_driven"
    UNKNOWN = "unknown"


class FrameworkType(str, Enum):
    """Detected framework types."""
    # PHP
    LARAVEL = "laravel"
    SYMFONY = "symfony"
    CODEIGNITER = "codeigniter"
    WORDPRESS = "wordpress"
    # Python
    DJANGO = "django"
    FLASK = "flask"
    FASTAPI = "fastapi"
    # JavaScript
    REACT = "react"
    VUE = "vue"
    ANGULAR = "angular"
    NEXTJS = "nextjs"
    NUXT = "nuxt"
    EXPRESS = "express"
    NESTJS = "nestjs"
    # Go
    GIN = "gin"
    ECHO = "echo"
    # Rust
    ACTIX = "actix"
    AXUM = "axum"
    # Generic
    UNKNOWN = "unknown"


# =============================================================================
# Detection Patterns
# =============================================================================

# Directory patterns that indicate architecture
DIRECTORY_PATTERNS: Dict[ArchitecturePattern, List[str]] = {
    ArchitecturePattern.MVC: [
        "models", "views", "controllers",
        "Models", "Views", "Controllers",
        "app/Models", "app/Controllers", "resources/views",
    ],
    ArchitecturePattern.MVVM: [
        "viewmodels", "ViewModels",
        "view-models", "view_models",
    ],
    ArchitecturePattern.CLEAN: [
        "domain", "application", "infrastructure", "presentation",
        "entities", "use_cases", "usecases", "use-cases",
        "core", "adapters", "ports",
    ],
    ArchitecturePattern.HEXAGONAL: [
        "ports", "adapters",
        "inbound", "outbound",
        "driving", "driven",
    ],
    ArchitecturePattern.LAYERED: [
        "services", "repositories", "entities",
        "Services", "Repositories", "Entities",
        "business", "data", "presentation",
    ],
    ArchitecturePattern.API_FIRST: [
        "api", "routes", "endpoints",
        "handlers", "resources",
        "v1", "v2",
    ],
}

# Framework detection patterns
FRAMEWORK_PATTERNS: Dict[FrameworkType, Dict[str, Any]] = {
    FrameworkType.LARAVEL: {
        "files": ["artisan", "composer.json"],
        "dirs": ["app/Http", "app/Models", "resources/views", "database/migrations"],
        "content": {"composer.json": "laravel/framework"},
    },
    FrameworkType.SYMFONY: {
        "files": ["symfony.lock", "composer.json"],
        "dirs": ["src/Controller", "src/Entity", "config/packages"],
        "content": {"composer.json": "symfony/framework-bundle"},
    },
    FrameworkType.DJANGO: {
        "files": ["manage.py", "settings.py"],
        "dirs": ["templates", "static"],
        "content": {"requirements.txt": "django", "setup.py": "django"},
    },
    FrameworkType.FLASK: {
        "files": ["app.py", "wsgi.py"],
        "content": {"requirements.txt": "flask", "setup.py": "flask"},
    },
    FrameworkType.FASTAPI: {
        "files": ["main.py"],
        "content": {"requirements.txt": "fastapi", "pyproject.toml": "fastapi"},
    },
    FrameworkType.REACT: {
        "files": ["package.json"],
        "dirs": ["src/components", "public"],
        "content": {"package.json": '"react"'},
    },
    FrameworkType.VUE: {
        "files": ["package.json", "vue.config.js"],
        "dirs": ["src/components", "src/views"],
        "content": {"package.json": '"vue"'},
    },
    FrameworkType.ANGULAR: {
        "files": ["angular.json", "package.json"],
        "dirs": ["src/app"],
        "content": {"package.json": '"@angular/core"'},
    },
    FrameworkType.NEXTJS: {
        "files": ["next.config.js", "next.config.mjs", "package.json"],
        "dirs": ["pages", "app"],
        "content": {"package.json": '"next"'},
    },
    FrameworkType.EXPRESS: {
        "files": ["package.json", "app.js", "server.js"],
        "content": {"package.json": '"express"'},
    },
    FrameworkType.NESTJS: {
        "files": ["nest-cli.json", "package.json"],
        "dirs": ["src/modules"],
        "content": {"package.json": '"@nestjs/core"'},
    },
    FrameworkType.WORDPRESS: {
        "files": ["wp-config.php", "wp-load.php"],
        "dirs": ["wp-content", "wp-admin", "wp-includes"],
    },
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ArchitectureAnalysis:
    """Result of architecture analysis."""
    pattern: ArchitecturePattern
    confidence: float  # 0.0 to 1.0
    framework: Optional[FrameworkType] = None
    detected_layers: List[str] = field(default_factory=list)
    detected_patterns: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "confidence": self.confidence,
            "framework": self.framework.value if self.framework else None,
            "detected_layers": self.detected_layers,
            "detected_patterns": self.detected_patterns,
            "suggestions": self.suggestions,
        }

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        parts = [f"Architecture: {self.pattern.value}"]
        if self.framework:
            parts.append(f"Framework: {self.framework.value}")
        if self.detected_layers:
            parts.append(f"Layers: {', '.join(self.detected_layers[:5])}")
        parts.append(f"Confidence: {self.confidence:.0%}")
        return ". ".join(parts)


@dataclass
class ProjectStructure:
    """Detected project structure."""
    root_path: str
    directories: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    languages: Dict[str, int] = field(default_factory=dict)  # language -> file count


# =============================================================================
# Architecture Detector
# =============================================================================

class ArchitectureDetector:
    """
    Detects architectural patterns in a codebase.
    """

    def __init__(self):
        self._cache: Dict[str, ArchitectureAnalysis] = {}

    def analyze(self, project_path: str) -> ArchitectureAnalysis:
        """
        Analyze a project and detect its architecture.

        Args:
            project_path: Path to project root

        Returns:
            ArchitectureAnalysis with detected pattern and confidence
        """
        if project_path in self._cache:
            return self._cache[project_path]

        path = Path(project_path)
        if not path.exists():
            return ArchitectureAnalysis(
                pattern=ArchitecturePattern.UNKNOWN,
                confidence=0.0,
            )

        # Gather project structure
        structure = self._scan_structure(path)

        # Detect framework first (helps with architecture detection)
        framework = self._detect_framework(path, structure)

        # Detect architecture pattern
        pattern, confidence, layers = self._detect_pattern(path, structure, framework)

        # Generate suggestions
        suggestions = self._generate_suggestions(pattern, structure, framework)

        analysis = ArchitectureAnalysis(
            pattern=pattern,
            confidence=confidence,
            framework=framework,
            detected_layers=layers,
            detected_patterns=self._detect_design_patterns(structure),
            suggestions=suggestions,
        )

        self._cache[project_path] = analysis
        return analysis

    def _scan_structure(self, path: Path, max_depth: int = 4) -> ProjectStructure:
        """Scan project directory structure."""
        directories: List[str] = []
        files: List[str] = []
        languages: Dict[str, int] = {}

        ext_to_lang = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".php": "php", ".go": "go", ".rs": "rust", ".rb": "ruby",
            ".java": "java", ".cs": "csharp", ".vue": "vue",
        }

        def scan(current: Path, depth: int):
            if depth > max_depth:
                return

            try:
                for item in current.iterdir():
                    # Skip hidden and common non-source dirs
                    if item.name.startswith('.') or item.name in [
                        "node_modules", "vendor", "__pycache__", "venv",
                        ".venv", "dist", "build", "target"
                    ]:
                        continue

                    rel_path = str(item.relative_to(path))

                    if item.is_dir():
                        directories.append(rel_path)
                        scan(item, depth + 1)
                    else:
                        files.append(rel_path)
                        ext = item.suffix.lower()
                        if ext in ext_to_lang:
                            lang = ext_to_lang[ext]
                            languages[lang] = languages.get(lang, 0) + 1
            except PermissionError:
                pass

        scan(path, 0)

        return ProjectStructure(
            root_path=str(path),
            directories=directories,
            files=files,
            languages=languages,
        )

    def _detect_framework(
        self,
        path: Path,
        structure: ProjectStructure,
    ) -> Optional[FrameworkType]:
        """Detect the framework used in the project."""
        best_match: Optional[FrameworkType] = None
        best_score = 0

        for framework, patterns in FRAMEWORK_PATTERNS.items():
            score = 0

            # Check files
            for file in patterns.get("files", []):
                if (path / file).exists():
                    score += 2

            # Check directories
            for dir_name in patterns.get("dirs", []):
                if (path / dir_name).exists():
                    score += 1

            # Check content
            for file, content_pattern in patterns.get("content", {}).items():
                file_path = path / file
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        if content_pattern.lower() in content.lower():
                            score += 3
                    except Exception:
                        pass

            if score > best_score:
                best_score = score
                best_match = framework

        # Require minimum score
        return best_match if best_score >= 3 else None

    def _detect_pattern(
        self,
        path: Path,
        structure: ProjectStructure,
        framework: Optional[FrameworkType],
    ) -> Tuple[ArchitecturePattern, float, List[str]]:
        """Detect architectural pattern."""
        scores: Dict[ArchitecturePattern, float] = {p: 0.0 for p in ArchitecturePattern}
        detected_layers: List[str] = []

        dirs_lower = [d.lower() for d in structure.directories]

        # Check directory patterns
        for pattern, dir_patterns in DIRECTORY_PATTERNS.items():
            for dir_pattern in dir_patterns:
                dir_lower = dir_pattern.lower()
                for dir_name in dirs_lower:
                    if dir_lower in dir_name or dir_name.endswith(dir_lower):
                        scores[pattern] += 1.0
                        if dir_pattern not in detected_layers:
                            detected_layers.append(dir_pattern)

        # Framework-based inference
        if framework:
            if framework in [FrameworkType.LARAVEL, FrameworkType.SYMFONY,
                           FrameworkType.DJANGO, FrameworkType.CODEIGNITER]:
                scores[ArchitecturePattern.MVC] += 3.0
            elif framework in [FrameworkType.FASTAPI, FrameworkType.EXPRESS,
                              FrameworkType.NESTJS]:
                scores[ArchitecturePattern.API_FIRST] += 2.0
                scores[ArchitecturePattern.LAYERED] += 1.0
            elif framework in [FrameworkType.REACT, FrameworkType.VUE,
                              FrameworkType.ANGULAR]:
                scores[ArchitecturePattern.MVVM] += 2.0

        # Normalize scores and find best match
        max_score = max(scores.values()) if scores.values() else 0
        if max_score == 0:
            return ArchitecturePattern.UNKNOWN, 0.0, detected_layers

        best_pattern = max(scores, key=scores.get)
        confidence = min(1.0, scores[best_pattern] / 10.0)  # Normalize to 0-1

        return best_pattern, confidence, detected_layers

    def _detect_design_patterns(self, structure: ProjectStructure) -> List[str]:
        """Detect common design patterns from file/class names."""
        patterns: List[str] = []

        # Check for common pattern indicators in file names
        pattern_indicators = {
            "Factory": "factory",
            "Repository": "repository",
            "Service": "service",
            "Controller": "controller",
            "Middleware": "middleware",
            "Observer": "observer",
            "Singleton": "singleton",
            "Adapter": "adapter",
            "Decorator": "decorator",
            "Strategy": "strategy",
            "Command": "command",
            "Handler": "handler",
            "DTO": "dto",
            "Entity": "entity",
            "ValueObject": "valueobject",
        }

        files_lower = [f.lower() for f in structure.files]

        for pattern_name, indicator in pattern_indicators.items():
            if any(indicator in f for f in files_lower):
                patterns.append(pattern_name)

        return patterns

    def _generate_suggestions(
        self,
        pattern: ArchitecturePattern,
        structure: ProjectStructure,
        framework: Optional[FrameworkType],
    ) -> List[str]:
        """Generate architecture improvement suggestions."""
        suggestions: List[str] = []

        # Check for missing common directories
        if pattern == ArchitecturePattern.MVC:
            expected = ["models", "views", "controllers"]
            dirs_lower = [d.lower() for d in structure.directories]
            for exp in expected:
                if not any(exp in d for d in dirs_lower):
                    suggestions.append(f"Consider adding a '{exp}' directory")

        # Check for tests directory
        if not any("test" in d.lower() for d in structure.directories):
            suggestions.append("Add a tests directory for unit/integration tests")

        # Framework-specific suggestions
        if framework == FrameworkType.LARAVEL:
            if not any("service" in d.lower() for d in structure.directories):
                suggestions.append("Consider adding a Services directory for business logic")

        return suggestions[:5]  # Limit suggestions

    def clear_cache(self, project_path: Optional[str] = None):
        """Clear analysis cache."""
        if project_path:
            self._cache.pop(project_path, None)
        else:
            self._cache.clear()


# =============================================================================
# Global Instance
# =============================================================================

architecture_detector = ArchitectureDetector()
