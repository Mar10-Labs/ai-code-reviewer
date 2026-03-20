from typing import Any

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    Estado base de un agente (por ejemplo, al orquestar un flujo con LangGraph).

    Nota: los issues posteriores pueden extender este modelo con tipos más específicos
    (por ejemplo, `ReviewComment`).
    """

    repo_full_name: str = Field(..., min_length=1)
    pr_number: int = Field(..., ge=1)
    status: str = Field(..., min_length=1)
    messages: list[str]
    review_comments: list[dict[str, Any]] = Field(default_factory=list)

