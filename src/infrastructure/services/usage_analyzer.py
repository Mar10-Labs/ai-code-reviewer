from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UsageReference:
    file_path: str
    line_number: int
    context: str
    usage_type: str  # call, import, reference, subclass


@dataclass
class UsageAnalysis:
    symbol_name: str
    total_usages: int
    references: list[UsageReference]
    is_exported: bool
    is_critical: bool
    can_be_removed: bool
    suggestion: str


@dataclass
class DeletedSymbol:
    name: str
    symbol_type: str  # function, class, method
    file_path: str
    line_number: int


@dataclass
class ImpactAnalysis:
    deleted_symbols: list[DeletedSymbol]
    usage_analysis: dict[str, UsageAnalysis]
    safe_to_remove: list[str]
    unsafe_to_remove: list[str]
    affected_files: list[str]
    impact_score: float  # 0-1, higher = more impact
    recommendations: list[str]


class UsageAnalyzer:
    def __init__(self, get_file_content_func=None):
        self.get_file_content = get_file_content_func or (lambda x: "")

    def find_usages_in_content(
        self,
        content: str,
        symbol_name: str,
        file_path: str
    ) -> list[UsageReference]:
        references = []
        lines = content.split("\n")
        
        for i, line in enumerate(lines, 1):
            line_clean = line.strip()
            
            if f"{symbol_name}(" in line and not line_clean.startswith("#"):
                references.append(UsageReference(
                    file_path=file_path,
                    line_number=i,
                    context=line_clean[:100],
                    usage_type="call"
                ))
            
            elif f"from " in line and symbol_name in line and "import" in line:
                references.append(UsageReference(
                    file_path=file_path,
                    line_number=i,
                    context=line_clean[:100],
                    usage_type="import"
                ))
            
            elif symbol_name in line and not line_clean.startswith("#"):
                if "=" in line or "return" in line:
                    references.append(UsageReference(
                        file_path=file_path,
                        line_number=i,
                        context=line_clean[:100],
                        usage_type="reference"
                    ))
        
        return references

    def analyze_deleted_symbol(
        self,
        symbol: DeletedSymbol,
        all_files: list[str],
        get_content_func=None
    ) -> UsageAnalysis:
        if get_content_func is None:
            get_content_func = self.get_file_content
        
        all_references = []
        for file_path in all_files:
            if file_path == symbol.file_path:
                continue
            
            content = get_content_func(file_path)
            if content:
                refs = self.find_usages_in_content(content, symbol.name, file_path)
                all_references.extend(refs)
        
        can_remove = len(all_references) == 0
        suggestion = ""
        
        if can_remove:
            suggestion = f"Símbolo '{symbol.name}' no se usa en otros archivos. Seguro eliminar."
        else:
            file_list = ", ".join(set(r.file_path for r in all_references))
            suggestion = f"Símbolo '{symbol.name}' se usa en: {file_list}. No eliminar sin actualizar esos archivos."
        
        return UsageAnalysis(
            symbol_name=symbol.name,
            total_usages=len(all_references),
            references=all_references,
            is_exported=symbol.symbol_type == "class",
            is_critical=self._is_critical_symbol(symbol),
            can_be_removed=can_remove,
            suggestion=suggestion
        )

    def _is_critical_symbol(self, symbol: DeletedSymbol) -> bool:
        critical_prefixes = [
            "auth", "login", "logout", "verify",
            "payment", "charge", "refund",
            "admin", "root", "sudo",
            "encrypt", "decrypt", "hash",
        ]
        name_lower = symbol.name.lower()
        return any(prefix in name_lower for prefix in critical_prefixes)

    def parse_deleted_symbols_from_diff(self, diff_content: str) -> list[DeletedSymbol]:
        deleted = []
        lines = diff_content.split("\n")
        
        current_file = ""
        for i, line in enumerate(lines):
            if line.startswith("--- a/"):
                current_file = line[4:]
            elif line.startswith("-def ") or line.startswith("-async def "):
                name = line.split("(")[0].replace("-def ", "").replace("-async def ", "").strip()
                if name and not name.startswith("_"):
                    deleted.append(DeletedSymbol(
                        name=name,
                        symbol_type="function",
                        file_path=current_file,
                        line_number=i + 1
                    ))
            elif line.startswith("-class "):
                name = line.split("(")[0].replace("-class ", "").strip()
                if name and not name.startswith("_"):
                    deleted.append(DeletedSymbol(
                        name=name,
                        symbol_type="class",
                        file_path=current_file,
                        line_number=i + 1
                    ))
        
        return deleted

    def analyze_impact(
        self,
        diff_content: str,
        all_files: list[str],
        get_content_func=None
    ) -> ImpactAnalysis:
        deleted_symbols = self.parse_deleted_symbols_from_diff(diff_content)
        
        usage_map = {}
        safe_list = []
        unsafe_list = []
        all_affected = set()
        
        for symbol in deleted_symbols:
            analysis = self.analyze_deleted_symbol(symbol, all_files, get_content_func)
            usage_map[symbol.name] = analysis
            
            if analysis.can_be_removed:
                safe_list.append(symbol.name)
            else:
                unsafe_list.append(symbol.name)
                for ref in analysis.references:
                    all_affected.add(ref.file_path)
        
        impact_score = self._calculate_impact_score(
            len(deleted_symbols),
            len(unsafe_list),
            len(all_affected)
        )
        
        recommendations = self._generate_recommendations(
            safe_list, unsafe_list, all_affected, impact_score
        )
        
        return ImpactAnalysis(
            deleted_symbols=deleted_symbols,
            usage_analysis=usage_map,
            safe_to_remove=safe_list,
            unsafe_to_remove=unsafe_list,
            affected_files=list(all_affected),
            impact_score=impact_score,
            recommendations=recommendations
        )

    def _calculate_impact_score(
        self,
        total_deleted: int,
        unsafe_deleted: int,
        affected_files: int
    ) -> float:
        if total_deleted == 0:
            return 0.0
        
        deleted_factor = min(unsafe_deleted / max(total_deleted, 1), 1.0) * 0.5
        impact_factor = min(affected_files / 10, 1.0) * 0.3
        size_factor = min(total_deleted / 20, 1.0) * 0.2
        
        return round(deleted_factor + impact_factor + size_factor, 2)

    def _generate_recommendations(
        self,
        safe: list[str],
        unsafe: list[str],
        affected: set[str],
        impact_score: float
    ) -> list[str]:
        recs = []
        
        if safe:
            recs.append(f"Seguro eliminar: {', '.join(safe)}")
        
        if unsafe:
            recs.append(f"⚠️ No eliminar sin actualizar: {', '.join(unsafe)}")
            recs.append(f"Archivos afectados: {len(affected)}")
        
        if impact_score > 0.7:
            recs.append("🚨 Impacto ALTO - Requiere revisión manual obligatoria")
        elif impact_score > 0.4:
            recs.append("⚠️ Impacto MEDIO - Verificar usages en archivos afectados")
        else:
            recs.append("✅ Impacto BAJO - Cambios seguros")
        
        return recs
