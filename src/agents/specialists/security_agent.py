from typing import Optional
from dataclasses import dataclass

from src.agents.base_agent import BaseAgent, AgentConfig, AgentType, AgentCapability


@dataclass
class ReviewResult:
    file_path: str
    line_number: int
    severity: str
    category: str
    comment: str
    suggested_fix: Optional[str] = None


class SecurityAgent(BaseAgent):
    def __init__(self):
        config = AgentConfig(
            name="Security",
            agent_type=AgentType.SPECIALIST,
            description="Analyzes security: SQL injection, XSS, secrets, auth issues",
            capabilities=[AgentCapability.CODE_ANALYSIS, AgentCapability.SECURITY_SCAN]
        )
        super().__init__(config)

    async def execute(self, task: dict) -> dict:
        diff_content = task.get("diff_content", "")
        file_path = task.get("file_path", "")
        
        results = []
        
        results.extend(self._check_sql_injection(diff_content, file_path))
        results.extend(self._check_xss(diff_content, file_path))
        results.extend(self._check_secrets(diff_content, file_path))
        results.extend(self._check_auth(diff_content, file_path))
        
        return {
            "agent": self.config.name,
            "results": results,
            "summary": f"Found {len(results)} security concerns"
        }

    def _check_sql_injection(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        dangerous = [
            ("execute(", "Use parameterized queries"),
            ("cursor.execute", "Use parameterized queries"),
            ("SELECT ", "Validate and sanitize input"),
            ("INSERT ", "Validate and sanitize input"),
        ]
        
        for i, line in enumerate(content.split("\n"), 1):
            lower = line.lower()
            for pattern, fix in dangerous:
                if pattern.lower() in lower and '"%s"' in line or '%(' in line:
                    results.append(ReviewResult(
                        file_path=file_path,
                        line_number=i,
                        severity="critical",
                        category="security",
                        comment=f"Potential SQL injection vulnerability",
                        suggested_fix=fix
                    ))
        
        return results

    def _check_xss(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        
        for i, line in enumerate(content.split("\n"), 1):
            lower = line.lower()
            
            if any(x in lower for x in ["innerhtml", "dangerouslysetinnerhtml", ".html(", "v-html"]):
                results.append(ReviewResult(
                    file_path=file_path,
                    line_number=i,
                    severity="critical",
                    category="security",
                    comment="Potential XSS vulnerability - direct HTML injection detected",
                    suggested_fix="Sanitize input or use textContent instead"
                ))
        
        return results

    def _check_secrets(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        secret_patterns = [
            "password", "secret", "api_key", "apikey", "token",
            "private_key", "aws_access", "bearer"
        ]
        
        for i, line in enumerate(content.split("\n"), 1):
            lower = line.lower()
            if any(p in lower for p in secret_patterns):
                if "=" in line and not line.strip().startswith("#"):
                    results.append(ReviewResult(
                        file_path=file_path,
                        line_number=i,
                        severity="critical",
                        category="security",
                        comment="Possible hardcoded secret detected",
                        suggested_fix="Use environment variables or a secrets manager"
                    ))
        
        return results

    def _check_auth(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        
        for i, line in enumerate(content.split("\n"), 1):
            lower = line.lower()
            
            if "auth" in lower or "permission" in lower or "role" in lower:
                if any(x in lower for x in ["return true", "return 1", "== true"]):
                    results.append(ReviewResult(
                        file_path=file_path,
                        line_number=i,
                        severity="warning",
                        category="security",
                        comment="Authorization check appears to always return true",
                        suggested_fix="Implement proper authorization logic"
                    ))
        
        return results
