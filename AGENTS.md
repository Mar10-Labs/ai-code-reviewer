# AI Code Reviewer - Project Context

## Project Objective

**AI Code Reviewer** - An AI-powered code review agent that connects to GitHub repositories, analyzes Pull Requests automatically, and leaves intelligent code review comments.

## Architecture (from Project Brief PDF)

```
MasterAgent (orquestador)
    └── Coordina sub-agentes EN PARALELO (asyncio.gather)
            ├── CodeQualityAgent     → naming, duplicación, complejidad
            ├── PerformanceAgent     → algoritmos, loops, eficiencia
            ├── SecurityAgent       → secrets, SQL injection, XSS
            ├── DocumentationAgent  → docstrings, comentarios, TODO/FIXME
            └── TestingAgent        → coverage, edge cases
```

## Working with Mario

### How I work
1. **Lee el PDF** `AI_Code_Reviewer_Project_Brief.pdf` si hay dudas sobre arquitectura
2. **Pregunta** antes de agregar algo que no esté en el PDF o que cambie la dirección del proyecto
3. **Commits atómicos** con `--no-gpg-sign` (hay problema con GPG passphrase)
4. **PRs** para todo cambio significativo, luego merge

### Conventions
- Branch naming: `feat/descripcion-corta`
- Commits: imperativo en inglés + issue number
- Tests: pytest, objetivo 90% coverage mínimo
- Push remote: `git@github.com:Mar10-Labs/ai-code-reviewer.git`

## Current State

- ✅ 5 specialized agents implemented
- ✅ MasterAgent orchestrates in parallel
- ✅ 155 tests passing
- ✅ 91% coverage
- ✅ All PRs merged to main

## File Structure

```
src/
├── agents/
│   ├── master_agent.py          # Orchestrator
│   └── specialists/
│       ├── code_quality_agent.py
│       ├── performance_agent.py
│       ├── security_agent.py
│       ├── documentation_agent.py
│       └── testing_agent.py
├── models/                      # Pydantic schemas
├── llm/                         # LLM adapters (Groq, Gemini, Ollama)
├── api/                         # FastAPI routes
└── infrastructure/
    ├── db.py                    # SQLite service
    └── mcp_server/              # MCP tools

tests/                           # pytest tests
```

## Commands

```bash
# Install & activate venv
python -m venv .venv && source .venv/bin/activate

# Run tests
pytest tests/ --cov=src --cov-report=term-missing

# Start API
uvicorn src.api.main:app --reload

# Docker
docker compose up --build
```

## Remote

- GitHub: `git@github.com:Mar10-Labs/ai-code-reviewer.git`
- Use `gh` CLI for issues and PRs
- Origin: `origin`
