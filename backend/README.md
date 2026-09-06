Backend placeholder — the backend builder implements the FastAPI app here (Python 3.11+, uvicorn, asyncpg, no ORM, port 8100). See ../CONTRACT.md.

Layout:
- app/    Python package for the application (routers, db, auth, rate-limit, models).
- tests/  pytest suite.
