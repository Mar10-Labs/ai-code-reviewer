from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class FileChange(BaseModel):
    date: datetime
    message: str
    author: str
    lines_changed: int


class FileContext(BaseModel):
    file_path: str
    language: str
    current_content: Optional[str] = None
    imports: list[str] = Field(default_factory=list)
    imported_by: list[str] = Field(default_factory=list)
    public_api: list[str] = Field(default_factory=list)
    change_history: list[FileChange] = Field(default_factory=list)
    is_interface_file: bool = False
    is_critical: bool = False


class EnrichedFileContext(BaseModel):
    file_context: FileContext
    related_files: list[FileContext] = Field(default_factory=list)
    dependency_impact: list[str] = Field(default_factory=list)
    breaking_change_detected: bool = False
    analysis_notes: list[str] = Field(default_factory=list)


CRITICAL_KEYWORDS = ["auth", "login", "password", "token", "api_key", "secret", "payment", "security", "permission"]
INTERFACE_FILES = ["__init__.py", "index.ts", "index.js", "types.ts", "interfaces.ts", "models.py", "schemas.py"]


def detect_language(file_path: str) -> str:
    ext = file_path.split(".")[-1].lower()
    return {"py": "python", "js": "javascript", "ts": "typescript", "tsx": "typescript", "jsx": "javascript"}.get(ext, "unknown")


def parse_python_imports(content: str) -> list[str]:
    imports = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("import "):
            module = line.split()[1].split(".")[0]
            if module not in imports:
                imports.append(module)
        elif line.startswith("from "):
            parts = line.split()
            if len(parts) >= 2:
                module = parts[1].split(".")[0]
                if module not in imports:
                    imports.append(module)
    return imports


def parse_python_public_api(content: str) -> list[str]:
    public_api = []
    lines = content.split("\n")
    
    for line in lines:
        line = line.strip()
        clean = line.lstrip("+").lstrip("-")
        
        if clean.startswith("def ") and not clean.startswith("def _"):
            name = clean[4:].split("(")[0].strip()
            if name:
                public_api.append(name)
        
        elif clean.startswith("class ") and not clean.startswith("class _"):
            name = clean[6:].split("(")[0].split(":")[0].strip()
            if name:
                public_api.append(name)
        
        elif clean.startswith("__all__") and "=" in clean:
            all_content = clean.split("=", 1)[1].strip()
            if all_content.startswith("["):
                names = all_content.strip("[]").replace("'", "").replace('"', "").split(",")
                for name in names:
                    name = name.strip()
                    if name:
                        public_api.append(name)
    
    return list(set(public_api))


def detect_interface_file(file_path: str, content: str) -> bool:
    for iface in INTERFACE_FILES:
        if file_path.endswith(iface):
            return True
    return "__all__" in content


def detect_critical_file(file_path: str, content: str) -> bool:
    combined = (file_path + " " + content).lower()
    return any(keyword in combined for keyword in CRITICAL_KEYWORDS)


def detect_breaking_changes(diff_content: str, is_interface: bool) -> bool:
    lines = diff_content.split("\n")
    
    has_standalone_removals = False
    for i, line in enumerate(lines):
        if line.startswith("-") and not line.startswith("--"):
            clean = line[1:].strip()
            if clean.startswith(("def ", "class ", "async def ")):
                if i + 1 >= len(lines) or not lines[i + 1].startswith("+"):
                    has_standalone_removals = True
                    break
    
    if has_standalone_removals:
        return True
    
    if is_interface:
        deletions = sum(1 for line in lines if line.startswith("-") and not line.startswith("--"))
        additions = sum(1 for line in lines if line.startswith("+") and not line.startswith("++"))
        if deletions > additions * 2:
            return True
    
    return False


def build_file_context(file_path: str, diff_content: str, language: str = "python") -> FileContext:
    content = diff_content
    
    if language == "python":
        imports = parse_python_imports(content)
        public_api = parse_python_public_api(content)
    else:
        imports = []
        public_api = []
    
    return FileContext(
        file_path=file_path,
        language=language,
        current_content=content,
        imports=imports,
        public_api=public_api,
        is_interface_file=detect_interface_file(file_path, content),
        is_critical=detect_critical_file(file_path, content),
    )


def build_enriched_context(
    file_path: str,
    diff_content: str,
    language: Optional[str] = None,
    related_files: Optional[list[str]] = None,
) -> EnrichedFileContext:
    if language is None:
        language = detect_language(file_path)
    
    file_context = build_file_context(file_path, diff_content, language)
    
    related_contexts = []
    if related_files:
        for rel_file in related_files:
            related_contexts.append(FileContext(
                file_path=rel_file,
                language=detect_language(rel_file),
                imported_by=[file_path],
            ))
    
    breaking = detect_breaking_changes(diff_content, file_context.is_interface_file)
    
    notes = []
    if file_context.is_interface_file:
        notes.append("Archivo de interfaz - cambios pueden afectar importers")
    if file_context.is_critical:
        notes.append("Archivo crítico - requiere revisión exhaustiva")
    if file_context.public_api:
        notes.append(f"API pública: {', '.join(file_context.public_api[:5])}")
    
    return EnrichedFileContext(
        file_context=file_context,
        related_files=related_contexts,
        dependency_impact=related_files or [],
        breaking_change_detected=breaking,
        analysis_notes=notes,
    )


def enrich_diff_context(
    file_path: str,
    diff_content: str,
    language: Optional[str] = None,
    related_files: Optional[list[str]] = None,
) -> EnrichedFileContext:
    return build_enriched_context(file_path, diff_content, language, related_files)
