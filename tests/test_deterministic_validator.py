import pytest
from src.infrastructure.services.deterministic_validator import (
    DeterministicValidator,
    validate_deterministic,
    PatternMatch
)


class TestDeterministicValidator:
    def test_detect_sql_injection(self):
        diff = """--- a/db.py
+++ b/db.py
+        cursor.execute("SELECT * FROM users WHERE id=%s" % user_id)"""
        matches = validate_deterministic(diff)
        assert any(m.pattern_name == "sql_injection" for m in matches)

    def test_detect_hardcoded_secret(self):
        diff = """--- a/config.py
+++ b/config.py
+        password = "admin123"
+        api_key = "sk-1234567890abcdef" """
        matches = validate_deterministic(diff)
        assert any(m.pattern_name == "hardcoded_secret" for m in matches)

    def test_detect_inner_html(self):
        diff = """--- a/index.js
+++ b/index.js
+        element.innerHTML = userInput"""
        matches = validate_deterministic(diff)
        assert any(m.pattern_name == "inner_html" for m in matches)

    def test_detect_eval(self):
        diff = """--- a/script.py
+++ b/script.py
+        eval(user_code)"""
        matches = validate_deterministic(diff)
        assert any(m.pattern_name == "exec_usage" for m in matches)

    def test_detect_todo(self):
        diff = """--- a/main.py
+++ b/main.py
+        # TODO: fix this later"""
        matches = validate_deterministic(diff)
        assert any(m.pattern_name == "todo_fixme" for m in matches)

    def test_no_false_positives(self):
        diff = """--- a/main.py
+++ b/main.py
+        def hello():
+            print("Hello world")"""
        matches = validate_deterministic(diff)
        assert len(matches) == 0

    def test_empty_diff(self):
        matches = validate_deterministic("")
        assert len(matches) == 0

    def test_pattern_match_structure(self):
        diff = """--- a/test.py
+++ b/test.py
+        password = "secret123\""""
        matches = validate_deterministic(diff)
        assert len(matches) > 0
        m = matches[0]
        assert isinstance(m, PatternMatch)
        assert m.file_path == "test.py"
        assert m.severity == "critical"
        assert m.match.startswith("+")
