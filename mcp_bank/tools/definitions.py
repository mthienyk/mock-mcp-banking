from enum import StrEnum

from mcp.types import Tool

from mcp_bank.schemas import TAX_INPUT_SCHEMA, TRANSFER_INPUT_SCHEMA, WITHDRAW_INPUT_SCHEMA


class ToolName(StrEnum):
    WITHDRAW_FROM_COMMON_POT = "withdraw_from_common_pot"
    TRANSFER_TO_USER = "transfer_to_user"
    TAX_USER = "tax_user"


WITHDRAW_FROM_COMMON_POT = Tool(
    name=ToolName.WITHDRAW_FROM_COMMON_POT,
    description=(
        "Retirer de l'argent du pot commun vers votre compte personnel. "
        "Utilisez uniquement si vous avez besoin de fonds. "
        "Limite : 1 000 € par transaction. Ne pas utiliser pour consulter les soldes "
        "(lire la ressource bank://balances à la place)."
    ),
    inputSchema=WITHDRAW_INPUT_SCHEMA,
)

TRANSFER_TO_USER = Tool(
    name=ToolName.TRANSFER_TO_USER,
    description=(
        "Transférer de l'argent de votre compte vers un autre élève. "
        "Nécessite un solde suffisant. Limite : 1 000 € par transaction. "
        "Ne pas utiliser pour consulter les soldes."
    ),
    inputSchema=TRANSFER_INPUT_SCHEMA,
)

TAX_USER = Tool(
    name=ToolName.TAX_USER,
    description=(
        "Voter pour taxer un élève. Après 2 votes uniques, son solde personnel "
        "est confisqué et redistribué aux autres. Un seul vote par cible et par élève."
    ),
    inputSchema=TAX_INPUT_SCHEMA,
)

ALL_TOOLS: tuple[Tool, ...] = (
    WITHDRAW_FROM_COMMON_POT,
    TRANSFER_TO_USER,
    TAX_USER,
)
