"""
Package Import Validator for Hallucination Prevention (v1.0)

Validates that imported packages actually exist in the project's dependencies.
Detects "slopsquatting" - hallucinated package names that attackers could register.

Research shows ~20% of LLM-recommended packages don't exist!
Source: https://socket.dev/blog/slopsquatting-how-ai-hallucinations-are-fueling-a-new-class-of-supply-chain-attacks

Design Principles:
- Local validation only (no API calls)
- Standard libraries whitelisted
- WARN mode as default (never block by default)
- Levenshtein-based typo detection for slopsquatting
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from .symbol_patterns import Language, detect_language

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PackageIssue:
    """A potentially hallucinated package import."""
    package: str
    file: str
    line: int
    confidence: float  # 0.0 - 1.0
    import_type: str  # 'composer', 'npm', 'pip'
    reason: str = ""
    suggestions: List[str] = field(default_factory=list)
    is_slopsquatting: bool = False  # True if similar to known package

    @property
    def severity(self) -> str:
        """Get severity based on confidence."""
        if self.confidence > 0.8:
            return "HIGH"
        elif self.confidence > 0.5:
            return "MEDIUM"
        return "LOW"


@dataclass
class PackageValidationResult:
    """Result from package validation."""
    issues: List[PackageIssue]
    validated_count: int
    registry_found: bool  # Whether composer.json/package.json was found

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    @property
    def max_confidence(self) -> float:
        return max((i.confidence for i in self.issues), default=0.0)


# =============================================================================
# STANDARD LIBRARIES - Always valid, never hallucinated
# =============================================================================

PYTHON_STDLIB: Set[str] = {
    # Core
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
    'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect',
    'builtins', 'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd',
    'code', 'codecs', 'codeop', 'collections', 'colorsys', 'compileall',
    'concurrent', 'configparser', 'contextlib', 'contextvars', 'copy',
    'copyreg', 'cProfile', 'crypt', 'csv', 'ctypes', 'curses', 'dataclasses',
    'datetime', 'dbm', 'decimal', 'difflib', 'dis', 'distutils', 'doctest',
    'email', 'encodings', 'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp',
    'fileinput', 'fnmatch', 'fractions', 'ftplib', 'functools', 'gc',
    'getopt', 'getpass', 'gettext', 'glob', 'graphlib', 'grp', 'gzip',
    'hashlib', 'heapq', 'hmac', 'html', 'http', 'idlelib', 'imaplib',
    'imghdr', 'imp', 'importlib', 'inspect', 'io', 'ipaddress', 'itertools',
    'json', 'keyword', 'lib2to3', 'linecache', 'locale', 'logging', 'lzma',
    'mailbox', 'mailcap', 'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder',
    'multiprocessing', 'netrc', 'nis', 'nntplib', 'numbers', 'operator', 'optparse',
    'os', 'ossaudiodev', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes',
    'pkgutil', 'platform', 'plistlib', 'poplib', 'posix', 'posixpath', 'pprint',
    'profile', 'pstats', 'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue',
    'quopri', 'random', 're', 'readline', 'reprlib', 'resource', 'rlcompleter',
    'runpy', 'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex',
    'shutil', 'signal', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket',
    'socketserver', 'spwd', 'sqlite3', 'ssl', 'stat', 'statistics', 'string',
    'stringprep', 'struct', 'subprocess', 'sunau', 'symtable', 'sys', 'sysconfig',
    'syslog', 'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios', 'test',
    'textwrap', 'threading', 'time', 'timeit', 'tkinter', 'token', 'tokenize',
    'tomllib', 'trace', 'traceback', 'tracemalloc', 'tty', 'turtle', 'turtledemo',
    'types', 'typing', 'unicodedata', 'unittest', 'urllib', 'uu', 'uuid',
    'venv', 'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'winsound',
    'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib',
    # Typing extensions
    'typing_extensions',
}

NODE_BUILTINS: Set[str] = {
    'assert', 'async_hooks', 'buffer', 'child_process', 'cluster', 'console',
    'constants', 'crypto', 'dgram', 'diagnostics_channel', 'dns', 'domain',
    'events', 'fs', 'http', 'http2', 'https', 'inspector', 'module', 'net',
    'os', 'path', 'perf_hooks', 'process', 'punycode', 'querystring', 'readline',
    'repl', 'stream', 'string_decoder', 'sys', 'timers', 'tls', 'trace_events',
    'tty', 'url', 'util', 'v8', 'vm', 'wasi', 'worker_threads', 'zlib',
    # Node prefixed
    'node:assert', 'node:async_hooks', 'node:buffer', 'node:child_process',
    'node:cluster', 'node:console', 'node:constants', 'node:crypto', 'node:dgram',
    'node:diagnostics_channel', 'node:dns', 'node:domain', 'node:events',
    'node:fs', 'node:http', 'node:http2', 'node:https', 'node:inspector',
    'node:module', 'node:net', 'node:os', 'node:path', 'node:perf_hooks',
    'node:process', 'node:punycode', 'node:querystring', 'node:readline',
    'node:repl', 'node:stream', 'node:string_decoder', 'node:sys', 'node:timers',
    'node:tls', 'node:trace_events', 'node:tty', 'node:url', 'node:util',
    'node:v8', 'node:vm', 'node:wasi', 'node:worker_threads', 'node:zlib',
    # Bun
    'bun', 'bun:test', 'bun:sqlite', 'bun:ffi',
    # Deno
    'Deno',
}

PHP_BUILTINS: Set[str] = {
    # Core PHP classes/namespaces
    'Exception', 'Error', 'TypeError', 'ArgumentCountError', 'ArithmeticError',
    'DivisionByZeroError', 'ParseError', 'AssertionError', 'CompileError',
    'ValueError', 'UnhandledMatchError', 'FiberError',
    # SPL Exceptions
    'LogicException', 'BadFunctionCallException', 'BadMethodCallException',
    'DomainException', 'InvalidArgumentException', 'LengthException',
    'OutOfRangeException', 'RuntimeException', 'OutOfBoundsException',
    'OverflowException', 'RangeException', 'UnderflowException',
    'UnexpectedValueException',
    # SPL Classes
    'ArrayObject', 'ArrayIterator', 'RecursiveArrayIterator', 'DirectoryIterator',
    'FilesystemIterator', 'RecursiveDirectoryIterator', 'GlobIterator',
    'SplFileInfo', 'SplFileObject', 'SplTempFileObject', 'SplDoublyLinkedList',
    'SplStack', 'SplQueue', 'SplHeap', 'SplMinHeap', 'SplMaxHeap',
    'SplPriorityQueue', 'SplFixedArray', 'SplObjectStorage',
    # DateTime
    'DateTime', 'DateTimeImmutable', 'DateTimeInterface', 'DateTimeZone',
    'DateInterval', 'DatePeriod',
    # Reflection
    'ReflectionClass', 'ReflectionMethod', 'ReflectionProperty', 'ReflectionFunction',
    'ReflectionParameter', 'ReflectionType', 'ReflectionNamedType',
    'ReflectionObject', 'ReflectionExtension', 'ReflectionException',
    # Common
    'stdClass', 'Closure', 'Generator', 'Fiber', 'WeakReference', 'WeakMap',
    'Attribute', 'Stringable', 'Traversable', 'Iterator', 'IteratorAggregate',
    'Throwable', 'Countable', 'Serializable', 'JsonSerializable',
    # PDO
    'PDO', 'PDOStatement', 'PDOException',
    # JSON
    'JsonException',
    # Intl
    'IntlException', 'IntlDateFormatter', 'NumberFormatter', 'Locale',
    # Other common
    'SimpleXMLElement', 'DOMDocument', 'DOMElement', 'DOMNode', 'DOMException',
    'XMLReader', 'XMLWriter', 'Phar', 'PharException', 'ZipArchive',
    'CurlHandle', 'CurlMultiHandle', 'CurlShareHandle',
    'finfo', 'mysqli', 'mysqli_result', 'mysqli_stmt',
}

# =============================================================================
# PHP NAMESPACE TO PACKAGE MAPPING
# Maps Composer package names to their PHP namespaces
# =============================================================================

PHP_NAMESPACE_MAPPING: Dict[str, List[str]] = {
    # Laravel/Illuminate
    'laravel/framework': [
        'Illuminate\\', 'Illuminate\\Auth\\', 'Illuminate\\Broadcasting\\',
        'Illuminate\\Bus\\', 'Illuminate\\Cache\\', 'Illuminate\\Config\\',
        'Illuminate\\Console\\', 'Illuminate\\Container\\', 'Illuminate\\Contracts\\',
        'Illuminate\\Cookie\\', 'Illuminate\\Database\\', 'Illuminate\\Encryption\\',
        'Illuminate\\Events\\', 'Illuminate\\Filesystem\\', 'Illuminate\\Foundation\\',
        'Illuminate\\Hashing\\', 'Illuminate\\Http\\', 'Illuminate\\Log\\',
        'Illuminate\\Mail\\', 'Illuminate\\Notifications\\', 'Illuminate\\Pagination\\',
        'Illuminate\\Pipeline\\', 'Illuminate\\Queue\\', 'Illuminate\\Redis\\',
        'Illuminate\\Routing\\', 'Illuminate\\Session\\', 'Illuminate\\Support\\',
        'Illuminate\\Testing\\', 'Illuminate\\Translation\\', 'Illuminate\\Validation\\',
        'Illuminate\\View\\',
    ],
    # Symfony - note: all Symfony components use Symfony\Component\ prefix
    'symfony/console': ['Symfony\\Component\\Console\\', 'Symfony\\Component\\'],
    'symfony/http-foundation': ['Symfony\\Component\\HttpFoundation\\', 'Symfony\\Component\\'],
    'symfony/http-kernel': ['Symfony\\Component\\HttpKernel\\', 'Symfony\\Component\\'],
    'symfony/routing': ['Symfony\\Component\\Routing\\', 'Symfony\\Component\\'],
    'symfony/event-dispatcher': ['Symfony\\Component\\EventDispatcher\\', 'Symfony\\Component\\'],
    'symfony/validator': ['Symfony\\Component\\Validator\\', 'Symfony\\Component\\'],
    'symfony/cache': ['Symfony\\Component\\Cache\\', 'Symfony\\Contracts\\Cache\\', 'Symfony\\Component\\', 'Symfony\\Contracts\\'],
    'symfony/filesystem': ['Symfony\\Component\\Filesystem\\', 'Symfony\\Component\\'],
    'symfony/finder': ['Symfony\\Component\\Finder\\', 'Symfony\\Component\\'],
    'symfony/process': ['Symfony\\Component\\Process\\', 'Symfony\\Component\\'],
    'symfony/var-dumper': ['Symfony\\Component\\VarDumper\\', 'Symfony\\Component\\'],
    'symfony/yaml': ['Symfony\\Component\\Yaml\\', 'Symfony\\Component\\'],
    'symfony/contracts': ['Symfony\\Contracts\\'],
    # Guzzle
    'guzzlehttp/guzzle': [
        'GuzzleHttp\\', 'GuzzleHttp\\Client', 'GuzzleHttp\\Exception\\',
        'GuzzleHttp\\Handler\\', 'GuzzleHttp\\HandlerStack', 'GuzzleHttp\\Middleware',
        'GuzzleHttp\\Pool', 'GuzzleHttp\\Promise\\', 'GuzzleHttp\\Psr7\\',
    ],
    'guzzlehttp/psr7': ['GuzzleHttp\\Psr7\\'],
    'guzzlehttp/promises': ['GuzzleHttp\\Promise\\'],
    # Monolog
    'monolog/monolog': [
        'Monolog\\', 'Monolog\\Handler\\', 'Monolog\\Formatter\\',
        'Monolog\\Processor\\', 'Monolog\\Logger',
    ],
    # PSR
    'psr/log': ['Psr\\Log\\'],
    'psr/http-message': ['Psr\\Http\\Message\\', 'Psr\\Http\\'],
    'psr/http-client': ['Psr\\Http\\Client\\', 'Psr\\Http\\'],
    'psr/container': ['Psr\\Container\\'],
    'psr/cache': ['Psr\\Cache\\'],
    'psr/simple-cache': ['Psr\\SimpleCache\\'],
    'psr/event-dispatcher': ['Psr\\EventDispatcher\\'],
    # Doctrine
    'doctrine/orm': ['Doctrine\\ORM\\', 'Doctrine\\ORM\\Mapping\\'],
    'doctrine/dbal': ['Doctrine\\DBAL\\'],
    'doctrine/common': ['Doctrine\\Common\\'],
    'doctrine/collections': ['Doctrine\\Common\\Collections\\'],
    'doctrine/annotations': ['Doctrine\\Common\\Annotations\\'],
    # PHPUnit
    'phpunit/phpunit': ['PHPUnit\\', 'PHPUnit\\Framework\\'],
    # Carbon
    'nesbot/carbon': ['Carbon\\'],
    'carbon/carbon': ['Carbon\\'],
    # League packages
    'league/flysystem': ['League\\Flysystem\\'],
    'league/oauth2-client': ['League\\OAuth2\\Client\\'],
    'league/csv': ['League\\Csv\\'],
    # Other common packages
    'vlucas/phpdotenv': ['Dotenv\\'],
    'ramsey/uuid': ['Ramsey\\Uuid\\'],
    'firebase/php-jwt': ['Firebase\\JWT\\'],
    'predis/predis': ['Predis\\'],
    'aws/aws-sdk-php': ['Aws\\'],
    'stripe/stripe-php': ['Stripe\\'],
    'twilio/sdk': ['Twilio\\'],
    'sendgrid/sendgrid': ['SendGrid\\'],
    'phpmailer/phpmailer': ['PHPMailer\\PHPMailer\\'],
    'intervention/image': ['Intervention\\Image\\'],
    'spatie/laravel-permission': ['Spatie\\Permission\\'],
    'tymon/jwt-auth': ['Tymon\\JWTAuth\\'],
}


# =============================================================================
# IMPORT PATTERNS
# =============================================================================

# PHP: use statements
PHP_USE_PATTERN = re.compile(
    r'^\s*use\s+([A-Z][a-zA-Z0-9_\\]+)(?:\s+as\s+\w+)?;',
    re.MULTILINE
)

# PHP: Fully qualified class references (new \Vendor\Class)
PHP_FQN_PATTERN = re.compile(
    r'(?:new|extends|implements|instanceof)\s+\\?([A-Z][a-zA-Z0-9_\\]+)',
    re.MULTILINE
)

# JS/TS: import statements
JS_IMPORT_PATTERN = re.compile(
    r'''(?:^|\s)import\s+(?:(?:[\w*{}\s,]+)\s+from\s+)?['"]([^'"./][^'"]*?)['"]''',
    re.MULTILINE
)

# JS/TS: require statements
JS_REQUIRE_PATTERN = re.compile(
    r'''require\s*\(\s*['"]([^'"./][^'"]*?)['"]\s*\)''',
    re.MULTILINE
)

# JS/TS: dynamic import
JS_DYNAMIC_IMPORT_PATTERN = re.compile(
    r'''import\s*\(\s*['"]([^'"./][^'"]*?)['"]\s*\)''',
    re.MULTILINE
)

# Python: import statements
PYTHON_IMPORT_PATTERN = re.compile(
    r'^(?:from\s+(\w+)|import\s+(\w+))(?:\s|,|$)',
    re.MULTILINE
)

# Python: from X import Y
PYTHON_FROM_IMPORT_PATTERN = re.compile(
    r'^from\s+([\w.]+)\s+import',
    re.MULTILINE
)


# =============================================================================
# LEVENSHTEIN DISTANCE - For typo/slopsquatting detection
# =============================================================================

def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def find_similar_packages(
    package: str,
    known_packages: Set[str],
    max_distance: int = 2
) -> List[Tuple[str, int]]:
    """Find packages with similar names (potential typos or slopsquatting).

    Returns list of (package_name, distance) sorted by distance.
    """
    similar = []
    package_lower = package.lower()

    for known in known_packages:
        known_lower = known.lower()

        # Skip if too different in length
        if abs(len(package) - len(known)) > max_distance:
            continue

        distance = levenshtein_distance(package_lower, known_lower)

        if 0 < distance <= max_distance:
            similar.append((known, distance))

    # Sort by distance
    similar.sort(key=lambda x: x[1])
    return similar


# =============================================================================
# IMPORT EXTRACTOR
# =============================================================================

class ImportExtractor:
    """Extracts package imports from source code."""

    def extract_php_imports(self, content: str) -> List[Tuple[str, int]]:
        """Extract PHP use statements and FQN references.

        Returns: List of (package_namespace, line_number)
        """
        imports = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            # Check use statements
            match = PHP_USE_PATTERN.match(line)
            if match:
                namespace = match.group(1)
                # Get the vendor/package part (first two segments)
                parts = namespace.split('\\')
                if len(parts) >= 2:
                    package = f"{parts[0]}\\{parts[1]}"
                    imports.append((package, line_num))
                # Skip single-word imports without namespace - these are local classes/traits
                # or PHP builtins already covered elsewhere
                # e.g., "use CreatesApplication;" is a local trait, not an external package

        return imports

    def extract_js_imports(self, content: str) -> List[Tuple[str, int]]:
        """Extract JavaScript/TypeScript imports.

        Returns: List of (package_name, line_number)
        """
        imports = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            # Import statements
            for match in JS_IMPORT_PATTERN.finditer(line):
                package = match.group(1)
                # Get base package name (before any /)
                base_package = package.split('/')[0]
                # Handle scoped packages (@org/package)
                if package.startswith('@') and '/' in package:
                    parts = package.split('/')
                    if len(parts) >= 2:
                        base_package = f"{parts[0]}/{parts[1]}"
                imports.append((base_package, line_num))

            # Require statements
            for match in JS_REQUIRE_PATTERN.finditer(line):
                package = match.group(1)
                base_package = package.split('/')[0]
                if package.startswith('@') and '/' in package:
                    parts = package.split('/')
                    if len(parts) >= 2:
                        base_package = f"{parts[0]}/{parts[1]}"
                imports.append((base_package, line_num))

            # Dynamic imports
            for match in JS_DYNAMIC_IMPORT_PATTERN.finditer(line):
                package = match.group(1)
                base_package = package.split('/')[0]
                if package.startswith('@') and '/' in package:
                    parts = package.split('/')
                    if len(parts) >= 2:
                        base_package = f"{parts[0]}/{parts[1]}"
                imports.append((base_package, line_num))

        return imports

    def extract_python_imports(self, content: str) -> List[Tuple[str, int]]:
        """Extract Python imports.

        Returns: List of (package_name, line_number)
        """
        imports = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip comments
            if stripped.startswith('#'):
                continue

            # from X import Y
            match = PYTHON_FROM_IMPORT_PATTERN.match(stripped)
            if match:
                module = match.group(1)
                # Get root package
                root = module.split('.')[0]
                if root and not root.startswith('.'):
                    imports.append((root, line_num))
                continue

            # import X, Y, Z
            if stripped.startswith('import '):
                # Handle multiple imports
                import_part = stripped[7:].split('#')[0]  # Remove comments
                for part in import_part.split(','):
                    module = part.strip().split(' ')[0]  # Handle "as alias"
                    root = module.split('.')[0]
                    if root and not root.startswith('.'):
                        imports.append((root, line_num))

        return imports

    def extract_imports(
        self,
        content: str,
        lang: Language
    ) -> List[Tuple[str, int]]:
        """Extract imports based on language.

        Returns: List of (package_name, line_number)
        """
        if lang == Language.PHP:
            return self.extract_php_imports(content)
        elif lang in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            return self.extract_js_imports(content)
        elif lang == Language.PYTHON:
            return self.extract_python_imports(content)
        return []


# =============================================================================
# PACKAGE REGISTRY
# =============================================================================

class PackageRegistry:
    """Reads and caches package registry information."""

    def __init__(self, working_dir: str):
        self.working_dir = Path(working_dir)
        self._cache: Dict[str, Set[str]] = {}
        self._namespace_cache: Dict[str, Set[str]] = {}

    def get_installed_namespaces(self) -> Set[str]:
        """Get all installed namespaces by checking vendor directory structure.

        Priority:
        1. Parse vendor/composer/installed.json (most reliable)
        2. Scan vendor/ directory structure
        3. Parse composer.lock as fallback

        Returns: Set of valid namespace prefixes (e.g., 'Illuminate', 'GuzzleHttp')
        """
        cache_key = 'installed_namespaces'
        if cache_key in self._namespace_cache:
            return self._namespace_cache[cache_key]

        namespaces: Set[str] = set()

        # PRIORITY 1: vendor/composer/installed.json (Composer 2.x)
        installed_json = self.working_dir / 'vendor' / 'composer' / 'installed.json'
        if installed_json.exists():
            try:
                with open(installed_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Composer 2.x format
                packages = data.get('packages', data) if isinstance(data, dict) else data
                if isinstance(packages, list):
                    for pkg in packages:
                        autoload = pkg.get('autoload', {})
                        for ns in autoload.get('psr-4', {}).keys():
                            ns_clean = ns.rstrip('\\')
                            if ns_clean:
                                namespaces.add(ns_clean)
                                # Add all parent namespaces for prefix matching
                                parts = ns_clean.split('\\')
                                for i in range(1, len(parts) + 1):
                                    namespaces.add('\\'.join(parts[:i]))

                        for ns in autoload.get('psr-0', {}).keys():
                            ns_clean = ns.rstrip('\\')
                            if ns_clean:
                                namespaces.add(ns_clean)

                if namespaces:
                    self._namespace_cache[cache_key] = namespaces
                    return namespaces

            except (json.JSONDecodeError, IOError) as e:
                logger.debug(f"Could not parse installed.json: {e}")

        # PRIORITY 2: Scan vendor/ directory structure
        vendor_dir = self.working_dir / 'vendor'
        if vendor_dir.exists():
            for vendor in vendor_dir.iterdir():
                if not vendor.is_dir() or vendor.name.startswith('.') or vendor.name == 'composer':
                    continue
                for pkg_dir in vendor.iterdir():
                    if not pkg_dir.is_dir() or pkg_dir.name.startswith('.'):
                        continue
                    # Check for src/ directory and infer namespace
                    src_dir = pkg_dir / 'src'
                    if src_dir.exists():
                        # Try to find namespace from directory structure
                        # Common pattern: vendor/guzzlehttp/guzzle/src/Client.php -> GuzzleHttp\Client
                        # We add the vendor name with proper casing as potential namespace
                        vendor_ns = vendor.name.replace('-', '').title()
                        namespaces.add(vendor_ns)

        # PRIORITY 3: Parse composer.lock
        composer_lock = self.working_dir / 'composer.lock'
        if composer_lock.exists():
            try:
                with open(composer_lock, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for pkg_list in ['packages', 'packages-dev']:
                    if pkg_list not in data:
                        continue
                    for pkg in data[pkg_list]:
                        autoload = pkg.get('autoload', {})
                        for ns in autoload.get('psr-4', {}).keys():
                            ns_clean = ns.rstrip('\\')
                            if ns_clean:
                                namespaces.add(ns_clean)
                                parts = ns_clean.split('\\')
                                for i in range(1, len(parts) + 1):
                                    namespaces.add('\\'.join(parts[:i]))

            except (json.JSONDecodeError, IOError):
                pass

        self._namespace_cache[cache_key] = namespaces
        return namespaces

    def is_namespace_installed(self, namespace: str) -> bool:
        """Check if a namespace is installed by searching for the actual file.

        Approach: Convert namespace to file path and search in vendor/.
        Example: Illuminate\\Http\\Request → vendor/**/Request.php containing 'namespace Illuminate\\Http'

        Args:
            namespace: The namespace to check (e.g., 'Illuminate\\Http')

        Returns: True if namespace is from an installed package
        """
        # First try the fast cached lookup
        installed = self.get_installed_namespaces()
        if installed:
            parts = namespace.split('\\')
            for i in range(len(parts), 0, -1):
                prefix = '\\'.join(parts[:i])
                if prefix in installed:
                    return True

        # Fallback: Direct file search in vendor/
        return self._find_namespace_file(namespace)

    def _find_namespace_file(self, namespace: str) -> bool:
        """Search for a PHP file that defines the given namespace.

        Converts namespace to potential file paths and checks if they exist.
        Example: GuzzleHttp\\Client → vendor/guzzlehttp/guzzle/src/Client.php

        Args:
            namespace: The namespace to find (e.g., 'Illuminate\\Http')

        Returns: True if a matching file is found
        """
        vendor_dir = self.working_dir / 'vendor'
        if not vendor_dir.exists():
            return False

        parts = namespace.split('\\')
        if not parts:
            return False

        # Cache key for this namespace
        cache_key = f'file_search:{namespace}'
        if cache_key in self._namespace_cache:
            return self._namespace_cache[cache_key]

        # Strategy 1: Direct path mapping
        # Illuminate\Http\Request → vendor/illuminate/http/src/Request.php
        if len(parts) >= 2:
            vendor_name = parts[0].lower()
            # Common patterns for vendor directory names
            vendor_variants = [
                vendor_name,
                vendor_name.replace('http', '-http'),  # GuzzleHttp → guzzlehttp
                '-'.join(re.findall(r'[A-Z][a-z]*', parts[0])).lower(),  # CamelCase → kebab-case
            ]

            for vendor in vendor_variants:
                vendor_path = vendor_dir / vendor
                if vendor_path.exists():
                    # Search for the class file
                    class_name = parts[-1] if len(parts) > 1 else parts[0]
                    class_file = f"{class_name}.php"

                    # Check common locations
                    for pattern in [
                        f"**/src/**/{class_file}",
                        f"**/{class_file}",
                        f"**/lib/**/{class_file}",
                    ]:
                        matches = list(vendor_path.glob(pattern))
                        if matches:
                            # Verify the file contains the correct namespace
                            ns_pattern = '\\'.join(parts[:-1]) if len(parts) > 1 else parts[0]
                            for match in matches[:3]:  # Check first 3 matches
                                try:
                                    content = match.read_text(encoding='utf-8', errors='ignore')[:500]
                                    if f'namespace {ns_pattern}' in content or f'namespace {ns_pattern};' in content:
                                        self._namespace_cache[cache_key] = True
                                        return True
                                except IOError:
                                    continue

        # Strategy 2: Search by namespace pattern in any vendor package
        # Look for files that declare this namespace
        ns_declaration = f"namespace {namespace}"
        ns_prefix = '\\'.join(parts[:-1]) if len(parts) > 1 else namespace

        # Limit search to avoid performance issues
        search_count = 0
        max_searches = 50

        for vendor_subdir in vendor_dir.iterdir():
            if not vendor_subdir.is_dir() or vendor_subdir.name.startswith('.'):
                continue
            if vendor_subdir.name == 'composer':
                continue

            for pkg_dir in vendor_subdir.iterdir():
                if not pkg_dir.is_dir():
                    continue

                # Check src/ directory first (most common)
                src_dir = pkg_dir / 'src'
                search_dirs = [src_dir] if src_dir.exists() else [pkg_dir]

                for search_dir in search_dirs:
                    for php_file in search_dir.glob('**/*.php'):
                        search_count += 1
                        if search_count > max_searches:
                            break

                        try:
                            # Read only first 500 bytes for namespace declaration
                            content = php_file.read_text(encoding='utf-8', errors='ignore')[:500]
                            if f'namespace {ns_prefix}' in content:
                                self._namespace_cache[cache_key] = True
                                return True
                        except IOError:
                            continue

                    if search_count > max_searches:
                        break
                if search_count > max_searches:
                    break
            if search_count > max_searches:
                break

        self._namespace_cache[cache_key] = False
        return False

    def get_composer_packages(self) -> Tuple[Set[str], bool]:
        """Get packages from composer.json and composer.lock.

        Returns: (set of package names, whether composer.json was found)
        """
        cache_key = 'composer'
        if cache_key in self._cache:
            return self._cache[cache_key], True

        packages: Set[str] = set()
        composer_json = self.working_dir / 'composer.json'
        composer_lock = self.working_dir / 'composer.lock'

        found = False

        # Read composer.json
        if composer_json.exists():
            found = True
            try:
                with open(composer_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # require and require-dev
                for section in ['require', 'require-dev']:
                    if section in data:
                        for pkg in data[section].keys():
                            if pkg != 'php' and not pkg.startswith('ext-'):
                                # Convert package name to namespace
                                # e.g., "vendor/package" -> "Vendor\\Package" (approximate)
                                packages.add(pkg)

                # PSR-4 autoload (local namespaces)
                for section in ['autoload', 'autoload-dev']:
                    if section in data and 'psr-4' in data[section]:
                        for namespace in data[section]['psr-4'].keys():
                            # Remove trailing backslash
                            ns = namespace.rstrip('\\')
                            if ns:
                                packages.add(ns)

            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to parse composer.json: {e}")

        # Also check composer.lock for more accurate package list
        if composer_lock.exists():
            try:
                with open(composer_lock, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for pkg_list in ['packages', 'packages-dev']:
                    if pkg_list in data:
                        for pkg in data[pkg_list]:
                            if 'name' in pkg:
                                packages.add(pkg['name'])
                            # Also add autoload namespaces
                            if 'autoload' in pkg and 'psr-4' in pkg['autoload']:
                                for ns in pkg['autoload']['psr-4'].keys():
                                    packages.add(ns.rstrip('\\'))

            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to parse composer.lock: {e}")

        # Check vendor directory as fallback
        vendor_dir = self.working_dir / 'vendor'
        if vendor_dir.exists():
            found = True
            for vendor in vendor_dir.iterdir():
                if vendor.is_dir() and not vendor.name.startswith('.'):
                    for package in vendor.iterdir():
                        if package.is_dir() and not package.name.startswith('.'):
                            packages.add(f"{vendor.name}/{package.name}")

        self._cache[cache_key] = packages
        return packages, found

    def get_npm_packages(self) -> Tuple[Set[str], bool]:
        """Get packages from package.json.

        Returns: (set of package names, whether package.json was found)
        """
        cache_key = 'npm'
        if cache_key in self._cache:
            return self._cache[cache_key], True

        packages: Set[str] = set()
        package_json = self.working_dir / 'package.json'

        if not package_json.exists():
            return packages, False

        try:
            with open(package_json, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for section in ['dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies']:
                if section in data:
                    packages.update(data[section].keys())

            # Also add the package name itself (for internal imports)
            if 'name' in data:
                packages.add(data['name'])

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to parse package.json: {e}")
            return packages, False

        # Check node_modules as fallback
        node_modules = self.working_dir / 'node_modules'
        if node_modules.exists():
            for item in node_modules.iterdir():
                if item.is_dir():
                    if item.name.startswith('@'):
                        # Scoped packages
                        for pkg in item.iterdir():
                            if pkg.is_dir():
                                packages.add(f"{item.name}/{pkg.name}")
                    elif not item.name.startswith('.'):
                        packages.add(item.name)

        self._cache[cache_key] = packages
        return packages, True

    def get_pip_packages(self) -> Tuple[Set[str], bool]:
        """Get packages from requirements.txt, pyproject.toml, or setup.py.

        Returns: (set of package names, whether any requirements file was found)
        """
        cache_key = 'pip'
        if cache_key in self._cache:
            return self._cache[cache_key], True

        packages: Set[str] = set()
        found = False

        # requirements.txt
        for req_file in ['requirements.txt', 'requirements-dev.txt', 'requirements-test.txt']:
            req_path = self.working_dir / req_file
            if req_path.exists():
                found = True
                try:
                    with open(req_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and not line.startswith('-'):
                                # Extract package name (before version specifier)
                                match = re.match(r'^([a-zA-Z0-9_-]+)', line)
                                if match:
                                    packages.add(match.group(1).lower())
                except IOError as e:
                    logger.warning(f"Failed to read {req_file}: {e}")

        # pyproject.toml
        pyproject = self.working_dir / 'pyproject.toml'
        if pyproject.exists():
            found = True
            try:
                with open(pyproject, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Simple regex extraction (not a full TOML parser)
                # Match dependencies in [project.dependencies] or [tool.poetry.dependencies]
                dep_pattern = re.compile(r'^\s*([a-zA-Z0-9_-]+)\s*[=<>]', re.MULTILINE)
                for match in dep_pattern.finditer(content):
                    packages.add(match.group(1).lower())

            except IOError as e:
                logger.warning(f"Failed to read pyproject.toml: {e}")

        # setup.py (basic extraction)
        setup_py = self.working_dir / 'setup.py'
        if setup_py.exists():
            found = True
            try:
                with open(setup_py, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract from install_requires
                match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if match:
                    deps = match.group(1)
                    for dep_match in re.finditer(r"['\"]([a-zA-Z0-9_-]+)", deps):
                        packages.add(dep_match.group(1).lower())

            except IOError as e:
                logger.warning(f"Failed to read setup.py: {e}")

        self._cache[cache_key] = packages
        return packages, found

    def get_packages(self, lang: Language) -> Tuple[Set[str], bool]:
        """Get packages for a given language.

        Returns: (set of package names, whether registry was found)
        """
        if lang == Language.PHP:
            return self.get_composer_packages()
        elif lang in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            return self.get_npm_packages()
        elif lang == Language.PYTHON:
            return self.get_pip_packages()
        return set(), False

    def clear_cache(self):
        """Clear the package cache."""
        self._cache.clear()


# =============================================================================
# PACKAGE VALIDATOR
# =============================================================================

class PackageValidator:
    """Main validator for detecting hallucinated package imports."""

    def __init__(self, working_dir: str):
        self.working_dir = Path(working_dir)
        self.extractor = ImportExtractor()
        self.registry = PackageRegistry(working_dir)

    def validate_file(self, file_path: str) -> PackageValidationResult:
        """Validate a file for hallucinated package imports.

        Returns: PackageValidationResult
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self.working_dir / path

        if not path.exists():
            return PackageValidationResult(issues=[], validated_count=0, registry_found=False)

        lang = detect_language(str(path))
        if not lang:
            return PackageValidationResult(issues=[], validated_count=0, registry_found=False)

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
        except IOError:
            return PackageValidationResult(issues=[], validated_count=0, registry_found=False)

        return self.validate_content(content, str(path), lang)

    def validate_content(
        self,
        content: str,
        file_path: str,
        lang: Language
    ) -> PackageValidationResult:
        """Validate content for hallucinated package imports."""

        # Extract imports
        imports = self.extractor.extract_imports(content, lang)
        if not imports:
            return PackageValidationResult(issues=[], validated_count=0, registry_found=True)

        # Get known packages
        known_packages, registry_found = self.registry.get_packages(lang)

        # Get standard library for filtering
        stdlib = self._get_stdlib(lang)

        issues = []
        validated_count = 0

        for package, line in imports:
            validated_count += 1

            # Skip standard library
            if self._is_stdlib(package, lang, stdlib):
                continue

            # Check if package is known
            if self._is_known_package(package, lang, known_packages):
                continue

            # Package not found - create issue
            issue = self._create_issue(
                package=package,
                line=line,
                file_path=file_path,
                lang=lang,
                known_packages=known_packages,
                registry_found=registry_found
            )
            if issue:
                issues.append(issue)

        return PackageValidationResult(
            issues=issues,
            validated_count=validated_count,
            registry_found=registry_found
        )

    def _get_stdlib(self, lang: Language) -> Set[str]:
        """Get standard library for a language."""
        if lang == Language.PYTHON:
            return PYTHON_STDLIB
        elif lang in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            return NODE_BUILTINS
        elif lang == Language.PHP:
            return PHP_BUILTINS
        return set()

    def _is_stdlib(self, package: str, lang: Language, stdlib: Set[str]) -> bool:
        """Check if package is a standard library module."""
        # Direct match
        if package in stdlib:
            return True

        # Case-insensitive for Python
        if lang == Language.PYTHON:
            if package.lower() in {s.lower() for s in stdlib}:
                return True

        # PHP: Check if it's a built-in class
        if lang == Language.PHP:
            # Extract first part of namespace
            first_part = package.split('\\')[0]
            if first_part in stdlib:
                return True

        return False

    def _is_known_package(
        self,
        package: str,
        lang: Language,
        known_packages: Set[str]
    ) -> bool:
        """Check if package is in the known packages list."""
        # Direct match
        if package in known_packages:
            return True

        # Case-insensitive match for npm/pip
        if lang in (Language.JAVASCRIPT, Language.TYPESCRIPT, Language.PYTHON):
            package_lower = package.lower()
            if any(p.lower() == package_lower for p in known_packages):
                return True

        # PHP: Check namespace against installed packages
        if lang == Language.PHP:
            # PRIORITY 1: Check if namespace exists in vendor/ (dynamic, no mapping needed!)
            if self.registry.is_namespace_installed(package):
                return True

            # PRIORITY 2: Static namespace mapping (fallback for projects without vendor/)
            package_with_slash = package + '\\'
            for composer_pkg, namespaces in PHP_NAMESPACE_MAPPING.items():
                if composer_pkg in known_packages or composer_pkg.lower() in {p.lower() for p in known_packages}:
                    for ns in namespaces:
                        ns_clean = ns.rstrip('\\')
                        if package == ns_clean or package.startswith(ns_clean + '\\'):
                            return True

            # PRIORITY 3: Direct namespace/package matching (PSR-4 from composer.json)
            for known in known_packages:
                if known.startswith(package) or package.startswith(known):
                    return True
                known_ns = known.replace('/', '\\')
                if package.startswith(known_ns) or known_ns.startswith(package):
                    return True

        return False

    def _create_issue(
        self,
        package: str,
        line: int,
        file_path: str,
        lang: Language,
        known_packages: Set[str],
        registry_found: bool
    ) -> Optional[PackageIssue]:
        """Create a PackageIssue for an unknown package."""

        # Find similar packages (potential typos/slopsquatting)
        similar = find_similar_packages(package, known_packages)

        # Calculate confidence
        confidence = self._calculate_confidence(
            package=package,
            lang=lang,
            similar=similar,
            registry_found=registry_found
        )

        # Skip low confidence issues
        if confidence < 0.3:
            return None

        # Build reason
        if similar:
            is_slopsquatting = True
            reason = f"Package not found. Similar: {', '.join(s[0] for s in similar[:3])}"
        elif not registry_found:
            is_slopsquatting = False
            reason = "Package not found (no registry file found)"
            confidence *= 0.5  # Reduce confidence if no registry
        else:
            is_slopsquatting = False
            reason = "Package not found in project dependencies"

        # Determine import type
        import_type = {
            Language.PHP: 'composer',
            Language.JAVASCRIPT: 'npm',
            Language.TYPESCRIPT: 'npm',
            Language.PYTHON: 'pip',
        }.get(lang, 'unknown')

        return PackageIssue(
            package=package,
            file=file_path,
            line=line,
            confidence=confidence,
            import_type=import_type,
            reason=reason,
            suggestions=[s[0] for s in similar[:5]],
            is_slopsquatting=len(similar) > 0
        )

    def _calculate_confidence(
        self,
        package: str,
        lang: Language,
        similar: List[Tuple[str, int]],
        registry_found: bool
    ) -> float:
        """Calculate confidence score for a package issue."""
        confidence = 1.0

        # No registry file found -> lower confidence
        if not registry_found:
            confidence *= 0.5

        # Similar package exists -> HIGHER confidence (likely typo/slopsquatting!)
        if similar:
            closest_distance = similar[0][1]
            if closest_distance == 1:
                confidence = 0.95  # Very likely typo
            elif closest_distance == 2:
                confidence = 0.85

        # Very common package names -> lower confidence
        common_packages = {
            'utils', 'helpers', 'common', 'shared', 'lib', 'core',
            'config', 'types', 'models', 'services', 'components',
        }
        if package.lower() in common_packages:
            confidence *= 0.6

        # Scoped packages are less likely hallucinated
        if package.startswith('@'):
            confidence *= 0.8

        # Short package names are more suspicious
        if len(package) <= 2:
            confidence *= 1.2

        # Package with weird characters (potential attack)
        if re.search(r'[^a-zA-Z0-9_\-/@.]', package):
            confidence = 0.98

        return min(1.0, max(0.0, confidence))


# =============================================================================
# REPORT FORMATTER
# =============================================================================

def format_package_report(result: PackageValidationResult) -> str:
    """Format validation result as a readable report."""
    if not result.has_issues:
        if result.validated_count == 0:
            return "Package Validation: No imports found"
        return f"Package Validation: ✓ All {result.validated_count} imports verified"

    parts = [f"Package Validation: {len(result.issues)} potential issues"]

    if not result.registry_found:
        parts.append("⚠️ No package registry found (composer.json/package.json/requirements.txt)")
        parts.append("")

    # Group by severity
    high = [i for i in result.issues if i.severity == "HIGH"]
    medium = [i for i in result.issues if i.severity == "MEDIUM"]

    if high:
        parts.append("")
        parts.append("🔴 HIGH CONFIDENCE (likely hallucinated):")
        for issue in high[:5]:
            slopwarn = " ⚠️ SLOPSQUATTING RISK!" if issue.is_slopsquatting else ""
            parts.append(f"  {issue.package} in {issue.file}:{issue.line} [{issue.confidence:.0%}]{slopwarn}")
            if issue.suggestions:
                parts.append(f"    → Did you mean: {', '.join(issue.suggestions[:3])}?")

    if medium:
        parts.append("")
        parts.append("🟡 MEDIUM CONFIDENCE:")
        for issue in medium[:3]:
            parts.append(f"  {issue.package} in {issue.file}:{issue.line} [{issue.confidence:.0%}]")

    parts.append("")
    parts.append("Run `composer require <package>` / `npm install <package>` / `pip install <package>` to add missing packages.")

    return "\n".join(parts)
