from fastapi import APIRouter, HTTPException, Header, Request, BackgroundTasks
from src.api.routes.schemas import UserCommandRequest
from src.agents.master_agent import MasterAgent
from src.infrastructure.queue import QueueManager, ReviewEvent, EventType
from src.infrastructure.queue.event_store import EventStore

router = APIRouter(prefix="/agent", tags=["Agent"])

master = MasterAgent()
event_store = EventStore()
queue_manager = QueueManager(event_store=event_store)


async def process_review_event(event: ReviewEvent):
    await master.review_pr(
        event.diff_content,
        event.repository,
        event.pr_number or 0
    )


@router.on_event("startup")
async def startup():
    await queue_manager.start_worker(process_review_event)


@router.on_event("shutdown")
async def shutdown():
    await queue_manager.stop_worker()


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


@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_github_delivery: str = Header(None)
):
    if not x_github_delivery:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Delivery header")

    if queue_manager.is_duplicate(x_github_delivery):
        return {
            "status": "duplicate",
            "delivery_id": x_github_delivery,
            "message": "Event already processed"
        }

    body = await request.json()
    event_type = EventType.PULL_REQUEST
    diff_content = ""
    repository = ""
    pr_number = None

    if x_github_event == "pull_request":
        action = body.get("action")
        if action in ["opened", "synchronize", "reopened"]:
            pr = body.get("pull_request", {})
            pr_number = pr.get("number")
            repository = body.get("repository", {}).get("full_name", "")
            diff_content = pr.get("diff", "")
            event_type = EventType.PULL_REQUEST

    event = ReviewEvent(
        delivery_id=x_github_delivery,
        event_type=event_type,
        repository=repository,
        pr_number=pr_number,
        diff_content=diff_content
    )

    enqueued = await queue_manager.enqueue(event)

    return {
        "status": "queued" if enqueued else "error",
        "delivery_id": x_github_delivery,
        "message": "Review queued for processing" if enqueued else "Failed to queue event"
    }


@router.get("/queue/status")
async def queue_status():
    return {
        "queue_size": queue_manager.queue_size,
        "worker_running": queue_manager.is_worker_running
    }


@router.post("/queue/process-pending")
async def process_pending():
    await queue_manager.process_pending()
    return {"status": "processed"}


@router.get("/status")
async def get_status():
    return {
        "message": "AI Code Reviewer is running",
        "graph": "LangGraph StateGraph",
        "nodes": ["security", "code_quality", "performance", "documentation", "testing", "aggregate"],
        "queue": {
            "size": queue_manager.queue_size,
            "worker_running": queue_manager.is_worker_running
        }
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
