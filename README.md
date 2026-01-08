# Chainguard - MCP Server for Claude Code

[![License: Polyform Noncommercial](https://img.shields.io/badge/License-Polyform%20NC-blue.svg)](https://polyformproject.org/licenses/noncommercial/1.0.0)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

**Chainguard** is a Model Context Protocol (MCP) server that enhances Claude Code with task tracking, syntax validation, long-term memory, and intelligent context management.

## Features

### Core Features
- **Task Scope Management** - Define task boundaries, acceptance criteria, and track progress
- **Automatic Syntax Validation** - PHP, JavaScript, JSON, Python, TypeScript validation on file changes
- **Smart Context Tracking** - Canary-based context refresh ensures Claude never loses important instructions
- **HTTP Endpoint Testing** - Test endpoints with session support and automatic auth detection

### Long-Term Memory (v5.1+)
- **Semantic Code Search** - Natural language queries like "Where is authentication handled?"
- **ChromaDB Integration** - Local vector database, 100% offline
- **Automatic Indexing** - Code structure, functions, database schema, architecture patterns
- **Project Isolation** - Each project has its own isolated memory

### Deep Logic Summaries (v5.4)
- **Code Understanding** - Extracts human-readable summaries of what code actually does
- **Purpose Inference** - Recognizes patterns from docstrings, comments, and naming conventions
- **Multi-Language Support** - Python, PHP, JavaScript, TypeScript

### Architecture Analysis (v5.3+)
- **Pattern Detection** - MVC, MVVM, Clean Architecture, Hexagonal, Layered, API-first
- **Framework Recognition** - Laravel, Django, React, Vue, Angular, FastAPI, and more
- **AST Analysis** - Tree-sitter based code parsing with regex fallback

### Task Modes
| Mode | Use Case |
|------|----------|
| `programming` | Code, bugs, features (default) |
| `content` | Books, articles, documentation |
| `devops` | Server admin, CLI tools, WordPress |
| `research` | Analysis, information gathering |
| `generic` | Minimal tracking |

## Installation

### Quick Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/provimedia/chainguard/main/installer/install.sh | bash
```

### Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/provimedia/chainguard.git
cd chainguard
```

2. Run the installer:
```bash
./installer/install.sh
```

3. Restart Claude Code

### Requirements

- Python 3.9+
- Claude Code CLI
- Optional: `chromadb` and `sentence-transformers` for Long-Term Memory

## Usage

### Basic Workflow

```python
# 1. Start a task (REQUIRED)
chainguard_set_scope(
    description="Implement user login",
    mode="programming",
    acceptance_criteria=["Login works", "Tests pass"]
)

# 2. Track changes (auto-validates syntax)
chainguard_track(file="src/AuthController.php", ctx="🔗")

# 3. Check status
chainguard_status(ctx="🔗")

# 4. Complete task
chainguard_finish(confirmed=True)
```

### Long-Term Memory

```python
# Initialize memory (once per project)
chainguard_memory_init()

# Semantic search
chainguard_memory_query(query="Where is authentication handled?")

# Generate deep logic summaries
chainguard_memory_summarize()
```

### Database Schema Inspection

```python
# Connect to database
chainguard_db_connect(
    host="localhost",
    user="root",
    password="...",
    database="myapp"
)

# Get schema (prevents SQL field name guessing)
chainguard_db_schema()
```

## Available Tools

### Core Tools
| Tool | Description |
|------|-------------|
| `chainguard_set_scope` | Define task scope and criteria |
| `chainguard_track` | Track file changes with syntax validation |
| `chainguard_status` | Ultra-compact status line |
| `chainguard_finish` | Complete task with validation |

### Memory Tools
| Tool | Description |
|------|-------------|
| `chainguard_memory_init` | Initialize project memory |
| `chainguard_memory_query` | Semantic code search |
| `chainguard_memory_summarize` | Generate deep logic summaries |
| `chainguard_memory_status` | Show memory statistics |

### Analysis Tools
| Tool | Description |
|------|-------------|
| `chainguard_analyze` | Pre-flight code analysis |
| `chainguard_analyze_code` | AST-based code analysis |
| `chainguard_detect_architecture` | Detect architecture patterns |

### Database Tools
| Tool | Description |
|------|-------------|
| `chainguard_db_connect` | Connect to database |
| `chainguard_db_schema` | Get database schema |
| `chainguard_db_table` | Get table details |

### HTTP Testing Tools
| Tool | Description |
|------|-------------|
| `chainguard_set_base_url` | Set base URL for tests |
| `chainguard_test_endpoint` | Test HTTP endpoint |
| `chainguard_login` | Login and store session |

## Architecture

```
~/.chainguard/
├── chainguard/           # MCP Server Package (20 modules)
│   ├── handlers.py       # Tool handlers
│   ├── memory.py         # Long-Term Memory
│   ├── code_summarizer.py # Deep Logic Extraction
│   ├── ast_analyzer.py   # AST Analysis
│   ├── architecture.py   # Pattern Detection
│   └── ...
├── chainguard_mcp.py     # MCP Entry Point
├── hooks/                # Claude Code Hooks
│   ├── chainguard_enforcer.py    # PreToolUse Hook
│   └── chainguard_memory_inject.py # Memory Injection
├── projects/             # Project State Storage
├── memory/               # ChromaDB Vector Storage
└── templates/            # CLAUDE.md Templates
```

## Documentation

- [Usage Guide](docs/USAGE.md)
- [Testing Guide](docs/TESTING.md)
- [Long-Term Memory Concept](docs/LONG-TERM-MEMORY-CONCEPT.md)
- [Sync & Install Checklist](SYNCINSTALL.md)

## Development

### Running Tests

```bash
cd src/mcp-server
python3 -m pytest tests/ -v
```

### Test Coverage

| Module | Tests |
|--------|-------|
| Core (cache, models, handlers) | 88 |
| Validators | 48 |
| Analyzers | 46 |
| Memory System | 103 |
| Code Summarizer | 45 |
| **Total** | **605+** |

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the **Polyform Noncommercial License 1.0.0**.

**You may:**
- Use this software for any noncommercial purpose
- Modify and create derivative works
- Share and distribute the software

**You may not:**
- Sell this software or use it for commercial purposes
- Only Provimedia GmbH is authorized to sell this software

See the [LICENSE](LICENSE) file for full details.

## Credits

Created and maintained by **[Provimedia GmbH](https://provimedia.de)**

## Changelog

### v5.4.0
- Deep Logic Summaries with `code_summarizer.py`
- New `chainguard_memory_summarize` tool
- `code_summaries` collection for semantic code understanding
- 45 new tests for code summarizer

### v5.3.0
- AST Analysis with tree-sitter
- Architecture Pattern Detection
- Framework Recognition
- Memory Export/Import

### v5.2.0
- Smart Context Injection
- Automatic memory updates on track/finish

### v5.1.0
- Long-Term Memory with ChromaDB
- Semantic code search
- Project isolation

### v5.0.0
- Task Mode System (programming, content, devops, research)
- Mode-specific tools

---

**Made with care by Provimedia GmbH**
