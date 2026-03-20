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


class CodeQualityAgent(BaseAgent):
    def __init__(self):
        config = AgentConfig(
            name="CodeQuality",
            agent_type=AgentType.SPECIALIST,
            description="Analyzes code quality: naming conventions, duplication, complexity",
            capabilities=[AgentCapability.CODE_ANALYSIS]
        )
        super().__init__(config)

    async def execute(self, task: dict) -> dict:
        diff_content = task.get("diff_content", "")
        file_path = task.get("file_path", "")
        
        results = []
        
        results.extend(self._check_naming(diff_content, file_path))
        results.extend(self._check_complexity(diff_content, file_path))
        results.extend(self._check_duplication(diff_content, file_path))
        
        return {
            "agent": self.config.name,
            "results": results,
            "summary": f"Found {len(results)} quality issues"
        }

    def _check_naming(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        
        for i, line in enumerate(content.split("\n"), 1):
            if "_" in line and any(c.isupper() for c in line):
                results.append(ReviewResult(
                    file_path=file_path,
                    line_number=i,
                    severity="suggestion",
                    category="quality",
                    comment="Mixed naming convention detected. Consider using consistent snake_case or camelCase.",
                    suggested_fix="Use consistent naming: snake_case for Python, camelCase for JS"
                ))
        
        return results

    def _check_complexity(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        lines = content.split("\n")
        
        for i, line in enumerate(lines, 1):
            if line.count("if ") > 3:
                results.append(ReviewResult(
                    file_path=file_path,
                    line_number=i,
                    severity="warning",
                    category="quality",
                    comment="High cyclomatic complexity. Consider extracting to smaller functions.",
                    suggested_fix="Break down into smaller, more focused functions"
                ))
        
        return results

    def _check_duplication(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        
        seen = {}
        for i, line in enumerate(lines, 1):
            if len(line) > 20:
                normalized = line[:50]
                if normalized in seen:
                    results.append(ReviewResult(
                        file_path=file_path,
                        line_number=i,
                        severity="suggestion",
                        category="quality",
                        comment="Possible code duplication. Consider extracting to a function.",
                        suggested_fix=f"Similar code found at line {seen[normalized]}"
                    ))
                else:
                    seen[normalized] = i
        
        return results
