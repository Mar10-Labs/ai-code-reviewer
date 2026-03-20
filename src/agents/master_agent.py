import asyncio
from typing import Optional, TypedDict, Annotated
from dataclasses import dataclass, field
from enum import Enum
import operator

from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage

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


class ReviewState(TypedDict):
    messages: list[BaseMessage]
    diff_content: str
    repository: str
    pr_number: Optional[int]
    agent_results: dict
    summary: dict
    errors: list[str]


@dataclass
class MasterResponse:
    intent: Intent
    message: str
    agent_results: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    context: Optional[ConversationContext] = None


def create_review_graph():
    agents = {
        "code_quality": CodeQualityAgent(),
        "performance": PerformanceAgent(),
        "security": SecurityAgent(),
        "documentation": DocumentationAgent(),
        "testing": TestingAgent(),
    }
    
    async def run_code_quality(state: ReviewState) -> ReviewState:
        try:
            result = await agents["code_quality"].execute({
                "diff_content": state["diff_content"],
                "file_path": "",
                "language": "python"
            })
            state["agent_results"]["code_quality"] = result
        except Exception as e:
            state["errors"].append(f"code_quality: {str(e)}")
        return state
    
    async def run_performance(state: ReviewState) -> ReviewState:
        try:
            result = await agents["performance"].execute({
                "diff_content": state["diff_content"],
                "file_path": "",
                "language": "python"
            })
            state["agent_results"]["performance"] = result
        except Exception as e:
            state["errors"].append(f"performance: {str(e)}")
        return state
    
    async def run_security(state: ReviewState) -> ReviewState:
        try:
            result = await agents["security"].execute({
                "diff_content": state["diff_content"],
                "file_path": ""
            })
            state["agent_results"]["security"] = result
        except Exception as e:
            state["errors"].append(f"security: {str(e)}")
        return state
    
    async def run_documentation(state: ReviewState) -> ReviewState:
        try:
            result = await agents["documentation"].execute({
                "diff_content": state["diff_content"],
                "file_path": "",
                "language": "python"
            })
            state["agent_results"]["documentation"] = result
        except Exception as e:
            state["errors"].append(f"documentation: {str(e)}")
        return state
    
    async def run_testing(state: ReviewState) -> ReviewState:
        try:
            result = await agents["testing"].execute({
                "diff_content": state["diff_content"],
                "file_path": "",
                "existing_tests": ""
            })
            state["agent_results"]["testing"] = result
        except Exception as e:
            state["errors"].append(f"testing: {str(e)}")
        return state
    
    def aggregate_results(state: ReviewState) -> ReviewState:
        summary = {
            "total_issues": 0,
            "critical": 0,
            "warnings": 0,
            "suggestions": 0,
            "by_agent": {}
        }
        
        for agent_name, result in state["agent_results"].items():
            if isinstance(result, dict):
                summary["by_agent"][agent_name] = result.get("summary", "")
                for r in result.get("results", []):
                    if hasattr(r, 'severity'):
                        summary["total_issues"] += 1
                        if r.severity == "critical":
                            summary["critical"] += 1
                        elif r.severity == "warning":
                            summary["warnings"] += 1
                        else:
                            summary["suggestions"] += 1
        
        state["summary"] = summary
        return state
    
    async def run_all_agents_parallel(state: ReviewState) -> ReviewState:
        tasks = [
            run_code_quality(state.copy()),
            run_performance(state.copy()),
            run_security(state.copy()),
            run_documentation(state.copy()),
            run_testing(state.copy()),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        state_copy = state.copy()
        for i, result in enumerate(results):
            if isinstance(result, dict):
                agent_names = ["code_quality", "performance", "security", "documentation", "testing"]
                if i < len(agent_names):
                    state_copy["agent_results"][agent_names[i]] = result
        
        return aggregate_results(state_copy)
    
    builder = StateGraph(ReviewState)
    
    builder.add_node("code_quality", run_code_quality)
    builder.add_node("performance", run_performance)
    builder.add_node("security", run_security)
    builder.add_node("documentation", run_documentation)
    builder.add_node("testing", run_testing)
    builder.add_node("aggregate", aggregate_results)
    
    builder.set_entry_point("security")
    builder.add_edge("security", "code_quality")
    builder.add_edge("code_quality", "performance")
    builder.add_edge("performance", "documentation")
    builder.add_edge("documentation", "testing")
    builder.add_edge("testing", "aggregate")
    builder.add_edge("aggregate", END)
    
    return builder.compile()


class MasterAgent:
    def __init__(self):
        self.context = ConversationContext()
        self._history: list[MasterResponse] = []
        self.graph = create_review_graph()

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
        
        initial_state: ReviewState = {
            "messages": [HumanMessage(content=f"Review this diff:\n{diff_content}")],
            "diff_content": diff_content,
            "repository": repository,
            "pr_number": pr_number,
            "agent_results": {},
            "summary": {},
            "errors": []
        }
        
        result = await self.graph.ainvoke(initial_state)
        
        return MasterResponse(
            intent=Intent.REVIEW_PR,
            message=f"Code review completed: {result['summary'].get('total_issues', 0)} issues found",
            agent_results=list(result["agent_results"].values()),
            summary=result["summary"],
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
