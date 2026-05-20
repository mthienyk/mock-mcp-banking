import logging
import os

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from mcp.server.sse import SseServerTransport
from mcp.server import Server
from mcp.types import CallToolResult, Tool, TextContent
from models import User
import services

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="L'Élite MCP Bank")

# Enable CORS for cross-origin LLM connections and developer tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates directory setup
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
def startup_event():
    try:
        services.run_deploy_setup()
    except Exception:
        logger.exception("Database initialization failed on startup")
        raise


# Initialize the SSE transport for MCP
# Inside MCP, clients send POST messages to /messages/ with a session_id query param
sse = SseServerTransport("/messages/")


@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request, db: Session = Depends(get_db)):
    # Retrieve user from session cookie
    token = request.cookies.get("session_token")
    user = None
    if token:
        user = services.get_user_by_token(db, token)

    # Get server context variables
    base_url = str(request.base_url)
    common_pot = services.get_common_pot(db)
    transactions = services.get_transactions_history(db, limit=20)
    active_votes = services.get_active_votes_status(db)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "logged_in_user": user,
            "student_names": services.STUDENT_NAMES,
            "common_pot": common_pot,
            "transactions": transactions,
            "active_votes": active_votes,
            "base_url": base_url,
            "error": None,
        },
    )


@app.post("/login")
async def login(
    request: Request,
    name: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    # Verify promo password
    expected_password = os.getenv("SHARED_PASSWORD", "mcp-promo-2026")
    if password != expected_password:
        common_pot = services.get_common_pot(db)
        transactions = services.get_transactions_history(db, limit=20)
        active_votes = services.get_active_votes_status(db)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "logged_in_user": None,
                "student_names": services.STUDENT_NAMES,
                "common_pot": common_pot,
                "transactions": transactions,
                "active_votes": active_votes,
                "base_url": str(request.base_url),
                "error": "Mot de passe de la promo incorrect.",
            },
        )

    # Retrieve user and set cookie
    user = services.get_user_by_name(db, name)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="session_token",
        value=user.token,
        max_age=365 * 24 * 60 * 60,  # 1 year session duration
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
    """MCP GET Handshake Route. Establishes Server-Sent Events stream."""
    token = request.query_params.get("token")
    if not token:
        # Check Authorization header if query parameter is not present
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentification requise. Veuillez vous connecter pour obtenir un jeton valide.",
        )

    # We need an isolated DB session inside this endpoint coroutine
    # to find the user and to pass inside the tool callbacks
    db = SessionLocal()
    try:
        user = services.get_user_by_token(db, token)
        if not user:
            raise HTTPException(status_code=401, detail="Jeton d'API invalide.")

        # Keep a snapshot of the user id to queries inside the tool loop
        user_id = user.id
        user_name = user.name
    finally:
        db.close()

    # Create a dynamic Server instance scoped to this connection/user!
    server = Server(f"Banque MCP - {user_name}")

    # Register the tools available on this server
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="get_balances",
                description=(
                    "Consulter vos soldes bancaires. Retourne votre solde personnel "
                    "ainsi que le solde du pot commun de la banque."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="withdraw_from_common_pot",
                description=(
                    "Retirer de l'argent du pot commun vers votre compte personnel. "
                    "Limite de retrait: 1 000 € maximum par transaction. Le pot commun "
                    "démarre à 1 000 000,00 €."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "amount": {
                            "type": "number",
                            "description": "Le montant en euros à retirer (max 1000 €).",
                        }
                    },
                    "required": ["amount"],
                },
            ),
            Tool(
                name="transfer_to_user",
                description=(
                    "Transférer de l'argent de votre compte personnel vers le compte "
                    "bancaire d'un autre élève. Limite de transfert: 1 000 € maximum "
                    "par transaction. Vous devez posséder les fonds requis sur votre solde."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "receiver_name": {
                            "type": "string",
                            "description": (
                                "Le prénom exact de l'élève destinataire. Respectez la casse "
                                "et l'orthographe (ex: Sirine, Jean François, Jimmy...)."
                            ),
                        },
                        "amount": {
                            "type": "number",
                            "description": "Le montant en euros à transférer (max 1000 €).",
                        },
                    },
                    "required": ["receiver_name", "amount"],
                },
            ),
            Tool(
                name="tax_user",
                description=(
                    "Voter pour taxer et confisquer le solde d'un élève. "
                    "Dès qu'un élève reçoit 2 votes de taxation uniques de la part d'autres élèves, "
                    "l'intégralité de son argent personnel est saisie et immédiatement "
                    "redistribuée à parts égales entre tous les autres comptes d'élèves de la banque."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target_name": {
                            "type": "string",
                            "description": "Le prénom exact de la personne que vous souhaitez taxer.",
                        }
                    },
                    "required": ["target_name"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> CallToolResult:
        arguments = arguments or {}

        # Open a new short-lived session inside the tool execution block
        # to ensure database operations are isolated and clean
        local_db = SessionLocal()
        try:
            # Refresh user object in this local session
            db_user = local_db.query(User).filter(User.id == user_id).first()
            if not db_user:
                return CallToolResult(
                    content=[TextContent(type="text", text="Utilisateur introuvable.")],
                    isError=True,
                )

            if name == "get_balances":
                pot = services.get_common_pot(local_db)
                text = (
                    f"=== SOLDE BANCAIRE ===\n"
                    f"Titulaire : {db_user.name}\n"
                    f"Votre solde personnel : {db_user.balance:,.2f} €\n"
                    f"Solde du pot commun : {pot.balance:,.2f} €\n"
                    f"====================="
                )
                return CallToolResult(content=[TextContent(type="text", text=text)])

            elif name == "withdraw_from_common_pot":
                try:
                    amount = float(arguments.get("amount", 0))
                except (ValueError, TypeError):
                    return CallToolResult(
                        content=[
                            TextContent(
                                type="text", text="Montant invalide. Entrez un nombre."
                            )
                        ],
                        isError=True,
                    )

                try:
                    res = services.withdraw_from_common_pot(local_db, db_user, amount)
                    text = (
                        f"Retrait de {amount:,.2f} € réussi !\n"
                        f"Nouveau solde de {db_user.name} : {res['user_balance']:,.2f} €\n"
                        f"Nouveau solde du pot commun : {res['common_pot_balance']:,.2f} €"
                    )
                    return CallToolResult(content=[TextContent(type="text", text=text)])
                except ValueError as e:
                    return CallToolResult(
                        content=[
                            TextContent(
                                type="text", text=f"Échec du retrait : {str(e)}"
                            )
                        ],
                        isError=True,
                    )

            elif name == "transfer_to_user":
                receiver_name = str(arguments.get("receiver_name", "")).strip()
                try:
                    amount = float(arguments.get("amount", 0))
                except (ValueError, TypeError):
                    return CallToolResult(
                        content=[
                            TextContent(
                                type="text", text="Montant invalide. Entrez un nombre."
                            )
                        ],
                        isError=True,
                    )

                try:
                    res = services.transfer_funds(local_db, db_user, receiver_name, amount)
                    text = (
                        f"Transfert réussi ! {amount:,.2f} € ont été envoyés vers {res['receiver_name']}.\n"
                        f"Votre nouveau solde personnel est de : {res['sender_balance']:,.2f} €"
                    )
                    return CallToolResult(content=[TextContent(type="text", text=text)])
                except ValueError as e:
                    return CallToolResult(
                        content=[
                            TextContent(
                                type="text", text=f"Échec du transfert : {str(e)}"
                            )
                        ],
                        isError=True,
                    )

            elif name == "tax_user":
                target_name = str(arguments.get("target_name", "")).strip()
                try:
                    res = services.tax_user_vote(local_db, db_user, target_name)
                    return CallToolResult(
                        content=[TextContent(type="text", text=res["message"])]
                    )
                except ValueError as e:
                    return CallToolResult(
                        content=[
                            TextContent(type="text", text=f"Échec du vote : {str(e)}")
                        ],
                        isError=True,
                    )

            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Outil inconnu: {name}")],
                    isError=True,
                )

        finally:
            local_db.close()

    # Route connection SSE to stream
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0], streams[1], server.create_initialization_options()
        )


@app.post("/messages/")
async def handle_messages(request: Request):
    """MCP Message Router. Receives client-to-server POST messages

    for active SSE sessions.
    """
    await sse.handle_post_message(request.scope, request.receive, request._send)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
