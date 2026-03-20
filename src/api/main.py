from fastapi import FastAPI
from src.api.routes import health_router
from src.api.routes import agent_router


app = FastAPI(title="AI Code Reviewer", 
              description="An AI-powered code review tool that provides feedback and suggestions to improve code quality.",
              version="0.1.0")

app.include_router(health_router)
app.include_router(agent_router)

