"""Coverage cache scoped to the current resume, content and complete pipeline."""

from typing import Any

from app.domain.models import MatchResult, RequirementStatus, RequirementVerdict


def serialize(result: Any) -> Any:
    """Stores only verdict data that can be restored with current requirements."""
    return {
        "percent": result.match_percent,
        "coverage": result.coverage_score,
        "verdicts": [
            {"score": v.score, "status": v.status.value, "quote": v.resume_quote, "fragment": v.fragment_ord}
            for v in result.verdicts
        ],
    }


def restore(vacancy: Any, data: Any) -> Any:
    """Restores a cached result against the current vacancy requirements."""
    verdicts = tuple(
        RequirementVerdict(i + 1, r.text, RequirementStatus(v["status"]), v["quote"], r, v["score"], v["fragment"])
        for i, (r, v) in enumerate(zip(vacancy.requirements, data["verdicts"], strict=True))
    )
    return MatchResult(vacancy.id, data["percent"], verdicts, data["coverage"])
