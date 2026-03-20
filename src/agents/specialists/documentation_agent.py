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


class DocumentationAgent(BaseAgent):
    def __init__(self):
        config = AgentConfig(
            name="Documentation",
            agent_type=AgentType.SPECIALIST,
            description="Analyzes documentation: docstrings, comments, README",
            capabilities=[AgentCapability.CODE_ANALYSIS]
        )
        super().__init__(config)

    async def execute(self, task: dict) -> dict:
        diff_content = task.get("diff_content", "")
        file_path = task.get("file_path", "")
        language = task.get("language", "python")
        
        results = []
        
        results.extend(self._check_docstrings(diff_content, file_path, language))
        results.extend(self._check_comments(diff_content, file_path))
        results.extend(self._check_todo_fixme(diff_content, file_path))
        
        return {
            "agent": self.config.name,
            "results": results,
            "summary": f"Found {len(results)} documentation concerns"
        }

    def _check_docstrings(self, content: str, file_path: str, language: str) -> list[ReviewResult]:
        results = []
        
        docstring_patterns = {
            "python": ['"""', "'''", 'def ', "class "],
            "javascript": ["/**", "function ", "const ", "class "],
            "typescript": ["/**", "function ", "const ", "interface "],
        }
        
        patterns = docstring_patterns.get(language, docstring_patterns["python"])
        lines = content.split("\n")
        
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                if line.strip().startswith(pattern) and not line.strip().endswith(":"):
                    continue
                    
                if line.strip().startswith(pattern) and i > 0:
                    prev_line = lines[i-2] if i > 1 else ""
                    if '"""' not in prev_line and "'''" not in prev_line and "/**" not in prev_line:
                        results.append(ReviewResult(
                            file_path=file_path,
                            line_number=i,
                            severity="suggestion",
                            category="docs",
                            comment="Missing docstring for function/class",
                            suggested_fix="Add a docstring describing the purpose and parameters"
                        ))
        
        return results

    def _check_comments(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        
        lines = content.split("\n")
        code_lines = [l for l in lines if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("//")]
        
        comment_count = len([l for l in lines if l.strip().startswith("#") or l.strip().startswith("//")])
        
        if code_lines and comment_count == 0:
            results.append(ReviewResult(
                file_path=file_path,
                line_number=1,
                severity="suggestion",
                category="docs",
                comment="No inline comments found. Consider adding explanatory comments for complex logic.",
                suggested_fix="Add comments for non-obvious code sections"
            ))
        
        return results

    def _check_todo_fixme(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        
        for i, line in enumerate(content.split("\n"), 1):
            lower = line.lower()
            if "todo" in lower or "fixme" in lower or "hack" in lower:
                results.append(ReviewResult(
                    file_path=file_path,
                    line_number=i,
                    severity="suggestion",
                    category="docs",
                    comment=f"Unresolved TODO/FIXME/HACK found: {line.strip()[:50]}",
                    suggested_fix="Address this item or create a tracking issue"
                ))
        
        return results
