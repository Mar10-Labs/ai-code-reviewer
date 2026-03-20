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


class TestingAgent(BaseAgent):
    def __init__(self):
        config = AgentConfig(
            name="Testing",
            agent_type=AgentType.SPECIALIST,
            description="Analyzes tests: coverage, missing tests, edge cases",
            capabilities=[AgentCapability.CODE_ANALYSIS]
        )
        super().__init__(config)

    async def execute(self, task: dict) -> dict:
        diff_content = task.get("diff_content", "")
        file_path = task.get("file_path", "")
        existing_tests = task.get("existing_tests", "")
        
        results = []
        
        results.extend(self._check_test_coverage(diff_content, file_path))
        results.extend(self._check_edge_cases(diff_content, file_path))
        results.extend(self._check_test_quality(diff_content, file_path, existing_tests))
        
        return {
            "agent": self.config.name,
            "results": results,
            "summary": f"Found {len(results)} testing concerns"
        }

    def _check_test_coverage(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        
        if "_test" in file_path or ".test." in file_path or "spec." in file_path:
            return results
        
        functions = []
        for line in content.split("\n"):
            if "def " in line or "function " in line or "const " in line:
                func_name = line.split("(")[0].split()[-1]
                if func_name and not func_name.startswith("_"):
                    functions.append(func_name)
        
        if functions and len(functions) > 2:
            results.append(ReviewResult(
                file_path=file_path,
                line_number=1,
                severity="suggestion",
                category="tests",
                comment=f"Found {len(functions)} new functions without corresponding tests",
                suggested_fix="Add tests for: " + ", ".join(functions[:3])
            ))
        
        return results

    def _check_edge_cases(self, content: str, file_path: str) -> list[ReviewResult]:
        results = []
        
        patterns = {
            "None": "null check",
            "null": "null check", 
            "undefined": "undefined check",
            "[]": "empty array check",
            "{}": "empty object check",
            "0": "zero check",
            "''": "empty string check",
            '""': "empty string check",
        }
        
        for i, line in enumerate(content.split("\n"), 1):
            if any(kw in line for kw in ["if ", "while ", "return "]):
                for pattern, check_type in patterns.items():
                    if pattern in line:
                        if "not " not in line.lower() and "!=" not in line and "!==" not in line:
                            results.append(ReviewResult(
                                file_path=file_path,
                                line_number=i,
                                severity="suggestion",
                                category="tests",
                                comment=f"Consider adding {check_type} edge case test",
                                suggested_fix=f"Test for {pattern} input"
                            ))
        
        return results

    def _check_test_quality(self, content: str, file_path: str, existing_tests: str) -> list[ReviewResult]:
        results = []
        
        if "_test" not in file_path and ".test." not in file_path and "spec." not in file_path:
            return results
        
        has_assertions = any(a in content for a in ["assert", "expect", "should", "it("])
        
        if not has_assertions:
            results.append(ReviewResult(
                file_path=file_path,
                line_number=1,
                severity="warning",
                category="tests",
                comment="Test file appears to have no assertions",
                suggested_fix="Add assertions to verify expected behavior"
            ))
        
        for i, line in enumerate(content.split("\n"), 1):
            if "sleep(" in line.lower():
                results.append(ReviewResult(
                    file_path=file_path,
                    line_number=i,
                    severity="warning",
                    category="tests",
                    comment="Avoid using sleep in tests - use proper wait conditions",
                    suggested_fix="Use waitFor or explicit waits instead of sleep"
                ))
        
        return results
