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


class PerformanceAgent(BaseAgent):
    def __init__(self):
        config = AgentConfig(
            name="Performance",
            agent_type=AgentType.SPECIALIST,
            description="Analyzes performance: algorithms, data structures, resource usage",
            capabilities=[AgentCapability.CODE_ANALYSIS]
        )
        super().__init__(config)

    async def execute(self, task: dict) -> dict:
        diff_content = task.get("diff_content", "")
        file_path = task.get("file_path", "")
        language = task.get("language", "python")
        
        results = []
        
        results.extend(self._check_algorithms(diff_content, file_path))
        results.extend(self._check_loops(diff_content, file_path))
        results.extend(self._check_inefficient_patterns(diff_content, file_path, language))
        
        return {
            "agent": self.config.name,
            "results": results,
            "summary": f"Found {len(results)} performance concerns"
        }

    def _check_algorithms(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        
        inefficient = ["for i in range(len(array))", "while True:", ".sort()"]
        
        for i, line in enumerate(content.split("\n"), 1):
            for pattern in inefficient:
                if pattern in line:
                    results.append(ReviewResult(
                        file_path=file_path,
                        line_number=i,
                        severity="warning",
                        category="performance",
                        comment=f"Inefficient pattern detected: {pattern}",
                        suggested_fix="Consider using more efficient iteration or sorting approach"
                    ))
        
        return results

    def _check_loops(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        lines = content.split("\n")
        
        in_nested_loop = False
        for i, line in enumerate(lines, 1):
            if line.strip().startswith("for ") or line.strip().startswith("while "):
                if in_nested_loop:
                    results.append(ReviewResult(
                        file_path=file_path,
                        line_number=i,
                        severity="suggestion",
                        category="performance",
                        comment="Deeply nested loop detected. Consider optimizing or caching.",
                        suggested_fix="Check if loop iterations can be reduced or results cached"
                    ))
                in_nested_loop = True
            elif not line.strip():
                in_nested_loop = False
        
        return results

    def _check_inefficient_patterns(self, content: str, file_path: str, language: str) -> list[ReviewResult]:
        results = []
        
        patterns = {
            "python": ["+= ''", ".append(", "list("],
            "javascript": ["+ ''", ".push(", "forEach"],
        }
        
        lang_patterns = patterns.get(language, patterns["python"])
        
        for i, line in enumerate(content.split("\n"), 1):
            for pattern in lang_patterns:
                if pattern in line:
                    results.append(ReviewResult(
                        file_path=file_path,
                        line_number=i,
                        severity="suggestion",
                        category="performance",
                        comment=f"Potential inefficiency: consider using list comprehension or join()",
                        suggested_fix=f"Pattern '{pattern}' can be optimized"
                    ))
        
        return results
