from sqlalchemy.orm import Session

import services
from mcp.types import CallToolResult
from mcp_bank.errors import parse_amount, parse_string, text_result
from mcp_bank.registry import bank_registry
from mcp_bank.schemas import MAX_TRANSACTION_EUR, MIN_TRANSACTION_EUR
from mcp_bank.tools.definitions import (
    GET_BALANCES,
    TAX_USER,
    TRANSFER_TO_USER,
    WITHDRAW_FROM_COMMON_POT,
)
from models import User


def _format_balances(user: User, pot_balance: float) -> str:
    return (
        "=== SOLDE BANCAIRE ===\n"
        f"Titulaire : {user.name}\n"
        f"Votre solde personnel : {user.balance:,.2f} €\n"
        f"Solde du pot commun : {pot_balance:,.2f} €\n"
        "====================="
    )


@bank_registry.register(GET_BALANCES)
async def handle_get_balances(
    db: Session,
    user: User,
    arguments: dict[str, object],
) -> CallToolResult:
    pot = services.get_common_pot(db)
    return text_result(_format_balances(user, pot.balance))


def _validate_amount(amount: float | None) -> str | None:
    if amount is None:
        return "Montant invalide. Entrez un nombre entre 0,01 et 1 000 €."
    if amount < MIN_TRANSACTION_EUR or amount > MAX_TRANSACTION_EUR:
        return (
            f"Montant hors limites : entre {MIN_TRANSACTION_EUR:.2f} € "
            f"et {MAX_TRANSACTION_EUR:.2f} €."
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
    error = _validate_amount(amount)
    if error:
        return text_result(error, is_error=True)

    try:
        result = services.withdraw_from_common_pot(db, user, amount)  # type: ignore[arg-type]
    except ValueError as exc:
        return text_result(f"Échec du retrait : {exc}", is_error=True)

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

    amount_error = _validate_amount(amount)
    if amount_error:
        return text_result(amount_error, is_error=True)

    try:
        result = services.transfer_funds(db, user, receiver_name, amount)  # type: ignore[arg-type]
    except ValueError as exc:
        return text_result(f"Échec du transfert : {exc}", is_error=True)

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
