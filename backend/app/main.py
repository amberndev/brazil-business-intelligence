from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .db import lifespan
from .errors import error_response, http_exception_handler, validation_exception_handler
from .routers import company, health, keys, market, search

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Brazil Business Intelligence API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type"],
    allow_credentials=False,
)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all 500 — every unhandled exception returns the JSON error envelope
    instead of Starlette's bare 'Internal Server Error' text (F-103)."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return error_response("internal_error", "Internal server error.", 500)


app.include_router(health.router,   prefix="/v1")
app.include_router(company.router,  prefix="/v1")
app.include_router(search.router,   prefix="/v1")
app.include_router(market.router,   prefix="/v1")
app.include_router(keys.router,     prefix="/v1")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8100, reload=False)
