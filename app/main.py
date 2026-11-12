from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import companies, health, jobs
from app.core.config import settings
from app.core.exceptions import AppError

app = FastAPI(title=settings.app_name)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


app.include_router(health.router)
app.include_router(companies.router)
app.include_router(jobs.router)
