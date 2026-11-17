from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import applications, auth, candidates, companies, health, jobs, me
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.middleware import add_security_headers

app = FastAPI(title=settings.app_name)

app.middleware("http")(add_security_headers)
# Only the listed origins may call the API from a browser. Tokens travel in the
# Authorization header, not cookies, so credentials mode stays off.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
        headers=headers,
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(applications.router)
app.include_router(me.router)
