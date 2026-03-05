import logging
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import get_settings
from backend.database.session import Base, engine
from backend.routers import tickets
from backend.utils.logging_config import setup_logging


settings = get_settings()
setup_logging()
logger = logging.getLogger("flowgen")

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created or verified.")


origins = settings.get_allowed_origins_list() or ["http://localhost:5173", "http://127.0.0.1:5173"]

# Allow explicit origins (ALLOWED_ORIGINS) + any *.vercel.app so preview/production URLs work without reconfig
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://[a-zA-Z0-9-]+\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],899999906y89-
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health_check() -> Dict[str, Any]:
    return {"status": "ok"}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning("HTTP error %s: %s", exc.status_code, exc.detail)
    if isinstance(exc.detail, dict):
        detail = exc.detail
    else:
        detail = {"code": "http_error", "message": str(exc.detail)}
    return JSONResponse(
        status_code=exc.status_code,
        content=detail,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error: %s", exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "validation_error",
            "message": "Request validation failed.",
            "details": {"errors": exc.errors()},
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "internal_error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


app.include_router(tickets.router)

