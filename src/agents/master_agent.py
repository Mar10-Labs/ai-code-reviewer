import asyncio
import re
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from src.agents.base_agent import (
    BaseAgent, AgentConfig, AgentResponse, AgentType, AgentCapability
)
from src.agents.specialists.devops_agent import DevOpsAgent


class Intent(Enum):
    EXECUTE_ISSUE = "execute_issue"
    CHECK_STATUS = "check_status"
    REVIEW_CODE = "review_code"
    CREATE_BRANCH = "create_branch"
    COMMIT_CHANGES = "commit_changes"
    MERGE_BRANCH = "merge_branch"
    RUN_TESTS = "run_tests"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ConversationContext:
    current_issue: Optional[int] = None
    current_issue_title: str = ""
    pending_files: list[dict] = field(default_factory=list)
    workflow_step: str = "idle"
    auto_mode: bool = False


@dataclass  
class MasterResponse:
    intent: Intent
    message: str
    agent_results: list[AgentResponse] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    context: Optional[ConversationContext] = None


class MasterAgent:
    def __init__(self):
        self.devops = DevOpsAgent()
        self.context = ConversationContext()
        self._history: list[MasterResponse] = []

    async def process(self, user_input: str) -> MasterResponse:
        intent = self.classify_intent(user_input)
        
        handlers = {
            Intent.EXECUTE_ISSUE: self._handle_execute_issue,
            Intent.CHECK_STATUS: self._handle_check_status,
            Intent.CREATE_BRANCH: self._handle_create_branch,
            Intent.COMMIT_CHANGES: self._handle_commit,
            Intent.MERGE_BRANCH: self._handle_merge,
            Intent.RUN_TESTS: self._handle_run_tests,
            Intent.HELP: self._handle_help,
        }
        
        handler = handlers.get(intent, self._handle_unknown)
        response = await handler(user_input)
        response.intent = intent
        
        self._history.append(response)
        return response

    def classify_intent(self, text: str) -> Intent:
        text_lower = text.lower()
        
        if re.search(r'execute\s+#?\d+|issue\s+#?\d+', text_lower):
            return Intent.EXECUTE_ISSUE
        if 'branch' in text_lower and ('create' in text_lower or 'new' in text_lower):
            return Intent.CREATE_BRANCH
        if any(word in text_lower for word in ['status', 'estado', 'git']):
            return Intent.CHECK_STATUS
        if any(word in text_lower for word in ['commit', 'commits']):
            return Intent.COMMIT_CHANGES
        if any(word in text_lower for word in ['merge', 'pr', 'pull request']):
            return Intent.MERGE_BRANCH
        if any(word in text_lower for word in ['test', 'tests', 'pytest']):
            return Intent.RUN_TESTS
        if any(word in text_lower for word in ['help', 'ayuda', 'comandos']):
            return Intent.HELP
        
        return Intent.UNKNOWN

    def extract_issue_number(self, text: str) -> Optional[int]:
        match = re.search(r'#?(\d+)', text)
        return int(match.group(1)) if match else None

    async def _handle_execute_issue(self, user_input: str) -> MasterResponse:
        issue_number = self.extract_issue_number(user_input)
        
        if not issue_number:
            return MasterResponse(
                intent=Intent.EXECUTE_ISSUE,
                message="¿Cuál es el número del issue que querés ejecutar?",
                questions=[{
                    "text": "Ingresá el número del issue (ej: 10)",
                    "options": ["Cancelar"]
                }]
            )

        self.context.current_issue = issue_number
        self.context.current_issue_title = self._guess_issue_title(user_input, issue_number)
        self.context.workflow_step = "verifying"

        verify_result = await self.devops.execute({"action": "verify_state"})
        
        status_data = verify_result.data or {}
        questions = []
        actions_needed = []

        if not status_data.get("on_main"):
            actions_needed.append(f"Cambiar de {status_data.get('current_branch')} a main")
        
        orphan_branches = status_data.get("orphan_branches", [])
        if orphan_branches:
            actions_needed.append(f"Limpiar {len(orphan_branches)} branches huérfanos")
        
        if not status_data.get("is_clean"):
            actions_needed.append(f"Hay {status_data.get('changes_count')} cambios sin commitear")

        if actions_needed or not status_data.get("on_main"):
            questions.append({
                "id": "prepare_issue",
                "text": f"Issue #{issue_number}: {self.context.current_issue_title}",
                "status": f"Branch actual: {status_data.get('current_branch', 'unknown')}",
                "actions_needed": actions_needed,
                "options": [
                    {"value": "prepare", "label": "Sí, preparar entorno limpio"},
                    {"value": "continue", "label": "Continuar en branch actual"},
                    {"value": "cancel", "label": "Cancelar"}
                ]
            })
            
            return MasterResponse(
                intent=Intent.EXECUTE_ISSUE,
                message=f"Preparando issue #{issue_number}: {self.context.current_issue_title}",
                agent_results=[verify_result],
                questions=questions,
                context=self.context
            )

        return await self._prepare_and_execute(issue_number)

    async def _prepare_and_execute(self, issue_number: int) -> MasterResponse:
        prepare_result = await self.devops.execute({
            "action": "prepare_branch",
            "issue_number": issue_number,
            "issue_title": self.context.current_issue_title
        })

        if not prepare_result.success:
            return MasterResponse(
                intent=Intent.EXECUTE_ISSUE,
                message=f"Error preparando branch: {prepare_result.message}",
                agent_results=[prepare_result]
            )

        branch_created = prepare_result.data.get("branch", "unknown") if prepare_result.data else "unknown"
        
        tasks = [
            self.devops.execute({
                "action": "create_file",
                "file_path": f"src/models/agent_state.py",
                "content": self._generate_agent_state_code()
            }),
            self.devops.execute({
                "action": "create_file", 
                "file_path": "tests/test_agent_state.py",
                "content": self._generate_agent_state_tests()
            })
        ]

        file_results = await asyncio.gather(*tasks)
        
        test_result = await self.devops.execute({"action": "run_tests", "command": "pytest -v"})

        all_files_created = all(r.success for r in file_results)
        
        questions = []
        if all_files_created and test_result.success:
            questions.append({
                "id": "commit_changes",
                "text": "Archivos creados y tests pasando",
                "files": [r.data.get("file_path") for r in file_results if r.success and r.data],
                "tests": "✓ Todos los tests pasaron",
                "options": [
                    {"value": "commit", "label": "Hacer commit"},
                    {"value": "show_diff", "label": "Ver cambios antes de commit"},
                    {"value": "skip", "label": "No commitear aún"}
                ]
            })
        
        return MasterResponse(
            intent=Intent.EXECUTE_ISSUE,
            message=f"Issue #{issue_number} listo para revisar\nBranch: {branch_created}",
            agent_results=[prepare_result] + file_results + [test_result],
            questions=questions,
            context=self.context
        )

    def _guess_issue_title(self, text: str, issue_number: int) -> str:
        common_titles = {
            10: "Add AgentState Pydantic schema",
            11: "Add ReviewComment Pydantic schema",
            12: "Add MCP Pydantic schemas",
            13: "Add unit tests for Pydantic schemas",
            14: "Add SQLite volume and db connection",
            15: "Update README with setup instructions",
        }
        return common_titles.get(issue_number, f"Issue #{issue_number}")

    def _generate_agent_state_code(self) -> str:
        return '''from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class ReviewComment(BaseModel):
    file_path: str
    line_number: int
    severity: Literal["critical", "warning", "suggestion"]
    category: Literal["security", "performance", "quality", "debt", "tests"]
    comment: str = Field(min_length=20, max_length=500)
    suggested_fix: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class EnrichedDiff(BaseModel):
    file_path: str
    language: str
    diff_content: str
    num_additions: int
    num_deletions: int
    chunks: list[str] = Field(default_factory=list)


class AgentState(BaseModel):
    pr_id: int
    pr_title: str
    repository: str
    current_file: Optional[str] = None
    enriched_diffs: list[EnrichedDiff] = Field(default_factory=list)
    review_comments: list[ReviewComment] = Field(default_factory=list)
    agent_name: Optional[str] = None
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "pr_id": 123,
                "pr_title": "feat: add user authentication",
                "repository": "owner/repo",
                "status": "processing"
            }
        }
'''

    def _generate_agent_state_tests(self) -> str:
        return '''import pytest
from src.models.agent_state import AgentState, ReviewComment, EnrichedDiff


class TestAgentState:
    def test_agent_state_creation(self):
        state = AgentState(
            pr_id=123,
            pr_title="Test PR",
            repository="test/repo"
        )
        assert state.pr_id == 123
        assert state.status == "pending"
        assert len(state.review_comments) == 0

    def test_agent_state_with_comments(self):
        comment = ReviewComment(
            file_path="src/main.py",
            line_number=10,
            severity="warning",
            category="quality",
            comment="This function is too long, consider splitting it.",
            confidence=0.85
        )
        state = AgentState(
            pr_id=123,
            pr_title="Test PR",
            repository="test/repo",
            review_comments=[comment]
        )
        assert len(state.review_comments) == 1
        assert state.review_comments[0].severity == "warning"

    def test_review_comment_validation(self):
        with pytest.raises(Exception):
            ReviewComment(
                file_path="test.py",
                line_number=1,
                severity="warning",
                category="quality",
                comment="Too short",  # min_length=20
                confidence=0.5
            )


class TestEnrichedDiff:
    def test_enriched_diff_creation(self):
        diff = EnrichedDiff(
            file_path="src/main.py",
            language="python",
            diff_content="+def new_func():\\n    pass",
            num_additions=2,
            num_deletions=0
        )
        assert diff.language == "python"
        assert diff.num_additions == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''

    async def _handle_check_status(self, user_input: str) -> MasterResponse:
        result = await self.devops.execute({"action": "verify_state"})
        report = self.devops.generate_status_report()
        
        return MasterResponse(
            intent=Intent.CHECK_STATUS,
            message=report,
            agent_results=[result]
        )

    async def _handle_create_branch(self, user_input: str) -> MasterResponse:
        issue_number = self.extract_issue_number(user_input)
        title = self._guess_issue_title(user_input, issue_number) if issue_number else "new-feature"
        
        result = await self.devops.execute({
            "action": "prepare_branch",
            "issue_number": issue_number,
            "issue_title": title
        })
        
        return MasterResponse(
            intent=Intent.CREATE_BRANCH,
            message=f"Branch creado: {result.data.get('branch', 'unknown') if result.data else 'unknown'}",
            agent_results=[result]
        )

    async def _handle_commit(self, user_input: str) -> MasterResponse:
        result = await self.devops.execute({"action": "commit", "auto": False})
        
        if result.success:
            questions = [{
                "id": "push_after_commit",
                "text": "Commit realizado",
                "options": [
                    {"value": "push", "label": "Sí, hacer push"},
                    {"value": "no", "label": "No hacer push"}
                ]
            }]
        else:
            questions = []
        
        return MasterResponse(
            intent=Intent.COMMIT_CHANGES,
            message=result.message,
            agent_results=[result],
            questions=questions
        )

    async def _handle_merge(self, user_input: str) -> MasterResponse:
        result = await self.devops.execute({
            "action": "merge",
            "create_pr": True,
            "squash": True
        })
        
        if result.success:
            self.context.workflow_step = "completed"
            questions = [{
                "id": "cleanup",
                "text": "Merge completado",
                "options": [
                    {"value": "cleanup", "label": "Volver a main y limpiar"},
                    {"value": "keep", "label": "Mantener en branch actual"}
                ]
            }]
        else:
            questions = []
        
        return MasterResponse(
            intent=Intent.MERGE_BRANCH,
            message=result.message,
            agent_results=[result],
            questions=questions
        )

    async def _handle_run_tests(self, user_input: str) -> MasterResponse:
        result = await self.devops.execute({
            "action": "run_tests",
            "command": "pytest -v"
        })
        
        return MasterResponse(
            intent=Intent.RUN_TESTS,
            message=f"Tests: {'✓ PASSED' if result.success else '✗ FAILED'}",
            agent_results=[result]
        )

    async def _handle_help(self, user_input: str) -> MasterResponse:
        help_text = '''
╔══════════════════════════════════════════════════════════╗
║                    COMANDOS DEL MASTER                     ║
╠══════════════════════════════════════════════════════════╣
║                                                           ║
║  "Execute #10"      → Ejecutar issue #10                 ║
║  "Status"           → Ver estado de git                   ║
║  "Branch #15"       → Crear branch para issue #15         ║
║  "Commit"           → Commitear cambios                   ║
║  "Merge"            → Hacer merge a main                  ║
║  "Tests"            → Ejecutar tests                      ║
║  "Help"             → Mostrar esta ayuda                   ║
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
            "execute #<numero> - Ejecutar un issue",
            "status - Ver estado de git",
            "branch #<numero> - Crear branch",
            "commit - Commitear cambios",
            "merge - Merge a main",
            "tests - Ejecutar tests",
            "help - Ver comandos"
        ]
