"""JSON Schemas for MCP tools (strict bounds, enums)."""

from typing import Any

import services

MAX_TRANSACTION_EUR = 1000.0
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


def amount_property(*, description: str) -> dict[str, Any]:
    return {
        "type": "number",
        "minimum": MIN_TRANSACTION_EUR,
        "maximum": MAX_TRANSACTION_EUR,
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
            description="Montant en euros à retirer du pot commun (max 1 000 €)."
        ),
    },
    required=["amount"],
)

TRANSFER_INPUT_SCHEMA = _object_schema(
    {
        "receiver_name": student_name_property(
            description="Prénom exact du destinataire parmi la promo."
        ),
        "amount": amount_property(
            description="Montant en euros à transférer (max 1 000 €)."
        ),
    },
    required=["receiver_name", "amount"],
)

TAX_INPUT_SCHEMA = _object_schema(
    {
        "target_name": student_name_property(
            description="Prénom exact de l'élève à taxer."
        ),
    },
    required=["target_name"],
)
