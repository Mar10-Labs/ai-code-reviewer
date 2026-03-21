import pytest
from src.infrastructure.services.context_builder import (
    parse_python_imports,
    parse_python_public_api,
    detect_interface_file,
    detect_critical_file,
    detect_breaking_changes,
    build_file_context,
    build_enriched_context,
    enrich_diff_context,
)


class TestParseImports:
    def test_parse_simple_imports(self):
        content = """
import os
import sys
from typing import Optional, List
from datetime import datetime
"""
        imports = parse_python_imports(content)
        
        assert "os" in imports
        assert "sys" in imports
        assert "typing" in imports

    def test_parse_from_import(self):
        content = "from src.models import User"
        imports = parse_python_imports(content)
        
        assert "src" in imports or "models" in imports


class TestParsePublicAPI:
    def test_parse_public_functions(self):
        content = """
def public_function():
    pass

def _private_function():
    pass

class PublicClass:
    pass

class _PrivateClass:
    pass
"""
        public_api = parse_python_public_api(content)
        
        assert "public_function" in public_api
        assert "PublicClass" in public_api
        assert "_private_function" not in public_api
        assert "_PrivateClass" not in public_api

    def test_parse_with_all(self):
        content = '__all__ = ["public_function", "PublicClass"]\ndef internal():\n    pass'
        public_api = parse_python_public_api(content)
        
        assert "public_function" in public_api
        assert "PublicClass" in public_api


class TestDetectFiles:
    def test_interface_file(self):
        assert detect_interface_file("src/__init__.py", "") is True
        assert detect_interface_file("src/models/__init__.py", "") is True
        assert detect_interface_file("src/utils.py", "") is False

    def test_critical_file(self):
        assert detect_critical_file("src/auth.py", "") is True
        assert detect_critical_file("src/security.py", "") is True
        assert detect_critical_file("src/utils.py", "") is False

    def test_critical_content(self):
        assert detect_critical_file("src/utils.py", "api_key = 'secret'") is True


class TestBreakingChanges:
    def test_removal_detection(self):
        diff = """
-def old_function():
-    pass
+def new_function():
+    return True
"""
        assert detect_breaking_changes(diff, False) is True

    def test_interface_massive_change(self):
        diff = """
-import old_module
+import new_module
-def removed1(): pass
-def removed2(): pass
-def removed3(): pass
-def removed4(): pass
-def removed5(): pass
"""
        assert detect_breaking_changes(diff, True) is True

    def test_normal_change(self):
        diff = """
-def old_func():
+def new_func():
     pass
"""
        assert detect_breaking_changes(diff, False) is False


class TestBuildFileContext:
    def test_basic_context(self):
        diff = "+def new_function():\n+    return True"
        context = build_file_context("src/utils.py", diff, "python")
        
        assert context.file_path == "src/utils.py"
        assert context.language == "python"
        assert "new_function" in context.public_api


class TestBuildEnrichedContext:
    def test_full_enrichment(self):
        result = enrich_diff_context(
            file_path="src/models/user.py",
            diff_content="+def create_user():\n+    pass",
            related_files=["src/models/__init__.py"],
        )
        
        assert result.file_context.file_path == "src/models/user.py"
        assert len(result.related_files) == 1
        assert result.breaking_change_detected is False
        assert len(result.analysis_notes) > 0

    def test_critical_file_detection(self):
        result = enrich_diff_context(
            file_path="src/auth.py",
            diff_content="+def login():\n+    pass",
        )
        
        assert result.file_context.is_critical is True
        assert "crítico" in result.analysis_notes[0].lower()
