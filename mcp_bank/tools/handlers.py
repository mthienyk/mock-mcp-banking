from sqlalchemy.orm import Session

import services
from mcp.types import CallToolResult
from mcp_bank.errors import parse_amount, parse_string, text_result
from mcp_bank.registry import bank_registry
import game_services
from mcp_bank.schemas import MAX_TRANSFER_EUR, MAX_WITHDRAW_EUR, MIN_TRANSACTION_EUR
from mcp_bank.tools.definitions import (
    GET_BALANCES,
    TAX_USER,
    TRANSFER_TO_USER,
    WITHDRAW_FROM_COMMON_POT,
)
from models import User


def _format_balances(db: Session, user: User, pot_balance: float) -> str:
    role = "animateur (simulation)" if services.is_host(user) else "élève"
    metrics = game_services.get_pot_metrics(db)
    lines = [
        "=== SOLDE BANCAIRE ===",
        f"Titulaire : {user.name} ({role})",
        f"Votre solde personnel : {user.balance:,.2f} €",
        f"Pot commun : {pot_balance:,.2f} € "
        f"({metrics['pot_remaining_pct']} % du pot initial)",
        f"Rareté pot : {metrics['pot_scarcity']} — {metrics['pot_scarcity_hint']}",
    ]
    if services.is_host(user):
        lines.append(
            "Mode animateur : retraits, transferts et votes sont simulés "
            "sans modifier la banque."
        )
    lines.append("=====================")
    return "\n".join(lines)


@bank_registry.register(GET_BALANCES)
async def handle_get_balances(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    pot = services.get_common_pot(db)
    return text_result(_format_balances(db, user, pot.balance))


def _validate_amount(
    amount: float | None,
    *,
    cap: float,
    label: str,
) -> str | None:
    if amount is None:
        return f"Montant invalide pour {label}."
    if amount < MIN_TRANSACTION_EUR or amount > cap:
        return (
            f"Montant hors limites pour {label} : "
            f"entre {MIN_TRANSACTION_EUR:.2f} € et {cap:.2f} € "
            "(phase active : voir get_game_status)."
        )
    return None


def _validate_student_name(name: str, field: str) -> str | None:
    if not name:
        return f"{field} requis."
    if name not in services.STUDENT_NAMES:
        return (
            f"'{name}' n'est pas un élève reconnu. "
            f"Valeurs acceptées : {', '.join(services.STUDENT_NAMES)}."
        )
    return None


@bank_registry.register(WITHDRAW_FROM_COMMON_POT)
async def handle_withdraw_from_common_pot(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    amount = parse_amount(arguments)
    cap = game_services.effective_max_withdraw_eur(db)
    error = _validate_amount(
        amount, cap=min(MAX_WITHDRAW_EUR, cap), label="retrait"
    )
    if error:
        return text_result(error, is_error=True)

    try:
        result = services.withdraw_from_common_pot(db, user, amount)  # type: ignore[arg-type]
    except ValueError as exc:
        return text_result(f"Échec du retrait : {exc}", is_error=True)

    if result.get("mock"):
        display = float(result["display_balance"])
        text = (
            f"[Simulation animateur] Retrait fictif de {amount:,.2f} €.\n"
            f"Solde affiché (démo) : {display:,.2f} €\n"
            f"Pot commun réel inchangé : {result['common_pot_balance']:,.2f} €"
        )
    else:
        text = (
            f"Retrait de {amount:,.2f} € réussi.\n"
            f"Nouveau solde de {user.name} : {result['user_balance']:,.2f} €\n"
            f"Nouveau solde du pot commun : {result['common_pot_balance']:,.2f} €"
        )
    return text_result(text)


@bank_registry.register(TRANSFER_TO_USER)
async def handle_transfer_to_user(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    receiver_name = parse_string(arguments, "receiver_name")
    amount = parse_amount(arguments)

    name_error = _validate_student_name(receiver_name, "receiver_name")
    if name_error:
        return text_result(name_error, is_error=True)

    rules = game_services.current_rules(db)
    amount_error = _validate_amount(
        amount,
        cap=min(MAX_TRANSFER_EUR, rules.max_transfer_eur),
        label="transfert",
    )
    if amount_error:
        return text_result(amount_error, is_error=True)

    try:
        result = services.transfer_funds(db, user, receiver_name, amount)  # type: ignore[arg-type]
    except ValueError as exc:
        return text_result(f"Échec du transfert : {exc}", is_error=True)

    if result.get("mock"):
        display = float(result["display_sender_balance"])
        text = (
            f"[Simulation animateur] Transfert fictif de {amount:,.2f} € "
            f"vers {result['receiver_name']}.\n"
            f"Solde affiché (démo) : {display:,.2f} €\n"
            f"Solde réel de {result['receiver_name']} inchangé : "
            f"{result['receiver_balance']:,.2f} €"
        )
    else:
        text = (
            f"Transfert réussi : {amount:,.2f} € envoyés à {result['receiver_name']}.\n"
            f"Votre nouveau solde : {result['sender_balance']:,.2f} €"
        )
    return text_result(text)


@bank_registry.register(TAX_USER)
async def handle_tax_user(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    target_name = parse_string(arguments, "target_name")
    name_error = _validate_student_name(target_name, "target_name")
    if name_error:
        return text_result(name_error, is_error=True)

    try:
        result = services.tax_user_vote(db, user, target_name)
    except ValueError as exc:
        return text_result(f"Échec du vote : {exc}", is_error=True)

    return text_result(result["message"])
