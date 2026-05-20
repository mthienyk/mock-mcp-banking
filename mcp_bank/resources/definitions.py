from enum import StrEnum

from mcp.types import Resource
from pydantic import AnyUrl

BALANCES_URI = AnyUrl("bank://balances")


class ResourceName(StrEnum):
    BALANCES = "balances"


BALANCES_RESOURCE = Resource(
    uri=BALANCES_URI,
    name=ResourceName.BALANCES,
    title="Soldes bancaires",
    description=(
        "Lecture seule : solde personnel de l'élève connecté et solde du pot "
        "commun. À consulter avant toute opération financière."
    ),
    mimeType="application/json",
)

ALL_RESOURCES: tuple[Resource, ...] = (BALANCES_RESOURCE,)
