import re
from dataclasses import dataclass, field
from typing import Optional, Callable


@dataclass
class Chunk:
    content: str
    chunk_index: int
    total_chunks: int
    start_line: int
    end_line: int
    scope_name: Optional[str] = None
    parent_scope: Optional[str] = None


@dataclass
class ChunkingConfig:
    MAX_TOKENS_PER_CHUNK: int = 2000
    MIN_CHUNK_SIZE: int = 100
    OVERLAP_LINES: int = 5
    LANGUAGE_PATTERNS: dict = field(default_factory=lambda: {
        "python": {
            "class": r"^class\s+(\w+)",
            "function": r"^(?:async\s+)?def\s+(\w+)",
            "import": r"^(?:from\s+[\w.]+\s+)?import\s+",
        },
        "javascript": {
            "class": r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)",
            "function": r"^(?:export\s+)?(?:async\s+)?(?:function\s+)?(\w+)\s*\(",
            "import": r"^import\s+",
        },
        "typescript": {
            "class": r"^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)",
            "function": r"^(?:export\s+)?(?:async\s+)?(?:function\s+)?(\w+)\s*\(",
            "import": r"^import\s+",
        },
        "java": {
            "class": r"^(?:public|private|protected)?\s*(?:abstract|final)?\s*class\s+(\w+)",
            "function": r"^\s*(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(",
            "import": r"^import\s+",
        },
        "go": {
            "function": r"^func\s+(?:\([^)]+\)\s+)?(\w+)",
            "import": r"^import\s+",
        },
        "rust": {
            "function": r"^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)",
            "struct": r"^(?:pub\s+)?struct\s+(\w+)",
            "import": r"^use\s+",
        },
        "default": {
            "class": r"^(?:class|interface|struct)\s+(\w+)",
            "function": r"^(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(",
        }
    })


class SemanticChunker:
    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()

    def chunk_file(
        self,
        content: str,
        file_path: str = "file.py",
        language: str = None
    ) -> list[Chunk]:
        if not content.strip():
            return []

        language = language or self._detect_language(file_path)
        lines = content.split("\n")

        tokens = self._estimate_tokens(content)
        if tokens <= self.config.MAX_TOKENS_PER_CHUNK:
            return [Chunk(
                content=content,
                chunk_index=0,
                total_chunks=1,
                start_line=1,
                end_line=len(lines),
                scope_name="file"
            )]

        semantic_chunks = self._split_by_semantics(lines, language)

        if not semantic_chunks:
            return self._split_by_lines(content, lines)

        return self._merge_chunks(semantic_chunks, lines, language)

    def _detect_language(self, file_path: str) -> str:
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
        }

        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return "default"

    def _estimate_tokens(self, content: str) -> int:
        return len(content) // 4

    def _split_by_semantics(self, lines: list[str], language: str) -> list[dict]:
        patterns = self.config.LANGUAGE_PATTERNS.get(language, self.config.LANGUAGE_PATTERNS["default"])
        chunks = []
        current_scope = "file"
        scope_stack = ["file"]
        chunk_start = 0
        current_lines = []

        for i, line in enumerate(lines):
            indent = len(line) - len(line.lstrip())

            for scope_type, pattern in patterns.items():
                if scope_type == "import":
                    continue

                match = re.match(pattern, line.strip())
                if match:
                    name = match.group(1) if match.groups() else scope_type
                    new_scope = f"{scope_type}:{name}"

                    if scope_type == "class" or scope_type == "struct":
                        scope_stack = [new_scope]
                    elif indent > 0 and scope_stack:
                        scope_stack[-1] = new_scope
                    else:
                        scope_stack = [new_scope]

                    if current_lines:
                        chunks.append({
                            "start": chunk_start,
                            "end": i - 1,
                            "scope": ".".join(scope_stack[:-1]) or current_scope,
                            "lines": current_lines
                        })

                    current_scope = new_scope
                    chunk_start = i
                    current_lines = [line]
                    break
            else:
                current_lines.append(line)

                tokens = self._estimate_tokens("\n".join(current_lines))
                if tokens > self.config.MAX_TOKENS_PER_CHUNK * 1.5:
                    chunks.append({
                        "start": chunk_start,
                        "end": i,
                        "scope": current_scope,
                        "lines": current_lines[:-1]
                    })
                    current_lines = [line]
                    chunk_start = i

        if current_lines:
            chunks.append({
                "start": chunk_start,
                "end": len(lines) - 1,
                "scope": current_scope,
                "lines": current_lines
            })

        return chunks

    def _split_by_lines(self, content: str, lines: list[str]) -> list[Chunk]:
        chunks = []
        total_tokens = self._estimate_tokens(content)
        chunk_size = self.config.MAX_TOKENS_PER_CHUNK * 4
        overlap = self.config.OVERLAP_LINES

        for i in range(0, len(lines), chunk_size - overlap):
            end = min(i + chunk_size, len(lines))
            chunk_lines = lines[i:end]
            chunk_content = "\n".join(chunk_lines)

            chunks.append(Chunk(
                content=chunk_content,
                chunk_index=len(chunks),
                total_chunks=0,
                start_line=i + 1,
                end_line=end,
                scope_name="lines"
            ))

        for i, chunk in enumerate(chunks):
            chunk.total_chunks = len(chunks)

        return chunks

    def _merge_chunks(
        self,
        semantic_chunks: list[dict],
        all_lines: list[str],
        language: str
    ) -> list[Chunk]:
        if not semantic_chunks:
            return self._split_by_lines("\n".join(all_lines), all_lines)

        result = []
        current_buffer = []
        current_scope = "file"
        buffer_start = 0

        for chunk_data in semantic_chunks:
            chunk_lines = chunk_data["lines"]
            chunk_content = "\n".join(chunk_lines)
            chunk_tokens = self._estimate_tokens(chunk_content)

            if chunk_tokens <= self.config.MAX_TOKENS_PER_CHUNK:
                current_buffer.extend(chunk_lines)
                current_scope = chunk_data["scope"]
            else:
                if current_buffer:
                    result.append(Chunk(
                        content="\n".join(current_buffer),
                        chunk_index=len(result),
                        total_chunks=0,
                        start_line=buffer_start + 1,
                        end_line=buffer_start + len(current_buffer),
                        scope_name=current_scope
                    ))
                    current_buffer = []
                    buffer_start = chunk_data["start"]

                sub_chunks = self._split_large_chunk(
                    chunk_lines,
                    chunk_data["start"],
                    chunk_data["scope"]
                )
                result.extend(sub_chunks)

        if current_buffer:
            result.append(Chunk(
                content="\n".join(current_buffer),
                chunk_index=len(result),
                total_chunks=0,
                start_line=buffer_start + 1,
                end_line=buffer_start + len(current_buffer),
                scope_name=current_scope
            ))

        for i, chunk in enumerate(result):
            chunk.total_chunks = len(result)
            chunk.chunk_index = i

        return result

    def _split_large_chunk(
        self,
        lines: list[str],
        start_offset: int,
        scope: str
    ) -> list[Chunk]:
        chunks = []
        chunk_size = self.config.MAX_TOKENS_PER_CHUNK * 4

        for i in range(0, len(lines), chunk_size):
            end = min(i + chunk_size, len(lines))
            chunk_lines = lines[i:end]

            chunks.append(Chunk(
                content="\n".join(chunk_lines),
                chunk_index=len(chunks),
                total_chunks=0,
                start_line=start_offset + i + 1,
                end_line=start_offset + end,
                scope_name=scope
            ))

        return chunks


def chunk_file(
    content: str,
    file_path: str = "file.py",
    language: str = None,
    config: ChunkingConfig = None
) -> list[Chunk]:
    chunker = SemanticChunker(config)
    return chunker.chunk_file(content, file_path, language)
