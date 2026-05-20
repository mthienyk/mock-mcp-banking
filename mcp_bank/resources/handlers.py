import json

from pydantic import AnyUrl
from sqlalchemy.orm import Session

import services
from database import SessionLocal
from mcp_bank.resources.definitions import BALANCES_URI
from mcp_bank.runtime import require_session
from models import User


def _load_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


async def read_balances(uri: AnyUrl) -> str:
    if str(uri) != str(BALANCES_URI):
        raise ValueError(f"Unknown resource URI: {uri}")

    session = require_session()
    db = SessionLocal()
    try:
        user = _load_user(db, session.user_id)
        if user is None:
            raise ValueError("Utilisateur introuvable.")
        pot = services.get_common_pot(db)
        payload = {
            "holder": user.name,
            "personal_balance_eur": round(user.balance, 2),
            "common_pot_balance_eur": round(pot.balance, 2),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
    finally:
        db.close()
