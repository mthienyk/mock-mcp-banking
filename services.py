import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, initialize_database
from models import CommonPot, GameMeta, TaxVote, Transaction, User

logger = logging.getLogger(__name__)

HOST_NAME = os.getenv("HOST_NAME", "Thieny")
HOST_DEMO_BALANCE_EUR = 10_000.0

# Session participants (host account is separate)
STUDENT_NAMES = [
    "Alexandre",
    "Chahira",
    "Estelle",
    "Jean François",
    "Jimmy",
    "Julien",
    "Maxence",
    "Mickael",
    "Mohammed",
    "Pierre",
    "Rodica",
    "Sebastien",
    "Sirine",
    "Theo",
    "Yann",
]


def is_host(user: User) -> bool:
    return user.name.lower() == HOST_NAME.lower()


def count_students(db: Session) -> int:
    return db.query(User).filter(~User.name.ilike(HOST_NAME)).count()


def init_db():
    """Create tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def ensure_common_pot(db: Session) -> CommonPot:
    from mcp_bank.game_rules import POT_INITIAL_EUR

    pot = db.query(CommonPot).first()
    if not pot:
        pot = CommonPot(balance=POT_INITIAL_EUR)
        db.add(pot)
        db.commit()
        db.refresh(pot)
        logger.info("Common pot created with %.0f €", POT_INITIAL_EUR)
    return pot


def sync_students(db: Session) -> list[str]:
    """Add any student from STUDENT_NAMES missing in the database."""
    existing_names = {name.lower() for name, in db.query(User.name).all()}
    created: list[str] = []
    for name in STUDENT_NAMES:
        if name.lower() in existing_names:
            continue
        user = User(name=name, token=User.generate_token(name), balance=0.0)
        db.add(user)
        created.append(name)
    if created:
        db.commit()
        logger.info("Added students: %s", ", ".join(created))
    return created


def sync_host(db: Session) -> None:
    """Ensure the training host account exists (login + MCP, no game impact)."""
    if get_user_by_name(db, HOST_NAME):
        return
    host = User(
        name=HOST_NAME,
        token=User.generate_token(HOST_NAME),
        balance=0.0,
    )
    db.add(host)
    db.commit()
    logger.info("Host account created: %s", HOST_NAME)


def ensure_game_meta(db: Session) -> GameMeta:
    meta = db.query(GameMeta).first()
    if not meta:
        meta = GameMeta()
        db.add(meta)
        db.commit()
        db.refresh(meta)
    return meta


def seed_database(db: Session) -> None:
    """Idempotent deploy setup: tables, pot commun, liste participants à jour."""
    import game_services

    init_db()
    game_services.migrate_game_schema()
    ensure_common_pot(db)
    ensure_game_meta(db)
    sync_students(db)
    sync_host(db)


def run_deploy_setup() -> None:
    """Run before web workers start (Railway release phase + startup fallback)."""
    import game_services

    initialize_database()
    if SessionLocal is None or engine is None:
        raise RuntimeError("Database session factory unavailable after init")

    db = SessionLocal()
    try:
        seed_database(db)
        student_count = count_students(db)
        pot_balance = ensure_common_pot(db).balance
        from database import DB_BACKEND

        logger.info(
            "Deploy DB ready [%s]: %s students + host %s, pot commun %.2f €",
            DB_BACKEND,
            student_count,
            HOST_NAME,
            pot_balance,
        )
    finally:
        db.close()


def get_user_by_token(db: Session, token: str) -> Optional[User]:
    """Retrieves a user by their unique token."""
    return db.query(User).filter(User.token == token).first()


def get_user_by_name(db: Session, name: str) -> Optional[User]:
    """Retrieves a user by their name (case-insensitive)."""
    return db.query(User).filter(User.name.ilike(name)).first()


def get_common_pot(db: Session) -> CommonPot:
    """Gets the common pot record."""
    pot = db.query(CommonPot).first()
    if not pot:
        pot = CommonPot(balance=1000000.0)
        db.add(pot)
        db.commit()
    return pot


def _mock_withdraw(db: Session, user: User, amount: float) -> Dict[str, object]:
    pot = get_common_pot(db)
    return {
        "success": True,
        "mock": True,
        "amount": amount,
        "user_balance": user.balance,
        "common_pot_balance": pot.balance,
        "display_balance": HOST_DEMO_BALANCE_EUR,
    }


def _mock_transfer(
    db: Session,
    sender: User,
    receiver_name: str,
    amount: float,
) -> Dict[str, object]:
    receiver = get_user_by_name(db, receiver_name)
    if not receiver:
        raise ValueError(f"L'utilisateur '{receiver_name}' n'existe pas.")
    return {
        "success": True,
        "mock": True,
        "amount": amount,
        "sender_balance": sender.balance,
        "receiver_name": receiver.name,
        "receiver_balance": receiver.balance,
        "display_sender_balance": HOST_DEMO_BALANCE_EUR,
    }


def _mock_tax_vote(db: Session, voter: User, target_name: str) -> Dict[str, object]:
    import game_services as gs

    target = get_user_by_name(db, target_name)
    if not target:
        raise ValueError(f"L'utilisateur '{target_name}' n'existe pas.")
    if voter.id == target.id:
        raise ValueError("Vous ne pouvez pas voter pour vous taxer vous-même.")
    vote_count = db.query(TaxVote).filter(TaxVote.target_id == target.id).count()
    votes_needed = gs.taxation_votes_required(db, target)
    return {
        "success": True,
        "mock": True,
        "taxation_triggered": False,
        "target_name": target.name,
        "current_votes": vote_count,
        "votes_needed": max(0, votes_needed - vote_count),
        "message": (
            f"[Simulation animateur] Vote fictif contre {target.name}. "
            f"Aucun effet sur la banque ({vote_count}/2 votes réels en cours)."
        ),
    }


def withdraw_from_common_pot(db: Session, user: User, amount: float) -> Dict[str, any]:
    """Withdraws money from the common pot (requires a pre-unlocked slot)."""
    import game_services

    if is_host(user):
        return _mock_withdraw(db, user, amount)

    pot = get_common_pot(db)
    if pot.balance < amount:
        raise ValueError("Le pot commun ne contient pas assez de fonds.")

    game_services.consume_withdrawal_slot(db, user, amount)

    # Execute transfer
    pot.balance -= amount
    user.balance += amount

    # Log transaction
    transaction = Transaction(
        sender_id=None,  # Null represents Common Pot / System
        receiver_id=user.id,
        amount=amount,
        type="withdrawal",
        timestamp=datetime.utcnow(),
    )
    db.add(transaction)
    db.commit()
    db.refresh(user)
    db.refresh(pot)

    return {
        "success": True,
        "amount": amount,
        "user_balance": user.balance,
        "common_pot_balance": pot.balance,
    }


def transfer_funds(db: Session, sender: User, receiver_name: str, amount: float) -> Dict[str, any]:
    """Transfers funds between students (phase-dependent cap)."""
    import game_services

    if is_host(sender):
        return _mock_transfer(db, sender, receiver_name, amount)

    game_services.validate_transfer_amount(db, amount)

    if sender.balance < amount:
        raise ValueError(f"Fonds insuffisants. Solde actuel : {sender.balance} €.")

    receiver = get_user_by_name(db, receiver_name)
    if not receiver:
        raise ValueError(f"L'utilisateur '{receiver_name}' n'existe pas.")

    if is_host(receiver):
        raise ValueError(
            "Transfert vers l'animateur interdit (compte hors compétition)."
        )

    if sender.id == receiver.id:
        raise ValueError("Vous ne pouvez pas vous envoyer de l'argent à vous-même.")

    # Execute transfer
    sender.balance -= amount
    receiver.balance += amount

    # Log transaction
    transaction = Transaction(
        sender_id=sender.id,
        receiver_id=receiver.id,
        amount=amount,
        type="transfer",
        timestamp=datetime.utcnow(),
    )
    db.add(transaction)
    db.commit()
    db.refresh(sender)
    db.refresh(receiver)

    return {
        "success": True,
        "amount": amount,
        "sender_balance": sender.balance,
        "receiver_name": receiver.name,
        "receiver_balance": receiver.balance,
    }


def tax_user_vote(db: Session, voter: User, target_name: str) -> Dict[str, any]:
    """Cast a tax vote against a user. If 2 or more unique users vote to tax the same target,

    the target's entire balance is confiscated and redistributed equally among all other users.
    """
    if is_host(voter):
        return _mock_tax_vote(db, voter, target_name)

    import game_services as gs

    gs.assert_game_mutable(db)

    target = get_user_by_name(db, target_name)
    if not target:
        raise ValueError(f"L'utilisateur '{target_name}' n'existe pas.")

    if voter.id == target.id:
        raise ValueError("Vous ne pouvez pas voter pour vous taxer vous-même.")

    if is_host(target):
        raise ValueError("L'animateur ne peut pas être taxé.")

    if target.balance <= 0:
        raise ValueError(
            f"{target.name} n'a aucun solde à confisquer (vote inutile)."
        )

    # Check for duplicate vote
    existing_vote = (
        db.query(TaxVote).filter(TaxVote.voter_id == voter.id, TaxVote.target_id == target.id).first()
    )
    if existing_vote:
        raise ValueError(f"Vous avez déjà voté pour taxer {target.name}.")

    # Record the vote
    vote = TaxVote(voter_id=voter.id, target_id=target.id, created_at=datetime.utcnow())
    db.add(vote)
    db.flush()  # Push to database to get count correctly

    # Count votes against the target
    vote_count = db.query(TaxVote).filter(TaxVote.target_id == target.id).count()

    votes_needed = gs.taxation_votes_required(db, target)
    if vote_count >= votes_needed:
        # Trigger Taxation!
        taxable_amount = target.balance

        if taxable_amount > 0:
            # Get all other users (excluding the target)
            other_users = [
                u
                for u in db.query(User).filter(User.id != target.id).all()
                if not is_host(u)
            ]
            num_others = len(other_users)

            if num_others > 0:
                share = taxable_amount / num_others

                # Log confiscation transaction
                confiscation_tx = Transaction(
                    sender_id=target.id,
                    receiver_id=None,  # Redistributed to multiple
                    amount=taxable_amount,
                    type="taxation",
                    timestamp=datetime.utcnow(),
                )
                db.add(confiscation_tx)

                # Reset target's balance
                target.balance = 0.0

                # Distribute share to other users
                for recipient in other_users:
                    recipient.balance += share
                    # Log redistribution for each
                    redistrib_tx = Transaction(
                        sender_id=None,
                        receiver_id=recipient.id,
                        amount=share,
                        type="redistribution",
                        timestamp=datetime.utcnow(),
                    )
                    db.add(redistrib_tx)
            else:
                share = 0.0
        else:
            share = 0.0
            other_users = []

        # Delete all votes against this target
        db.query(TaxVote).filter(TaxVote.target_id == target.id).delete()
        db.commit()

        return {
            "success": True,
            "taxation_triggered": True,
            "target_name": target.name,
            "confiscated_amount": taxable_amount,
            "share_redistributed": share,
            "message": f"Taxation activée ! {taxable_amount} € confisqués à {target.name} et redistribués aux autres ({share:.2f} € chacun).",
        }

    db.commit()
    remaining = votes_needed - vote_count
    return {
        "success": True,
        "taxation_triggered": False,
        "target_name": target.name,
        "current_votes": vote_count,
        "votes_needed": remaining,
        "message": (
            f"Vote enregistré contre {target.name}. "
            f"({vote_count}/{votes_needed} votes requis)."
        ),
    }


def get_transactions_history(db: Session, limit: int = 20) -> List[Transaction]:
    """Gets the history of bank transactions."""
    return db.query(Transaction).order_by(Transaction.timestamp.desc()).limit(limit).all()


def get_active_votes_status(db: Session) -> Dict[str, List[str]]:
    """Gets the status of active tax votes against all users."""
    users = db.query(User).filter(~User.name.ilike(HOST_NAME)).all()
    status = {}
    for u in users:
        votes = db.query(TaxVote).filter(TaxVote.target_id == u.id).all()
        if votes:
            status[u.name] = [v.voter.name for v in votes]
    return status
