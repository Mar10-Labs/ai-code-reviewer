import asyncio
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field

from src.agents.base_agent import BaseAgent, AgentConfig, AgentType, AgentCapability
from src.agents.specialists import (
    CodeQualityAgent,
    PerformanceAgent,
    SecurityAgent,
    DocumentationAgent,
    TestingAgent
)


class Intent(Enum):
    REVIEW_PR = "review_pr"
    ANALYZE_FILE = "analyze_file"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ConversationContext:
    repository: str = ""
    pr_number: Optional[int] = None
    diff_content: str = ""
    files_to_review: list[str] = field(default_factory=list)
    workflow_step: str = "idle"


@dataclass
class MasterResponse:
    intent: Intent
    message: str
    agent_results: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    context: Optional[ConversationContext] = None


class MasterAgent:
    def __init__(self):
        self.context = ConversationContext()
        self._history: list[MasterResponse] = []
        
        self.agents = [
            CodeQualityAgent(),
            PerformanceAgent(),
            SecurityAgent(),
            DocumentationAgent(),
            TestingAgent(),
        ]

    async def process(self, user_input: str) -> MasterResponse:
        intent = self.classify_intent(user_input)
        
        handlers = {
            Intent.REVIEW_PR: self._handle_review_pr,
            Intent.ANALYZE_FILE: self._handle_analyze_file,
            Intent.HELP: self._handle_help,
            Intent.UNKNOWN: self._handle_unknown,
        }
        
        handler = handlers.get(intent)
        if not handler:
            handler = self._handle_unknown
        response = await handler(user_input)
        response.intent = intent
        
        self._history.append(response)
        return response

    def classify_intent(self, text: str) -> Intent:
        text_lower = text.lower()
        
        if "review" in text_lower or "pr" in text_lower:
            return Intent.REVIEW_PR
        if "analyze" in text_lower or "check" in text_lower:
            return Intent.ANALYZE_FILE
        if "help" in text_lower or "ayuda" in text_lower:
            return Intent.HELP
        
        return Intent.UNKNOWN

    async def review_pr(self, diff_content: str, repository: str = "", pr_number: Optional[int] = None) -> MasterResponse:
        self.context.diff_content = diff_content
        self.context.repository = repository
        self.context.pr_number = pr_number
        
        tasks = [agent.execute({"diff_content": diff_content}) for agent in self.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        agent_results = []
        summary = {
            "total_issues": 0,
            "critical": 0,
            "warnings": 0,
            "suggestions": 0,
            "by_agent": {}
        }
        
        for agent, result in zip(self.agents, results):
            if isinstance(result, Exception):
                agent_results.append({
                    "agent": agent.config.name,
                    "error": str(result)
                })
                continue
            
            if isinstance(result, dict):
                agent_results.append(result)
                summary["by_agent"][agent.config.name] = result.get("summary", "")
                
                for r in result.get("results", []):
                    if hasattr(r, 'severity'):
                        summary["total_issues"] += 1
                        if r.severity == "critical":
                            summary["critical"] += 1
                        elif r.severity == "warning":
                            summary["warnings"] += 1
                        else:
                            summary["suggestions"] += 1
        
        return MasterResponse(
            intent=Intent.REVIEW_PR,
            message=f"Code review completed: {summary['total_issues']} issues found",
            agent_results=agent_results,
            summary=summary,
            context=self.context
        )

    async def _handle_review_pr(self, user_input: str) -> MasterResponse:
        return await self.review_pr(
            diff_content=user_input,
            repository=self.context.repository,
            pr_number=self.context.pr_number
        )

    async def _handle_analyze_file(self, user_input: str) -> MasterResponse:
        return await self.review_pr(
            diff_content=user_input,
            repository=self.context.repository
        )

    async def _handle_help(self, user_input: str) -> MasterResponse:
        help_text = '''
╔══════════════════════════════════════════════════════════╗
║              AI CODE REVIEWER - COMMANDS                ║
╠══════════════════════════════════════════════════════════╣
║                                                           ║
║  "review <pr_url>"   → Analyze a Pull Request            ║
║  "analyze <file>"    → Analyze a file or code snippet    ║
║  "help"              → Show this help                    ║
║                                                           ║
╚══════════════════════════════════════════════════════════╝
'''
        return MasterResponse(
            intent=Intent.HELP,
            message=help_text
        )

    async def _handle_unknown(self, user_input: str) -> MasterResponse:
        return MasterResponse(
            intent=Intent.UNKNOWN,
            message=f"No entendí: '{user_input}'\n\nEscribí 'help' para ver los comandos disponibles."
        )

    def get_available_commands(self) -> list[str]:
        return [
            "review <pr_url> - Review a Pull Request",
            "analyze <file> - Analyze a file or code",
            "help - Show available commands"
        ]
