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

## My Agent System (`.agents/` folder)

When working on this project, I use specialized agents defined in `.agents/`:

| Agent | File | Responsibility |
|-------|------|----------------|
| architect | `.agents/architect.md` | Architecture & design decisions |
| code_quality | `.agents/code_quality.md` | Naming, duplication, complexity |
| security | `.agents/security.md` | Vulnerabilities, secrets |
| performance | `.agents/performance.md` | Efficiency, algorithms |
| documentation | `.agents/documentation.md` | Docstrings, comments |
| testing | `.agents/testing.md` | Coverage, edge cases |
| git_flow | `.agents/git_flow.md` | Git workflow, branches |
| solid | `.agents/solid.md` | SOLID principles |

## How I Work

### 1. Before Starting Any Task
- Read AGENTS.md for context
- Read relevant `.agents/*.md` files for the task at hand
- Consult AI_Code_Reviewer_Project_Brief.pdf if unsure about architecture

### 2. Task Execution
1. When you ask me to do something, I identify which agents should work
2. Multiple agents can work in parallel WITHOUT stepping on each other
3. Each agent has a specific scope (see their .md file)
4. Results are aggregated at the end

### 3. Git Workflow (from git_flow.md)
1. Always branch from `main`: `git checkout main && git pull origin main`
2. Create branch: `git checkout -b feat/nombre-descriptivo`
3. Make changes, commit with `--no-gpg-sign` (GPG has passphrase issues)
4. Push: `git push -u origin feat/nombre`
5. Create PR with `gh pr create`
6. **After completing the task**: Ask you "Should I merge and push to main?"
7. After merge: `git checkout main && git pull origin main`

### 4. Important Rules
- **NO automatic push** - I must ask permission before pushing
- **NO automatic merge** - I must ask permission before merging
- **NO modifications** to `.agents/` files without your approval
- **Branch from main always**

## Conventions

- Branch naming: `feat/descripcion-corta`
- Commits: imperative in English + issue number
- Tests: pytest, minimum 90% coverage
- Push remote: `git@github.com:Mar10-Labs/ai-code-reviewer.git`

## Current State

- ✅ 5 specialized code review agents implemented (LangGraph)
- ✅ MasterAgent orchestrates in parallel
- ✅ 156 tests passing
- ✅ 91% coverage
- ✅ LangGraph diagram generated at `img/code_review_graph.png`
- ✅ Agent prompts created in `.agents/` folder

## File Structure

```
src/
├── agents/
│   ├── master_agent.py          # Orchestrator (LangGraph)
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

.agents/                         # My agent prompts (for me, not executable)
├── architect.md
├── code_quality.md
├── security.md
├── performance.md
├── documentation.md
├── testing.md
├── git_flow.md
└── solid.md

tests/                           # pytest tests
img/                             # diagrams
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
