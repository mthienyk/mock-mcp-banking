"""JSON Schemas for MCP tools (strict bounds, enums)."""

from typing import Any

import services

MAX_WITHDRAW_EUR = 250.0
MAX_TRANSFER_EUR = 600.0
MIN_TRANSACTION_EUR = 0.01

_STUDENT_ENUM: list[str] = list(services.STUDENT_NAMES)


def _object_schema(
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def amount_property(*, description: str, maximum: float) -> dict[str, Any]:
    return {
        "type": "number",
        "minimum": MIN_TRANSACTION_EUR,
        "maximum": maximum,
        "description": description,
    }


def student_name_property(*, description: str) -> dict[str, Any]:
    return {
        "type": "string",
        "enum": _STUDENT_ENUM,
        "description": description,
    }


WITHDRAW_INPUT_SCHEMA = _object_schema(
    {
        "amount": amount_property(
            description=(
                "Montant en euros. Plafond effectif = phase × rareté du pot "
                "(champ max_withdraw_eur dans get_game_status)."
            ),
            maximum=MAX_WITHDRAW_EUR,
        ),
    },
    required=["amount"],
)

TRANSFER_INPUT_SCHEMA = _object_schema(
    {
        "receiver_name": student_name_property(
            description="Prénom exact du destinataire (liste des participants)."
        ),
        "amount": amount_property(
            description="Montant en euros (plafond selon phase).",
            maximum=MAX_TRANSFER_EUR,
        ),
    },
    required=["receiver_name", "amount"],
)

ALLIANCE_PROPOSE_SCHEMA = _object_schema(
    {
        "partner_name": student_name_property(
            description="Élève avec qui former une alliance."
        ),
    },
    required=["partner_name"],
)

ALLIANCE_RESPOND_SCHEMA = _object_schema(
    {
        "proposer_name": student_name_property(
            description="Prénom de l'élève qui vous a proposé l'alliance."
        ),
        "accept": {
            "type": "boolean",
            "description": "true pour accepter, false pour refuser.",
        },
    },
    required=["proposer_name", "accept"],
)

SPY_INPUT_SCHEMA = _object_schema(
    {
        "target_name": student_name_property(
            description="Élève dont vous voulez révéler le solde."
        ),
    },
    required=["target_name"],
)

TAX_INPUT_SCHEMA = _object_schema(
    {
        "target_name": student_name_property(
            description=(
                "Élève cible. Si assez de votes : solde confisqué et redistribué. "
                "Suivre tax_pressure via get_game_status."
            ),
        ),
    },
    required=["target_name"],
)
