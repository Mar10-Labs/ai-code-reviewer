import re
from dataclasses import dataclass


@dataclass
class PatternMatch:
    file_path: str
    line_number: int
    pattern_name: str
    severity: str
    match: str


class DeterministicValidator:
    PATTERNS = {
        "sql_injection": {
            "regex": r"(execute|query|cursor\.execute)\s*\(\s*['\"].*%s|['\"].*%.*['\"]",
            "severity": "critical"
        },
        "hardcoded_secret": {
            "regex": r"(password|api_key|secret|token)\s*=\s*['\"][^'\"]{4,}['\"]",
            "severity": "critical"
        },
        "inner_html": {
            "regex": r"innerHTML\s*=|dangerouslySetInnerHTML\s*=",
            "severity": "warning"
        },
        "exec_usage": {
            "regex": r"(eval|exec)\s*\(",
            "severity": "critical"
        },
        "todo_fixme": {
            "regex": r"(TODO|FIXME|HACK|XXX):",
            "severity": "info"
        }
    }

    @classmethod
    def validate_diff(cls, diff_content: str) -> list[PatternMatch]:
        matches = []
        current_file = "unknown"

        for line_num, line in enumerate(diff_content.split("\n"), 1):
            if line.startswith("+++"):
                current_file = line[4:].strip().replace("b/", "")
                continue
            if not line.startswith("+") or line.startswith("++"):
                continue

            for pattern_name, pattern_info in cls.PATTERNS.items():
                if re.search(pattern_info["regex"], line, re.IGNORECASE):
                    matches.append(PatternMatch(
                        file_path=current_file,
                        line_number=line_num,
                        pattern_name=pattern_name,
                        severity=pattern_info["severity"],
                        match=line.strip()[:100]
                    ))

        return matches


def validate_deterministic(diff_content: str) -> list[PatternMatch]:
    return DeterministicValidator.validate_diff(diff_content)
