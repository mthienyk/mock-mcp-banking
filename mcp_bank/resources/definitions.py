from enum import StrEnum

from mcp.types import Resource
from pydantic import AnyUrl

BALANCES_URI = AnyUrl("bank://balances")
LEADERBOARD_URI = AnyUrl("bank://leaderboard")
GAME_URI = AnyUrl("bank://game")

_READ_HINT = "Lecture seule — équivalent JSON des outils "


class ResourceName(StrEnum):
    BALANCES = "balances"
    LEADERBOARD = "leaderboard"
    GAME = "game"


BALANCES_RESOURCE = Resource(
    uri=BALANCES_URI,
    name=ResourceName.BALANCES,
    title="Soldes",
    description=(
        f"{_READ_HINT}get_balances : solde personnel, pot commun, rôle "
        "(élève ou animateur)."
    ),
    mimeType="application/json",
)

LEADERBOARD_RESOURCE = Resource(
    uri=LEADERBOARD_URI,
    name=ResourceName.LEADERBOARD,
    title="Classement",
    description=(
        f"{_READ_HINT}get_leaderboard : rang et soldes des élèves."
    ),
    mimeType="application/json",
)

GAME_RESOURCE = Resource(
    uri=GAME_URI,
    name=ResourceName.GAME,
    title="État de partie",
    description=(
        f"{_READ_HINT}get_game_status : phase, limites, slots, rareté du pot "
        "(pot_remaining_pct), tax_pressure. Idéal pour scripts de veille."
    ),
    mimeType="application/json",
)

ALL_RESOURCES: tuple[Resource, ...] = (
    BALANCES_RESOURCE,
    LEADERBOARD_RESOURCE,
    GAME_RESOURCE,
)
