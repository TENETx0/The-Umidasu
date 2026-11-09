"""The Umidasu — FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.storage.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("umidasu")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info("%s v%s starting — data dir: %s", settings.APP_NAME, settings.APP_VERSION, settings.BASE_DIR)
    logger.warning("Localhost binding is not a complete security boundary against malicious local web pages "
                    "or browser-origin attacks. Do not expose this service beyond 127.0.0.1 without additional controls.")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=f"Universal Metadata Inspector, Editor & File Analyzer — by {settings.APP_AUTHOR}",
    lifespan=lifespan,
)

# Import parsers package to trigger plugin registration. Using `from app
# import parsers` (rather than `import app.parsers`) avoids rebinding the
# local name `app` to the package, which would shadow the FastAPI instance.
from app import parsers as _parsers_pkg  # noqa: E402,F401

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://127.0.0.1:{settings.PORT}", f"http://localhost:{settings.PORT}",
                    "http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak internals (paths, stack traces) to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred. See server logs for details."})


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION, "author": settings.APP_AUTHOR}


app.include_router(router, prefix="/api")

# Serve the built frontend (frontend/dist) as static files, so execute.sh
# can start a single process on a single port. If the frontend hasn't been
# built, API-only mode still works (useful for `npm run dev` + Vite proxy
# during frontend development).
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/favicon.svg")
    def favicon():
        return FileResponse(_FRONTEND_DIST / "favicon.svg")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # Single-page app: any non-API, non-asset path serves index.html.
        # Defense in depth: even though this path segment cannot reach here
        # with a literal ".." after Starlette's own normalization, resolve
        # and re-verify containment before ever serving a file by path.
        if full_path:
            try:
                candidate = (_FRONTEND_DIST / full_path).resolve()
                candidate.relative_to(_FRONTEND_DIST.resolve())
            except ValueError:
                candidate = None
            if candidate is not None and candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
else:
    logger.warning("Frontend build not found at %s — run execute.sh to build it, or use `npm run dev` for frontend development.", _FRONTEND_DIST)
