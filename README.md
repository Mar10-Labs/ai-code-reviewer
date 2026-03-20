# AI CODE REVIEWER

An AI-powered code review agent that connects to GitHub repositories, analyzes Pull Requests automatically, and leaves intelligent code review comments directly on the diff — just like a senior developer would, but in seconds and for free.

## Features

- Automated code review using AI
- Multi-agent architecture for specialized analysis
- Support for multiple AI providers (Gemini, Groq, Claude, Ollama)
- GitHub webhook integration
- Review metrics and history tracking
- Clean Architecture design

## Tech Stack

| Component | Technology |
|-----------|------------|
| API Backend | FastAPI (Python) |
| AI Orchestration | LangGraph |
| AI Providers | LiteLLM (Gemini, Claude, Groq, Ollama) |
| Database | SQLite |
| Containerization | Docker Compose |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+ (for local development)
- API keys for AI providers (optional)

### 1. Clone the Repository

```bash
git clone https://github.com/Mar10-Labs/ai-code-reviewer.git
cd ai-code-reviewer
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# AI Provider (choose one)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key

# Or use Groq (free tier available)
# LLM_PROVIDER=groq
# GROQ_API_KEY=your-groq-api-key

# Models
LLM_STANDARD_MODEL=gemini/gemini-1.5-flash
LLM_PREMIUM_MODEL=gemini/gemini-1.5-pro

# GitHub Integration
GITHUB_TOKEN=your-github-token
GITHUB_WEBHOOK_SECRET=your-webhook-secret
```

### 3. Start with Docker

```bash
docker compose up --build
```

The API will be available at:
- **API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **Ollama**: http://localhost:11434

### 4. Local Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest -v

# Start development server
uvicorn src.api.main:app --reload
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        MASTER AGENT                          │
│  Orchestrates all specialized agents                       │
└────────────────────┬──────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┬─────────────┬──────────┐
     ▼               ▼               ▼             ▼          ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ ┌──────────┐
│  CODE    │  │ SECURITY │  │PERFORMANCE│  │ TECH    │ │  TESTS  │
│ QUALITY  │  │          │  │          │  │  DEBT   │ │          │
└──────────┘  └──────────┘  └──────────┘  └──────────┘ └──────────┘
                                                              │
     ┌────────────────────────────────────────────────────────┘
     ▼
┌──────────┐  ┌──────────┐
│  STYLE   │  │ DEVOPS   │
└──────────┘  └──────────┘
```

## Project Structure

```
ai-code-reviewer/
├── src/
│   ├── agents/              # AI Agent framework
│   │   ├── base_agent.py
│   │   ├── master_agent.py
│   │   └── specialists/
│   │       └── devops_agent.py
│   ├── api/                # FastAPI endpoints
│   │   ├── main.py
│   │   └── routes/
│   ├── infrastructure/      # External services
│   │   ├── services/
│   │   │   ├── db.py
│   │   │   └── git_service.py
│   │   └── mcp_server/
│   └── models/             # Pydantic schemas
│       ├── agent_state.py
│       ├── review_comment.py
│       └── mcp_schemas.py
├── tests/                  # Unit tests
├── data/                   # SQLite database
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/agent/command` | Execute agent command |
| GET | `/agent/status` | Get git status |
| GET | `/agent/commands` | List available commands |
| POST | `/webhook` | GitHub webhook endpoint |

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_review_comment.py -v
```

## Available Agents

| Agent | Purpose |
|-------|---------|
| MasterAgent | Orchestrates workflow and delegates tasks |
| DevOpsAgent | Handles Git operations, branches, commits, merges |
| CodeQualityAgent | Reviews naming, duplication, complexity (future) |
| SecurityAgent | Reviews security vulnerabilities (future) |
| PerformanceAgent | Reviews performance issues (future) |

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Commit changes: `git commit -m "feat: add new feature"`
4. Push to branch: `git push origin feat/your-feature`
5. Open a Pull Request

## License

MIT

## Links

- [Documentation](./docs/)
- [Issues](https://github.com/Mar10-Labs/ai-code-reviewer/issues)
- [Pull Requests](https://github.com/Mar10-Labs/ai-code-reviewer/pulls)
