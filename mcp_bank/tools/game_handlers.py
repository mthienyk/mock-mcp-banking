from sqlalchemy.orm import Session

import game_services
import services
from mcp.types import CallToolResult
from mcp_bank.errors import parse_bool, parse_string, text_result
from mcp_bank.registry import bank_registry
from mcp_bank.tools.definitions import (
    GET_ALLIANCE_INTEL,
    GET_GAME_STATUS,
    GET_LEADERBOARD,
    PROPOSE_ALLIANCE,
    RESPOND_ALLIANCE,
    SPY_PLAYER_BALANCE,
    UNLOCK_WITHDRAWAL_SLOT,
)
from models import User


def _format_tax_pressure(tax: dict[str, object]) -> list[str]:
    lines: list[str] = ["--- Pression fiscale ---", str(tax.get("hint", ""))]
    against = tax.get("votes_against_you") or []
    if against:
        remaining = tax.get("votes_remaining_to_tax_you")
        lines.append(
            f"Votes contre VOUS : {', '.join(str(v) for v in against)} "
            f"({remaining} vote(s) restant(s) avant confiscation)"
        )
    campaigns = tax.get("active_campaigns") or []
    for camp in campaigns:
        if not isinstance(camp, dict):
            continue
        lines.append(
            f"→ {camp.get('target_name')} : "
            f"{camp.get('vote_count')}/{camp.get('votes_needed')} "
            f"({', '.join(str(v) for v in camp.get('voters') or [])})"
        )
    return lines


def _format_game_status(payload: dict[str, object]) -> str:
    phase_cap = payload.get("max_withdraw_eur_phase", payload.get("max_withdraw_eur"))
    lines = [
        "=== ÉTAT DE LA PARTIE ===",
        f"Phase : {payload['phase_label']}",
        f"Session démarrée : {'oui' if payload.get('session_started') else 'non'}",
        f"Message : {payload.get('waiting_message') or payload.get('phase_hint', '')}",
        "",
        "--- Pot commun (partagé, fini) ---",
        f"Solde : {payload['common_pot_eur']:,.2f} € / "
        f"{payload.get('pot_initial_eur', 0):,.0f} € "
        f"({payload.get('pot_remaining_pct', 0)} % restant)",
        f"Rareté : {payload.get('pot_scarcity', 'n/a')} — "
        f"{payload.get('pot_scarcity_hint', '')}",
        "",
        "--- Vos limites de retrait ---",
        f"Slots : {payload['your_withdrawal_slots']}/"
        f"{payload['max_slots_banked']}",
        f"Cooldown déblocage : {payload['unlock_cooldown_remaining_sec']} s",
        f"Retraits fenêtre ({payload.get('withdraw_window_minutes', 20)} min) : "
        f"{payload['withdrawals_used_in_window']}/"
        f"{payload['withdrawals_max_in_window']}",
        f"Max retrait effectif : {payload['max_withdraw_eur']} € "
        f"(phase {phase_cap} €)",
        f"Max transfert : {payload['max_transfer_eur']} €",
        f"Votre solde : {payload['personal_balance_eur']:,.2f} €",
    ]
    if payload.get("alliance_partner"):
        lines.append(f"Alliance : {payload['alliance_partner']}")
    if payload.get("pending_alliance_from"):
        lines.append(
            "Propositions en attente : "
            + ", ".join(str(x) for x in payload["pending_alliance_from"])
        )
    tax = payload.get("tax_pressure")
    if isinstance(tax, dict):
        lines.extend(_format_tax_pressure(tax))
    lines.append("")
    lines.append(f"Indice phase : {payload['phase_hint']}")
    lines.append("========================")
    return "\n".join(lines)


@bank_registry.register(GET_GAME_STATUS)
async def handle_get_game_status(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    payload = game_services.get_game_status_payload(db, user)
    return text_result(_format_game_status(payload))


@bank_registry.register(GET_LEADERBOARD)
async def handle_get_leaderboard(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    rows = game_services.get_leaderboard(db)
    lines = ["=== CLASSEMENT (solde personnel) ==="]
    for row in rows:
        lines.append(
            f"#{row['rank']} {row['name']}: {row['balance_eur']:,.2f} €"
        )
    lines.append("===================================")
    return text_result("\n".join(lines))


@bank_registry.register(UNLOCK_WITHDRAWAL_SLOT)
async def handle_unlock_withdrawal_slot(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    try:
        result = game_services.unlock_withdrawal_slot(db, user)
    except ValueError as exc:
        return text_result(str(exc), is_error=True)
    return text_result(result["message"])


@bank_registry.register(PROPOSE_ALLIANCE)
async def handle_propose_alliance(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    partner = parse_string(arguments, "partner_name")
    if partner not in services.STUDENT_NAMES:
        return text_result(
            f"'{partner}' invalide. Élèves : {', '.join(services.STUDENT_NAMES)}.",
            is_error=True,
        )
    try:
        result = game_services.propose_alliance(db, user, partner)
    except ValueError as exc:
        return text_result(str(exc), is_error=True)
    return text_result(result["message"])


@bank_registry.register(RESPOND_ALLIANCE)
async def handle_respond_alliance(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    proposer = parse_string(arguments, "proposer_name")
    accept = parse_bool(arguments, "accept")
    if accept is None:
        return text_result("Champ accept (true/false) requis.", is_error=True)
    try:
        result = game_services.respond_alliance(db, user, proposer, accept)
    except ValueError as exc:
        return text_result(str(exc), is_error=True)
    return text_result(result["message"])


@bank_registry.register(GET_ALLIANCE_INTEL)
async def handle_get_alliance_intel(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    try:
        payload = game_services.get_alliance_intel(db, user)
    except ValueError as exc:
        return text_result(str(exc), is_error=True)
    if payload.get("mock"):
        return text_result(payload["message"])
    text = (
        f"Alliance avec {payload['partner']}.\n"
        f"Solde allié : {payload['partner_balance_eur']:,.2f} €\n"
        f"Votre solde : {payload['your_balance_eur']:,.2f} €"
    )
    return text_result(text)


@bank_registry.register(SPY_PLAYER_BALANCE)
async def handle_spy_player_balance(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    target = parse_string(arguments, "target_name")
    if target not in services.STUDENT_NAMES:
        return text_result(
            f"'{target}' invalide. Élèves : {', '.join(services.STUDENT_NAMES)}.",
            is_error=True,
        )
    try:
        result = game_services.spy_player_balance(db, user, target)
    except ValueError as exc:
        return text_result(str(exc), is_error=True)
    if result.get("mock"):
        return text_result(result["message"])
    return text_result(
        f"Espionnage réussi ({result['cost_eur']:.0f} € débités).\n"
        f"{result['target']} : {result['balance_eur']:,.2f} €\n"
        f"Votre solde : {result['your_balance_eur']:,.2f} €"
    )
