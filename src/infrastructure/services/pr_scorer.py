from dataclasses import dataclass, field
from typing import Optional

from src.models.file_context import EnrichedFileContext
from src.infrastructure.services.git_client import GitClient
from src.infrastructure.services.usage_analyzer import (
    UsageAnalyzer,
    ImpactAnalysis,
    DeletedSymbol,
)
from src.infrastructure.services.context_builder import build_enriched_context


@dataclass
class ScoringFactor:
    name: str
    weight: float
    score: float
    details: str


@dataclass
class PRScoring:
    risk_score: float  # 0-1
    complexity: str  # low/medium/high
    requires_human_review: bool
    blocking: bool
    factors: list[ScoringFactor]
    impact_analysis: Optional[ImpactAnalysis]
    affected_files: list[str]
    recommendations: list[str]
    summary: str


class PRScoreCalculator:
    THRESHOLD_BLOCK = 0.75
    THRESHOLD_REVIEW = 0.5
    
    def __init__(self, repo_path: str = "."):
        self.git_client = GitClient(repo_path)
        self.usage_analyzer = UsageAnalyzer()

    def calculate_score(
        self,
        diff_content: str,
        enriched_contexts: list[EnrichedFileContext],
        file_paths: list[str],
        get_file_content_func=None
    ) -> PRScoring:
        factors = []
        
        breaking_score, breaking_details = self._score_breaking_changes(enriched_contexts)
        factors.append(ScoringFactor("breaking_changes", 0.3, breaking_score, breaking_details))
        
        critical_score, critical_details = self._score_critical_files(enriched_contexts)
        factors.append(ScoringFactor("critical_files", 0.25, critical_score, critical_details))
        
        size_score, size_details = self._score_size(diff_content)
        factors.append(ScoringFactor("size", 0.2, size_score, size_details))
        
        impact_analysis = self._analyze_impact(diff_content, file_paths, get_file_content_func)
        impact_score = impact_analysis.impact_score if impact_analysis else 0
        factors.append(ScoringFactor(
            "usage_impact", 0.15, 
            impact_score,
            f"{len(impact_analysis.unsafe_to_remove if impact_analysis else [])} símbolos usados"
        ))
        
        hot_score, hot_details = self._score_hot_files(enriched_contexts)
        factors.append(ScoringFactor("hot_files", 0.1, hot_score, hot_details))
        
        total_score = sum(f.weight * f.score for f in factors)
        
        complexity = self._get_complexity(total_score)
        requires_review = total_score > self.THRESHOLD_REVIEW
        blocking = total_score > self.THRESHOLD_BLOCK
        
        recommendations = self._generate_recommendations(
            total_score, factors, impact_analysis, enriched_contexts
        )
        
        summary = self._generate_summary(total_score, complexity, len(impact_analysis.affected_files if impact_analysis else []))
        
        return PRScoring(
            risk_score=round(total_score, 2),
            complexity=complexity,
            requires_human_review=requires_review,
            blocking=blocking,
            factors=factors,
            impact_analysis=impact_analysis,
            affected_files=impact_analysis.affected_files if impact_analysis else [],
            recommendations=recommendations,
            summary=summary
        )

    def _score_breaking_changes(self, contexts: list[EnrichedFileContext]) -> tuple[float, str]:
        breaking_count = sum(1 for c in contexts if c.breaking_change_detected)
        if not contexts:
            return 0.0, "Sin contexto"
        
        score = min(breaking_count / max(len(contexts), 1), 1.0)
        details = f"{breaking_count} archivos con cambios breaking"
        return score, details

    def _score_critical_files(self, contexts: list[EnrichedFileContext]) -> tuple[float, str]:
        critical_count = sum(1 for c in contexts if c.file_context.is_critical)
        if not contexts:
            return 0.0, "Sin contexto"
        
        score = min(critical_count / max(len(contexts), 1), 1.0)
        details = f"{critical_count} archivos críticos detectados"
        return score, details

    def _score_size(self, diff_content: str) -> tuple[float, str]:
        lines = diff_content.split("\n")
        additions = sum(1 for l in lines if l.startswith("+") and not l.startswith("++"))
        deletions = sum(1 for l in lines if l.startswith("-") and not l.startswith("--"))
        total = additions + deletions
        
        score = min(total / 500, 1.0)
        details = f"{total} líneas ({additions}+, {deletions}-)"
        return score, details

    def _score_hot_files(self, contexts: list[EnrichedFileContext]) -> tuple[float, str]:
        hot_count = 0
        hot_files = []
        
        for ctx in contexts:
            if self.git_client.is_file_hot(ctx.file_context.file_path, days=30):
                hot_count += 1
                hot_files.append(ctx.file_context.file_path)
        
        if not contexts:
            return 0.0, "Sin contexto"
        
        score = min(hot_count / max(len(contexts), 1), 1.0)
        details = f"{hot_count} archivos 'calientes' (muchos cambios recientes)"
        return score, details

    def _analyze_impact(
        self,
        diff_content: str,
        file_paths: list[str],
        get_content_func=None
    ) -> Optional[ImpactAnalysis]:
        try:
            return self.usage_analyzer.analyze_impact(
                diff_content,
                file_paths,
                get_content_func
            )
        except Exception:
            return None

    def _get_complexity(self, score: float) -> str:
        if score < 0.3:
            return "low"
        elif score < 0.6:
            return "medium"
        return "high"

    def _generate_recommendations(
        self,
        score: float,
        factors: list[ScoringFactor],
        impact: Optional[ImpactAnalysis],
        contexts: list[EnrichedFileContext]
    ) -> list[str]:
        recs = []
        
        if impact and impact.recommendations:
            recs.extend(impact.recommendations)
        
        if score > 0.75:
            recs.append("🚨 PR BLOQUEADO - Requiere revisión obligatoria antes de merge")
        elif score > 0.5:
            recs.append("⚠️ Revisar manualmente antes de merge")
        
        critical_contexts = [c for c in contexts if c.file_context.is_critical]
        if critical_contexts:
            recs.append(f"📁 Archivos críticos modificados: {len(critical_contexts)}")
            for ctx in critical_contexts[:3]:
                recs.append(f"   - {ctx.file_context.file_path}")
        
        hot_files = [c.file_context.file_path for c in contexts 
                     if self.git_client.is_file_hot(c.file_context.file_path)]
        if hot_files:
            recs.append(f"🔥 Archivos frecuentemente modificados: {len(hot_files)}")
        
        if not recs:
            recs.append("✅ PR de bajo riesgo - Aprobación estándar")
        
        return recs

    def _generate_summary(self, score: float, complexity: str, affected: int) -> str:
        if score > 0.75:
            return f"PR de ALTO RIESGO (score: {score:.2f}). {affected} archivos afectados. Requiere revisión manual obligatoria."
        elif score > 0.5:
            return f"PR de RIESGO MEDIO (score: {score:.2f}). Complejidad {complexity}. Se recomienda revisión manual."
        elif score > 0.3:
            return f"PR de BAJO RIESGO (score: {score:.2f}). Complejidad {complexity}. Aprobación estándar."
        return f"PR de RIESGO MÍNIMO (score: {score:.2f}). Safe to merge con aprobación rutinaria."


def score_pr(
    diff_content: str,
    enriched_contexts: list[EnrichedFileContext],
    file_paths: list[str],
    repo_path: str = "."
) -> PRScoring:
    calculator = PRScoreCalculator(repo_path)
    return calculator.calculate_score(diff_content, enriched_contexts, file_paths)
