import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from mcp_bank import (
    create_session_manager,
    extract_api_token,
    get_shared_server,
    handle_streamable_http,
    resolve_session,
    sse_transport,
)
from mcp_bank.runtime import bind_session, release_session
from models import User
import services

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")

streamable_manager = create_session_manager()


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        services.run_deploy_setup()
    except Exception:
        logger.exception("Database initialization failed on startup")
        raise
    async with streamable_manager.run():
        logger.info("MCP Streamable HTTP manager started at /mcp")
        yield


app = FastAPI(title="L'Élite MCP Bank", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)


def _index_context(
    request: Request,
    db: Session,
    *,
    logged_in_user=None,
    error: str | None = None,
) -> dict[str, object]:
    base = str(request.base_url).rstrip("/")
    token = logged_in_user.token if logged_in_user else ""
    return {
        "request": request,
        "logged_in_user": logged_in_user,
        "student_names": services.STUDENT_NAMES,
        "common_pot": services.get_common_pot(db),
        "transactions": services.get_transactions_history(db, limit=20),
        "active_votes": services.get_active_votes_status(db),
        "base_url": base + "/",
        "mcp_sse_url": f"{base}/sse?token={token}" if token else "",
        "mcp_http_url": f"{base}/mcp?token={token}" if token else "",
        "error": error,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    from mcp_bank.registry import bank_registry
    from mcp_bank.resources.definitions import ALL_RESOURCES

    db = SessionLocal()
    try:
        student_count = db.query(User).count()
    finally:
        db.close()
    return {
        "status": "ok",
        "students": str(student_count),
        "mcp_tools": str(len(bank_registry.list_tools())),
        "mcp_resources": str(len(ALL_RESOURCES)),
    }


@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session_token")
    user = services.get_user_by_token(db, token) if token else None
    return templates.TemplateResponse(
        request,
        "index.html",
        _index_context(request, db, logged_in_user=user),
    )


@app.post("/login")
async def login(
    request: Request,
    name: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    expected_password = os.getenv("SHARED_PASSWORD", "mcp-promo-2026")
    if password != expected_password:
        return templates.TemplateResponse(
            request,
            "index.html",
            _index_context(
                request,
                db,
                error="Mot de passe de la promo incorrect.",
            ),
        )

    user = services.get_user_by_name(db, name)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")

    response = RedirectResponse(url="/?mcp=1", status_code=303)
    response.set_cookie(
        key="session_token",
        value=user.token,
        max_age=365 * 24 * 60 * 60,
        httponly=True,
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response


@app.get("/sse")
async def handle_sse(request: Request):
    """MCP over SSE (legacy transport, still supported by Cursor)."""
    token = extract_api_token(request)
    session = resolve_session(token)
    reset = bind_session(session)

    server = get_shared_server()
    try:
        async with sse_transport.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options(),
            )
    finally:
        release_session(reset)


@app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
async def handle_mcp_streamable(request: Request):
    """MCP over Streamable HTTP (recommended transport, spec 2025+)."""
    token = extract_api_token(request)
    session = resolve_session(token)
    reset = bind_session(session)
    try:
        await handle_streamable_http(
            streamable_manager,
            request.scope,
            request.receive,
            request._send,
        )
    finally:
        release_session(reset)


@app.post("/messages/")
async def handle_messages(request: Request):
    """MCP message router for active SSE sessions."""
    await sse_transport.handle_post_message(
        request.scope,
        request.receive,
        request._send,
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
