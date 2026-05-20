import json

from pydantic import AnyUrl
from sqlalchemy.orm import Session

import game_services
import services
from database import SessionLocal
from mcp_bank.resources.definitions import BALANCES_URI, GAME_URI, LEADERBOARD_URI
from mcp_bank.runtime import require_session
from models import User


def _load_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


async def read_bank_resource(uri: AnyUrl) -> str:
    uri_str = str(uri)
    session = require_session()
    db = SessionLocal()
    try:
        user = _load_user(db, session.user_id)
        if user is None:
            raise ValueError("Utilisateur introuvable.")

        if uri_str == str(BALANCES_URI):
            return _read_balances(db, user)
        if uri_str == str(LEADERBOARD_URI):
            return _read_leaderboard(db)
        if uri_str == str(GAME_URI):
            return _read_game(db, user)
        raise ValueError(f"Unknown resource URI: {uri}")
    finally:
        db.close()


def _read_balances(db: Session, user: User) -> str:
    pot = services.get_common_pot(db)
    pot_metrics = game_services.get_pot_metrics(db)
    payload: dict[str, object] = {
        "holder": user.name,
        "role": "host" if services.is_host(user) else "student",
        "personal_balance_eur": round(user.balance, 2),
        "common_pot_balance_eur": round(pot.balance, 2),
        **pot_metrics,
    }
    if services.is_host(user):
        payload["mutations_are_mocked"] = True
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _read_leaderboard(db: Session) -> str:
    return json.dumps(
        {"leaderboard": game_services.get_leaderboard(db)},
        ensure_ascii=False,
        indent=2,
    )


def _read_game(db: Session, user: User) -> str:
    return json.dumps(
        game_services.get_game_status_payload(db, user),
        ensure_ascii=False,
        indent=2,
    )
