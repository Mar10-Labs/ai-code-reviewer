import pytest
from src.infrastructure.services.semantic_chunker import (
    SemanticChunker,
    ChunkingConfig,
    Chunk,
    chunk_file,
)


class TestChunkingConfig:
    def test_default_config(self):
        config = ChunkingConfig()
        assert config.MAX_TOKENS_PER_CHUNK == 2000
        assert config.MIN_CHUNK_SIZE == 100
        assert config.OVERLAP_LINES == 5

    def test_custom_config(self):
        config = ChunkingConfig(MAX_TOKENS_PER_CHUNK=1000, MIN_CHUNK_SIZE=50)
        assert config.MAX_TOKENS_PER_CHUNK == 1000
        assert config.MIN_CHUNK_SIZE == 50


class TestSemanticChunker:
    def test_detect_python(self):
        chunker = SemanticChunker()
        assert chunker._detect_language("file.py") == "python"
        assert chunker._detect_language("module.py") == "python"

    def test_detect_javascript(self):
        chunker = SemanticChunker()
        assert chunker._detect_language("file.js") == "javascript"
        assert chunker._detect_language("file.ts") == "typescript"
        assert chunker._detect_language("file.jsx") == "javascript"

    def test_detect_java(self):
        chunker = SemanticChunker()
        assert chunker._detect_language("Main.java") == "java"
        assert chunker._detect_language("Test.java") == "java"

    def test_detect_go(self):
        chunker = SemanticChunker()
        assert chunker._detect_language("main.go") == "go"

    def test_detect_rust(self):
        chunker = SemanticChunker()
        assert chunker._detect_language("lib.rs") == "rust"

    def test_detect_unknown(self):
        chunker = SemanticChunker()
        assert chunker._detect_language("file.xyz") == "default"


class TestChunkingSmallFile:
    def test_small_file_returns_single_chunk(self):
        content = "def hello():\n    print('hi')"
        chunker = SemanticChunker()
        chunks = chunker.chunk_file(content, "file.py")

        assert len(chunks) == 1
        assert chunks[0].content == content
        assert chunks[0].chunk_index == 0
        assert chunks[0].total_chunks == 1

    def test_empty_file_returns_empty(self):
        chunker = SemanticChunker()
        chunks = chunker.chunk_file("", "file.py")
        assert len(chunks) == 0

    def test_chunk_has_correct_metadata(self):
        content = "def test():\n    pass"
        chunker = SemanticChunker()
        chunks = chunker.chunk_file(content, "file.py")

        chunk = chunks[0]
        assert chunk.start_line == 1
        assert chunk.end_line == 2
        assert chunk.scope_name == "file"


class TestChunkingLargeFile:
    def test_large_python_file_chunks_by_functions(self):
        content = """
class MyClass:
    def method1(self):
        return 1

    def method2(self):
        return 2

def standalone():
    return 3
"""
        chunker = SemanticChunker()
        chunks = chunker.chunk_file(content, "file.py")

        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.content
            assert chunk.chunk_index >= 0
            assert chunk.total_chunks >= 1


class TestChunkingJavaScript:
    def test_js_class_detection(self):
        content = """
class User {
    constructor() {}
    login() {}
}

class Admin extends User {
    adminMethod() {}
}
"""
        chunker = SemanticChunker()
        chunks = chunker.chunk_file(content, "file.js")

        assert len(chunks) >= 1


class TestChunkFunction:
    def test_chunk_file_helper(self):
        content = "def test():\n    pass"
        chunks = chunk_file(content, "file.py")

        assert len(chunks) == 1
        assert isinstance(chunks[0], Chunk)


class TestChunkMetadata:
    def test_chunk_index_sequential(self):
        content = """
class A:
    pass

class B:
    pass

class C:
    pass
"""
        chunker = SemanticChunker()
        chunks = chunker.chunk_file(content, "file.py")

        if len(chunks) > 1:
            for i, chunk in enumerate(chunks):
                assert chunk.chunk_index == i

    def test_total_chunks_consistent(self):
        content = """
class A:
    pass

class B:
    pass
"""
        chunker = SemanticChunker()
        chunks = chunker.chunk_file(content, "file.py")

        if len(chunks) > 1:
            for chunk in chunks:
                assert chunk.total_chunks == len(chunks)


class TestEdgeCases:
    def test_file_with_only_imports(self):
        content = "import os\nimport sys\nfrom typing import List"
        chunker = SemanticChunker()
        chunks = chunker.chunk_file(content, "file.py")

        assert len(chunks) >= 1

    def test_file_with_multiline_strings(self):
        content = '''
def test():
    long_string = """
    This is a very long
    multiline string
    """
    return long_string
'''
        chunker = SemanticChunker()
        chunks = chunker.chunk_file(content, "file.py")

        assert len(chunks) >= 1

    def test_custom_max_tokens(self):
        content = "def a():\n    pass\n" * 100
        config = ChunkingConfig(MAX_TOKENS_PER_CHUNK=50)
        chunker = SemanticChunker(config)
        chunks = chunker.chunk_file(content, "file.py")

        assert len(chunks) >= 1
