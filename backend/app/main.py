from fastapi import FastAPI
from sqlalchemy import text

from app.core.database import engine
from app.api.routes.auth import router as auth_router
from app.api.routes.workspaces import router as workspace_router
from app.api.routes.projects import router as project_router

app = FastAPI(
    title="AI Document Generator API",
    description="Backend API for the AI-powered documentation platform",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(project_router)


@app.get("/")
def root():
    return {
        "message": "AI Document Generator API is running"
    }


@app.get("/health")
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected",
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
    }