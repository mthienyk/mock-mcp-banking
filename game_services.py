"""Mécaniques de jeu : phases, slots, alliances, classement."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from mcp_bank.game_rules import (
    ALLIANCE_MAX_PER_USER,
    MAX_WITHDRAWALS_PER_WINDOW,
    MIN_TRANSACTION_EUR,
    POT_INITIAL_EUR,
    SPY_COOLDOWN_MIN,
    SPY_COST_EUR,
    WITHDRAW_WINDOW_MIN,
    GamePhase,
    PhaseRules,
    next_play_phase,
    pot_scarcity_multiplier,
    rules_for_phase,
)
from models import (
    Alliance,
    AllianceProposal,
    BalanceSpy,
    GameMeta,
    TaxVote,
    User,
    UserGameState,
)
import services

HOST_NAME = services.HOST_NAME


def session_not_started_message() -> str:
    return f"{HOST_NAME} n'a pas encore démarré la session."


def migrate_game_schema() -> None:
    """Migrations légères game_meta (phase, session_started_at)."""
    from sqlalchemy import inspect, text

    from database import get_engine

    try:
        db_engine = get_engine()
    except RuntimeError:
        return
    inspector = inspect(db_engine)
    if "game_meta" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("game_meta")}
    statements: list[str] = []
    if "phase" not in columns:
        statements.append(
            "ALTER TABLE game_meta ADD COLUMN phase VARCHAR DEFAULT 'discovery'"
        )
    if "session_started_at" not in columns:
        statements.append("ALTER TABLE game_meta ADD COLUMN session_started_at DATETIME")
    if not statements:
        return
    with db_engine.connect() as connection:
        for ddl in statements:
            connection.execute(text(ddl))
        connection.execute(
            text("UPDATE game_meta SET phase = 'discovery' WHERE phase IS NULL")
        )
        connection.commit()


def _parse_stored_phase(value: str | None) -> GamePhase:
    if not value:
        return GamePhase.DISCOVERY
    try:
        return GamePhase(value)
    except ValueError:
        return GamePhase.DISCOVERY


def ensure_game_meta(db: Session) -> GameMeta:
    meta = db.query(GameMeta).first()
    if not meta:
        meta = GameMeta(
            started_at=datetime.utcnow(),
            session_started_at=None,
            phase=GamePhase.DISCOVERY.value,
        )
        db.add(meta)
        db.commit()
        db.refresh(meta)
    elif not getattr(meta, "phase", None):
        meta.phase = GamePhase.DISCOVERY.value
        db.commit()
        db.refresh(meta)
    return meta


def is_session_started(db: Session) -> bool:
    meta = ensure_game_meta(db)
    return meta.session_started_at is not None


def is_session_active(db: Session) -> bool:
    meta = ensure_game_meta(db)
    return meta.session_started_at is not None and meta.frozen_at is None


def freeze_game(db: Session, reason: str = "Animateur") -> GameMeta:
    meta = ensure_game_meta(db)
    if meta.frozen_at is None:
        meta.frozen_at = datetime.utcnow()
        meta.frozen_reason = reason
        db.commit()
        db.refresh(meta)
    return meta


def unfreeze_game(db: Session) -> GameMeta:
    meta = ensure_game_meta(db)
    meta.frozen_at = None
    meta.frozen_reason = None
    db.commit()
    db.refresh(meta)
    return meta


def host_start_game_session(db: Session, user: User) -> dict[str, Any]:
    if not services.is_host(user):
        raise ValueError("Outil réservé à l'animateur.")
    meta = ensure_game_meta(db)
    if meta.session_started_at is not None and meta.frozen_at is None:
        raise ValueError(
            "La session est déjà en cours. Utilisez end_game_session pour terminer."
        )
    meta.session_started_at = datetime.utcnow()
    meta.phase = GamePhase.DISCOVERY.value
    meta.frozen_at = None
    meta.frozen_reason = None
    db.commit()
    db.refresh(meta)
    return {
        "success": True,
        "message": "Session démarrée. Les élèves peuvent jouer.",
        "phase": meta.phase,
    }


def host_end_game_session(db: Session, user: User) -> dict[str, Any]:
    if not services.is_host(user):
        raise ValueError("Outil réservé à l'animateur.")
    meta = ensure_game_meta(db)
    if meta.session_started_at is None:
        raise ValueError("Aucune session en cours à terminer.")
    freeze_game(db, "Fin de session animateur")
    return {
        "success": True,
        "message": "Session terminée. Classement figé.",
    }


def host_advance_game_phase(db: Session, user: User) -> dict[str, Any]:
    if not services.is_host(user):
        raise ValueError("Outil réservé à l'animateur.")
    meta = ensure_game_meta(db)
    if meta.session_started_at is None:
        raise ValueError(session_not_started_message())
    if meta.frozen_at is not None:
        raise ValueError("La session est terminée.")
    current = _parse_stored_phase(meta.phase)
    upcoming = next_play_phase(current)
    if upcoming is None:
        raise ValueError(
            f"Déjà en {rules_for_phase(current).label}. "
            "Utilisez end_game_session pour terminer."
        )
    meta.phase = upcoming.value
    db.commit()
    db.refresh(meta)
    return {
        "success": True,
        "phase": upcoming.value,
        "phase_label": rules_for_phase(upcoming).label,
        "message": f"Phase avancée : {rules_for_phase(upcoming).label}.",
    }


def current_phase(db: Session) -> GamePhase:
    meta = ensure_game_meta(db)
    if meta.frozen_at is not None:
        return GamePhase.FROZEN
    if meta.session_started_at is None:
        return GamePhase.LOBBY
    return _parse_stored_phase(meta.phase)


def current_rules(db: Session) -> PhaseRules:
    return rules_for_phase(current_phase(db))


def get_pot_metrics(db: Session) -> dict[str, Any]:
    pot = services.get_common_pot(db)
    balance = pot.balance
    ratio = balance / POT_INITIAL_EUR if POT_INITIAL_EUR > 0 else 0.0
    ratio = max(0.0, min(1.0, ratio))
    multiplier = pot_scarcity_multiplier(ratio)
    if ratio > 0.70:
        scarcity_label = "normal"
        scarcity_hint = "Retraits au plafond de phase."
    elif ratio > 0.40:
        scarcity_label = "tension"
        scarcity_hint = "Pot sous 70 % : plafond de retrait réduit à 75 %."
    elif ratio > 0.15:
        scarcity_label = "rarete"
        scarcity_hint = "Pot sous 40 % : plafond de retrait réduit à 50 %."
    else:
        scarcity_label = "critique"
        scarcity_hint = "Pot sous 15 % : plafond de retrait réduit à 25 %."
    return {
        "common_pot_eur": round(balance, 2),
        "pot_initial_eur": POT_INITIAL_EUR,
        "pot_remaining_pct": round(ratio * 100, 1),
        "withdraw_cap_multiplier": multiplier,
        "pot_scarcity": scarcity_label,
        "pot_scarcity_hint": scarcity_hint,
    }


def effective_max_withdraw_eur(db: Session) -> float:
    rules = current_rules(db)
    metrics = get_pot_metrics(db)
    return round(rules.max_withdraw_eur * metrics["withdraw_cap_multiplier"], 2)


def get_tax_pressure(db: Session, user: User) -> dict[str, Any]:
    """Votes de taxation en cours (lecture seule, pour piloter la stratégie)."""
    if services.is_host(user):
        return {
            "active_campaigns": [],
            "votes_against_you": [],
            "votes_needed_to_tax_you": None,
            "your_balance_at_risk_eur": 0.0,
            "hint": "Animateur : pas de pression fiscale personnelle.",
        }

    campaigns: list[dict[str, Any]] = []
    students = (
        db.query(User)
        .filter(~User.name.ilike(HOST_NAME))
        .order_by(User.name)
        .all()
    )
    for target in students:
        votes = (
            db.query(TaxVote)
            .filter(TaxVote.target_id == target.id)
            .all()
        )
        if not votes:
            continue
        voter_names = [v.voter.name for v in votes]
        needed = taxation_votes_required(db, target)
        campaigns.append(
            {
                "target_name": target.name,
                "voters": voter_names,
                "vote_count": len(voter_names),
                "votes_needed": needed,
                "votes_remaining": max(0, needed - len(voter_names)),
                "you_already_voted": user.name in voter_names,
                "target_has_alliance": has_alliance(db, target),
            }
        )

    against_me = (
        db.query(TaxVote)
        .filter(TaxVote.target_id == user.id)
        .all()
    )
    votes_against_you = [v.voter.name for v in against_me]
    needed_on_you = (
        taxation_votes_required(db, user) if user.balance > MIN_TRANSACTION_EUR else None
    )

    hint = "Aucune campagne de taxation active."
    if votes_against_you:
        remaining = (needed_on_you or 0) - len(votes_against_you)
        hint = (
            f"{len(votes_against_you)} vote(s) contre vous "
            f"({remaining} de plus pour confiscation totale)."
        )
    elif campaigns:
        hint = (
            f"{len(campaigns)} campagne(s) en cours. "
            "Coordonnez tax_user ou protégez le leader."
        )

    return {
        "active_campaigns": campaigns,
        "votes_against_you": votes_against_you,
        "votes_needed_to_tax_you": needed_on_you,
        "votes_remaining_to_tax_you": (
            max(0, (needed_on_you or 0) - len(votes_against_you))
            if needed_on_you
            else None
        ),
        "your_balance_at_risk_eur": round(user.balance, 2),
        "hint": hint,
    }


def ensure_user_game_state(db: Session, user: User) -> UserGameState:
    state = db.query(UserGameState).filter(UserGameState.user_id == user.id).first()
    if not state:
        state = UserGameState(user_id=user.id)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def _reset_withdraw_window_if_needed(state: UserGameState, now: datetime) -> None:
    if state.withdraw_window_start is None:
        state.withdraw_window_start = now
        state.withdraw_count_in_window = 0
        return
    window_end = state.withdraw_window_start + timedelta(minutes=WITHDRAW_WINDOW_MIN)
    if now >= window_end:
        state.withdraw_window_start = now
        state.withdraw_count_in_window = 0


def assert_session_started(db: Session) -> None:
    meta = ensure_game_meta(db)
    if meta.session_started_at is None:
        raise ValueError(session_not_started_message())


def assert_game_mutable(db: Session) -> PhaseRules:
    assert_session_started(db)
    if current_phase(db) == GamePhase.FROZEN:
        raise ValueError(
            "La session est terminée. Consultez get_leaderboard ou bank://leaderboard."
        )
    return rules_for_phase(current_phase(db))


def _status_common(db: Session) -> dict[str, Any]:
    meta = ensure_game_meta(db)
    phase = current_phase(db)
    rules = rules_for_phase(phase)
    pot_metrics = get_pot_metrics(db)
    waiting = meta.session_started_at is None
    return {
        "phase": phase.value,
        "phase_label": rules.label,
        "phase_hint": rules.hint if not waiting else session_not_started_message(),
        "session_started": not waiting,
        "session_active": is_session_active(db),
        "waiting_message": session_not_started_message() if waiting else None,
        "game_frozen": meta.frozen_at is not None,
        **pot_metrics,
    }


def get_public_game_status(db: Session) -> dict[str, Any]:
    return _status_common(db)


def get_game_status_payload(db: Session, user: User) -> dict[str, Any]:
    base = _status_common(db)
    phase = current_phase(db)
    rules = rules_for_phase(phase)
    state = ensure_user_game_state(db, user)
    alliance_view = get_alliance_view(db, user)
    pending = (
        db.query(AllianceProposal)
        .filter(
            AllianceProposal.target_id == user.id,
            AllianceProposal.status == "pending",
        )
        .all()
    )

    unlock_wait_sec = 0
    if state.last_slot_unlock_at and phase != GamePhase.FROZEN:
        elapsed = (datetime.utcnow() - state.last_slot_unlock_at).total_seconds()
        unlock_wait_sec = max(0, int(rules.unlock_cooldown_sec - elapsed))

    max_withdraw_phase = rules.max_withdraw_eur
    max_withdraw_effective = effective_max_withdraw_eur(db)

    return {
        **base,
        "your_withdrawal_slots": state.withdrawal_slots,
        "max_slots_banked": rules.max_slots_banked,
        "unlock_cooldown_remaining_sec": unlock_wait_sec,
        "withdrawals_used_in_window": state.withdraw_count_in_window,
        "withdrawals_max_in_window": MAX_WITHDRAWALS_PER_WINDOW,
        "withdraw_window_minutes": WITHDRAW_WINDOW_MIN,
        "max_withdraw_eur_phase": max_withdraw_phase,
        "max_withdraw_eur": max_withdraw_effective,
        "max_transfer_eur": rules.max_transfer_eur,
        "taxation_votes_required_default": rules.taxation_votes_required,
        "taxation_votes_required_allied_target_phase2": 3,
        "spy_cost_eur": SPY_COST_EUR,
        "spy_cooldown_minutes": SPY_COOLDOWN_MIN,
        "personal_balance_eur": round(user.balance, 2),
        "alliance_partner": alliance_view.partner_name if alliance_view else None,
        "pending_alliance_from": [p.proposer.name for p in pending],
        "tax_pressure": get_tax_pressure(db, user),
    }


def unlock_withdrawal_slot(db: Session, user: User) -> dict[str, Any]:
    if services.is_host(user):
        return {
            "success": True,
            "mock": True,
            "slots": 99,
            "message": "[Simulation] Slot de retrait fictif débloqué.",
        }

    rules = assert_game_mutable(db)
    state = ensure_user_game_state(db, user)
    now = datetime.utcnow()

    if state.withdrawal_slots >= rules.max_slots_banked:
        raise ValueError(
            f"Slots pleins ({rules.max_slots_banked} max). "
            "Retirez d'abord avec withdraw_from_common_pot."
        )

    if state.last_slot_unlock_at:
        elapsed = (now - state.last_slot_unlock_at).total_seconds()
        if elapsed < rules.unlock_cooldown_sec:
            wait = int(rules.unlock_cooldown_sec - elapsed)
            raise ValueError(
                f"Cooldown actif. Réessayez dans {wait} s "
                "(vérifiez unlock_cooldown_remaining_sec via get_game_status)."
            )

    state.withdrawal_slots += 1
    state.last_slot_unlock_at = now
    db.commit()

    return {
        "success": True,
        "slots": state.withdrawal_slots,
        "max_slots": rules.max_slots_banked,
        "next_unlock_cooldown_sec": rules.unlock_cooldown_sec,
        "message": (
            f"Slot débloqué ({state.withdrawal_slots}/{rules.max_slots_banked}). "
            "Un retrait consomme 1 slot."
        ),
    }


def _validate_withdraw_amount(
    db: Session,
    amount: float,
    rules: PhaseRules,
) -> None:
    if amount < MIN_TRANSACTION_EUR:
        raise ValueError("Montant trop faible.")
    cap = effective_max_withdraw_eur(db)
    if amount > cap:
        metrics = get_pot_metrics(db)
        raise ValueError(
            f"Max {cap:.0f} € actuellement (phase {rules.max_withdraw_eur:.0f} €, "
            f"pot à {metrics['pot_remaining_pct']:.0f} % → "
            f"multiplicateur {metrics['withdraw_cap_multiplier']:.2f})."
        )


def consume_withdrawal_slot(db: Session, user: User, amount: float) -> None:
    """Vérifie slots et fenêtre avant retrait réel."""
    rules = assert_game_mutable(db)
    _validate_withdraw_amount(db, amount, rules)
    state = ensure_user_game_state(db, user)
    now = datetime.utcnow()
    _reset_withdraw_window_if_needed(state, now)

    if state.withdrawal_slots < 1:
        raise ValueError(
            "Aucun slot de retrait. Appelez unlock_withdrawal_slot d'abord "
            "(automatisez : unlock → withdraw en script)."
        )

    if state.withdraw_count_in_window >= MAX_WITHDRAWALS_PER_WINDOW:
        raise ValueError(
            f"Limite de {MAX_WITHDRAWALS_PER_WINDOW} retraits "
            f"sur {WITHDRAW_WINDOW_MIN} min atteinte. Attendez ou transférez."
        )

    state.withdrawal_slots -= 1
    state.withdraw_count_in_window += 1
    db.flush()


def validate_transfer_amount(db: Session, amount: float) -> PhaseRules:
    rules = assert_game_mutable(db)
    if amount < MIN_TRANSACTION_EUR:
        raise ValueError("Montant trop faible.")
    if amount > rules.max_transfer_eur:
        raise ValueError(
            f"Max {rules.max_transfer_eur:.0f} € par transfert en phase actuelle."
        )
    return rules


def taxation_votes_required(db: Session, target: User) -> int:
    rules = current_rules(db)
    if current_phase(db) == GamePhase.FROZEN:
        return 99
    base = rules.taxation_votes_required
    if current_phase(db) == GamePhase.PRESSURE and has_alliance(db, target):
        return 3
    return base


def get_active_alliance(db: Session, user: User) -> Alliance | None:
    return (
        db.query(Alliance)
        .filter((Alliance.user_a_id == user.id) | (Alliance.user_b_id == user.id))
        .first()
    )


def has_alliance(db: Session, user: User) -> bool:
    return get_active_alliance(db, user) is not None


def _alliance_partner_name(alliance: Alliance, user: User) -> str:
    if alliance.user_a_id == user.id:
        return alliance.user_b.name
    return alliance.user_a.name


class AllianceView:
    def __init__(self, alliance: Alliance, user: User) -> None:
        self.alliance = alliance
        self.partner_name = _alliance_partner_name(alliance, user)


def get_alliance_view(db: Session, user: User) -> AllianceView | None:
    alliance = get_active_alliance(db, user)
    if not alliance:
        return None
    db.refresh(alliance.user_a)
    db.refresh(alliance.user_b)
    return AllianceView(alliance, user)


def count_user_alliances(db: Session, user_id: int) -> int:
    return (
        db.query(Alliance)
        .filter((Alliance.user_a_id == user_id) | (Alliance.user_b_id == user_id))
        .count()
    )


def propose_alliance(db: Session, user: User, partner_name: str) -> dict[str, Any]:
    if services.is_host(user):
        return {
            "success": True,
            "mock": True,
            "message": f"[Simulation] Alliance fictive proposée à {partner_name}.",
        }

    assert_game_mutable(db)
    partner = services.get_user_by_name(db, partner_name)
    if not partner:
        raise ValueError(f"'{partner_name}' introuvable.")
    if services.is_host(partner):
        raise ValueError("Impossible d'allier l'animateur.")
    if partner.id == user.id:
        raise ValueError("Pas d'alliance avec soi-même.")
    if count_user_alliances(db, user.id) >= ALLIANCE_MAX_PER_USER:
        raise ValueError("Vous avez déjà une alliance active.")
    if count_user_alliances(db, partner.id) >= ALLIANCE_MAX_PER_USER:
        raise ValueError(f"{partner.name} a déjà une alliance.")

    reverse_pending = (
        db.query(AllianceProposal)
        .filter(
            AllianceProposal.proposer_id == partner.id,
            AllianceProposal.target_id == user.id,
            AllianceProposal.status == "pending",
        )
        .first()
    )
    if reverse_pending:
        raise ValueError(
            f"{partner.name} vous a déjà proposé une alliance. "
            "Utilisez respond_alliance au lieu de reproposer."
        )

    existing = (
        db.query(AllianceProposal)
        .filter(
            AllianceProposal.proposer_id == user.id,
            AllianceProposal.target_id == partner.id,
            AllianceProposal.status == "pending",
        )
        .first()
    )
    if existing:
        raise ValueError(f"Proposition déjà en attente pour {partner.name}.")

    proposal = AllianceProposal(proposer_id=user.id, target_id=partner.id)
    db.add(proposal)
    db.commit()
    return {
        "success": True,
        "partner": partner.name,
        "message": (
            f"Alliance proposée à {partner.name}. "
            f"{partner.name} doit appeler respond_alliance avec votre prénom."
        ),
    }


def respond_alliance(
    db: Session,
    user: User,
    proposer_name: str,
    accept: bool,
) -> dict[str, Any]:
    if services.is_host(user):
        return {
            "success": True,
            "mock": True,
            "message": f"[Simulation] Réponse fictive à {proposer_name}.",
        }

    assert_game_mutable(db)
    proposer = services.get_user_by_name(db, proposer_name)
    if not proposer:
        raise ValueError(f"'{proposer_name}' introuvable.")

    proposal = (
        db.query(AllianceProposal)
        .filter(
            AllianceProposal.proposer_id == proposer.id,
            AllianceProposal.target_id == user.id,
            AllianceProposal.status == "pending",
        )
        .first()
    )
    if not proposal:
        raise ValueError(f"Aucune proposition en attente de {proposer.name}.")

    proposal.status = "accepted" if accept else "rejected"
    if not accept:
        db.commit()
        return {
            "success": True,
            "accepted": False,
            "message": f"Alliance refusée avec {proposer.name}.",
        }

    if count_user_alliances(db, user.id) >= ALLIANCE_MAX_PER_USER:
        raise ValueError("Vous avez déjà une alliance.")
    if count_user_alliances(db, proposer.id) >= ALLIANCE_MAX_PER_USER:
        raise ValueError(f"{proposer.name} a déjà une alliance.")

    alliance = Alliance(user_a_id=proposer.id, user_b_id=user.id)
    db.add(alliance)
    for proposal in (
        db.query(AllianceProposal)
        .filter(AllianceProposal.status == "pending")
        .filter(
            AllianceProposal.proposer_id.in_([proposer.id, user.id]),
            AllianceProposal.target_id.in_([proposer.id, user.id]),
        )
        .all()
    ):
        proposal.status = "expired"
    db.commit()

    return {
        "success": True,
        "accepted": True,
        "partner": proposer.name,
        "message": (
            f"Alliance formée avec {proposer.name}. "
            "get_alliance_intel révèle son solde. "
            "En phase 2, taxation contre vous ou votre allié : 3 votes requis."
        ),
    }


def get_alliance_intel(db: Session, user: User) -> dict[str, Any]:
    if services.is_host(user):
        return {"mock": True, "message": "[Simulation] Pas d'alliance réelle."}

    view = get_alliance_view(db, user)
    if not view:
        raise ValueError(
            "Pas d'alliance active. propose_alliance puis respond_alliance."
        )

    partner = (
        view.alliance.user_b
        if view.alliance.user_a_id == user.id
        else view.alliance.user_a
    )
    return {
        "partner": partner.name,
        "partner_balance_eur": round(partner.balance, 2),
        "your_balance_eur": round(user.balance, 2),
        "formed_at": view.alliance.formed_at.isoformat(),
    }


def spy_player_balance(db: Session, user: User, target_name: str) -> dict[str, Any]:
    if services.is_host(user):
        return {
            "mock": True,
            "target": target_name,
            "balance_eur": 0.0,
            "message": "[Simulation] Espionnage fictif.",
        }

    assert_game_mutable(db)
    target = services.get_user_by_name(db, target_name)
    if not target:
        raise ValueError(f"'{target_name}' introuvable.")
    if services.is_host(target):
        raise ValueError("Impossible d'espionner l'animateur.")
    if target.id == user.id:
        raise ValueError("Utilisez get_balances pour votre propre solde.")

    if user.balance < SPY_COST_EUR:
        raise ValueError(f"Espionnage coûte {SPY_COST_EUR:.0f} € (solde insuffisant).")

    now = datetime.utcnow()
    last = (
        db.query(BalanceSpy)
        .filter(BalanceSpy.spy_id == user.id, BalanceSpy.target_id == target.id)
        .order_by(BalanceSpy.spied_at.desc())
        .first()
    )
    if last:
        cooldown_end = last.spied_at + timedelta(minutes=SPY_COOLDOWN_MIN)
        if now < cooldown_end:
            wait = int((cooldown_end - now).total_seconds())
            raise ValueError(f"Cooldown espionnage : {wait} s restantes sur {target.name}.")

    user.balance -= SPY_COST_EUR
    pot = services.get_common_pot(db)
    pot.balance += SPY_COST_EUR
    db.add(BalanceSpy(spy_id=user.id, target_id=target.id, spied_at=now))
    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "target": target.name,
        "balance_eur": round(target.balance, 2),
        "cost_eur": SPY_COST_EUR,
        "your_balance_eur": round(user.balance, 2),
    }


def get_leaderboard(db: Session, *, limit: int = 20) -> list[dict[str, Any]]:
    students = (
        db.query(User)
        .filter(~User.name.ilike(HOST_NAME))
        .order_by(User.balance.desc())
        .all()
    )
    ranked: list[dict[str, Any]] = []
    for idx, student in enumerate(students[:limit], start=1):
        ranked.append(
            {
                "rank": idx,
                "name": student.name,
                "balance_eur": round(student.balance, 2),
            }
        )
    return ranked
