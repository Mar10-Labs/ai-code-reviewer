import pytest
from src.infrastructure.services.usage_analyzer import (
    UsageAnalyzer,
    UsageReference,
    DeletedSymbol,
    ImpactAnalysis,
)


class TestUsageAnalyzer:
    def test_find_usages_call(self):
        analyzer = UsageAnalyzer()
        content = """
def main():
    result = helper_function()
    value = another_helper(data)
"""
        refs = analyzer.find_usages_in_content(content, "helper_function", "test.py")
        
        assert len(refs) >= 1
        assert any(r.usage_type == "call" for r in refs)

    def test_find_usages_excludes_comments(self):
        analyzer = UsageAnalyzer()
        content = """
# TODO: call helper_function here later
def other_function():
    pass
"""
        refs = analyzer.find_usages_in_content(content, "helper_function", "test.py")
        assert len(refs) == 0

    def test_parse_deleted_symbols_function(self):
        analyzer = UsageAnalyzer()
        diff = """
--- a/src/utils.py
-def old_function():
-    pass
+def new_function():
+    return True
"""
        symbols = analyzer.parse_deleted_symbols_from_diff(diff)
        
        assert any(s.name == "old_function" and s.symbol_type == "function" for s in symbols)

    def test_parse_deleted_symbols_class(self):
        analyzer = UsageAnalyzer()
        diff = """--- a/src/models.py
-class OldClass:
-    pass
"""
        symbols = analyzer.parse_deleted_symbols_from_diff(diff)
        
        assert len(symbols) >= 1

    def test_private_symbols_ignored(self):
        analyzer = UsageAnalyzer()
        diff = """
-def _private_function():
-    pass
"""
        symbols = analyzer.parse_deleted_symbols_from_diff(diff)
        assert len(symbols) == 0

    def test_analyze_deleted_symbol_safe(self):
        analyzer = UsageAnalyzer(lambda x: "")
        symbol = DeletedSymbol(
            name="unused_function",
            symbol_type="function",
            file_path="src/utils.py",
            line_number=10
        )
        
        analysis = analyzer.analyze_deleted_symbol(symbol, ["src/other.py"])
        
        assert analysis.can_be_removed is True
        assert analysis.total_usages == 0
        assert "no se usa" in analysis.suggestion.lower()

    def test_analyze_deleted_symbol_unsafe(self):
        analyzer = UsageAnalyzer(lambda x: "result = unused_function(data)")
        symbol = DeletedSymbol(
            name="unused_function",
            symbol_type="function",
            file_path="src/utils.py",
            line_number=10
        )
        
        analysis = analyzer.analyze_deleted_symbol(symbol, ["src/other.py"])
        
        assert analysis.can_be_removed is False
        assert analysis.total_usages >= 1

    def test_critical_symbol_detection(self):
        analyzer = UsageAnalyzer()
        symbol = DeletedSymbol(
            name="verify_auth",
            symbol_type="function",
            file_path="src/auth.py",
            line_number=10
        )
        
        assert analyzer._is_critical_symbol(symbol) is True

    def test_non_critical_symbol(self):
        analyzer = UsageAnalyzer()
        symbol = DeletedSymbol(
            name="helper_utility",
            symbol_type="function",
            file_path="src/utils.py",
            line_number=10
        )
        
        assert analyzer._is_critical_symbol(symbol) is False


class TestImpactAnalysis:
    def test_impact_score_calculation(self):
        analyzer = UsageAnalyzer()
        diff = """
-def func1(): pass
-def func2(): pass
-def func3(): pass
"""
        impact = analyzer.analyze_impact(diff, ["file1.py", "file2.py"])
        
        assert isinstance(impact, ImpactAnalysis)
        assert impact.impact_score >= 0
        assert impact.impact_score <= 1

    def test_safe_removal_in_recommendations(self):
        analyzer = UsageAnalyzer()
        diff = "-def unused(): pass"
        
        impact = analyzer.analyze_impact(diff, [])
        
        assert any("Seguro eliminar" in r for r in impact.recommendations)

    def test_unsafe_removal_in_recommendations(self):
        analyzer = UsageAnalyzer(lambda x: "value = removed_func()")
        diff = "-def removed_func(): pass"
        
        impact = analyzer.analyze_impact(diff, ["src/other.py"])
        
        assert any("No eliminar" in r or "actualizar" in r for r in impact.recommendations)

    def test_high_impact_threshold(self):
        analyzer = UsageAnalyzer()
        
        def mock_content(file_path):
            return "removed_func1()\nremoved_func2()\nremoved_func3()\n"
        
        diff = """
-def removed_func1(): pass
-def removed_func2(): pass
-def removed_func3(): pass
"""
        
        impact = analyzer.analyze_impact(diff, ["file1.py"], mock_content)
        
        assert len(impact.deleted_symbols) == 3
        assert impact.impact_score > 0


class TestUsageReference:
    def test_reference_types(self):
        analyzer = UsageAnalyzer()
        
        content = """
from module import my_function
result = my_function()
value = my_function
"""
        refs = analyzer.find_usages_in_content(content, "my_function", "test.py")
        
        types = [r.usage_type for r in refs]
        assert "import" in types or "call" in types
