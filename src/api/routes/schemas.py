from pydantic import BaseModel
from typing import Optional


class UserCommandRequest(BaseModel):
    command: str
    auto_mode: bool = False


class QuestionAnswerRequest(BaseModel):
    question_id: str
    answer: str
