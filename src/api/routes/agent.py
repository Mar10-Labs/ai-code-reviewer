from fastapi import APIRouter, HTTPException
from src.api.routes.schemas import UserCommandRequest, QuestionAnswerRequest
from src.agents.master_agent import MasterAgent

router = APIRouter(prefix="/agent", tags=["Agent"])

master = MasterAgent()


@router.post("/command")
async def execute_command(request: UserCommandRequest):
    response = await master.process(request.command)
    return {
        "intent": response.intent.value,
        "message": response.message,
        "questions": response.questions,
        "context": {
            "current_issue": response.context.current_issue if response.context else None,
            "workflow_step": response.context.workflow_step if response.context else None
        } if response.context else None
    }


@router.get("/status")
async def get_git_status():
    response = await master.process("status")
    return {
        "message": response.message,
        "data": response.agent_results[0].data if response.agent_results else None
    }


@router.get("/commands")
async def list_commands():
    return {
        "commands": master.get_available_commands()
    }


@router.get("/history")
async def get_history():
    return {
        "history": [
            {"intent": h.intent.value, "message": h.message[:100]}
            for h in master._history[-10:]
        ]
    }
