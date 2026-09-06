from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .db import lifespan
from .errors import http_exception_handler, validation_exception_handler
from .routers import company, health, keys, market, search

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

app.include_router(health.router,   prefix="/v1")
app.include_router(company.router,  prefix="/v1")
app.include_router(search.router,   prefix="/v1")
app.include_router(market.router,   prefix="/v1")
app.include_router(keys.router,     prefix="/v1")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8100, reload=False)
