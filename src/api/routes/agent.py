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
        "agent_results": response.agent_results,
        "summary": response.summary,
        "context": {
            "repository": response.context.repository if response.context else None,
            "pr_number": response.context.pr_number if response.context else None
        } if response.context else None
    }


@router.post("/review")
async def review_pr(diff_content: str, repository: str = "", pr_number: int = 0):
    response = await master.review_pr(diff_content, repository, pr_number)
    return {
        "intent": response.intent.value,
        "message": response.message,
        "agent_results": response.agent_results,
        "summary": response.summary
    }


@router.get("/status")
async def get_status():
    return {
        "message": "AI Code Reviewer is running",
        "agents": [a.config.name for a in master.agents]
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
