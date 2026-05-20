from enum import StrEnum

from mcp.types import Tool

from mcp_bank.game_rules import SPY_COST_EUR
from mcp_bank.schemas import (
    ALLIANCE_PROPOSE_SCHEMA,
    ALLIANCE_RESPOND_SCHEMA,
    SPY_INPUT_SCHEMA,
    TAX_INPUT_SCHEMA,
    TRANSFER_INPUT_SCHEMA,
    WITHDRAW_INPUT_SCHEMA,
)

_READ = "[LECTURE] "
_WRITE = "[MUTATION] "


class ToolName(StrEnum):
    GET_BALANCES = "get_balances"
    GET_GAME_STATUS = "get_game_status"
    GET_LEADERBOARD = "get_leaderboard"
    UNLOCK_WITHDRAWAL_SLOT = "unlock_withdrawal_slot"
    WITHDRAW_FROM_COMMON_POT = "withdraw_from_common_pot"
    TRANSFER_TO_USER = "transfer_to_user"
    TAX_USER = "tax_user"
    PROPOSE_ALLIANCE = "propose_alliance"
    RESPOND_ALLIANCE = "respond_alliance"
    GET_ALLIANCE_INTEL = "get_alliance_intel"
    SPY_PLAYER_BALANCE = "spy_player_balance"
    HOST_START_GAME_SESSION = "start_game_session"
    HOST_END_GAME_SESSION = "end_game_session"
    HOST_ADVANCE_GAME_PHASE = "advance_game_phase"


GET_BALANCES = Tool(
    name=ToolName.GET_BALANCES,
    description=(
        f"{_READ}Soldes du compte connecté et du pot commun partagé. "
        "Effet : aucun. Suivant : get_game_status pour limites et phase, "
        "ou get_leaderboard pour le classement."
    ),
    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
)

GET_GAME_STATUS = Tool(
    name=ToolName.GET_GAME_STATUS,
    description=(
        f"{_READ}Tableau de bord de partie : phase, session démarrée ou non, "
        "slots de retrait, cooldowns, plafonds effectifs (pot rare → plafond "
        "réduit), tax_pressure (votes en cours contre vous ou les autres). "
        "Effet : aucun. À appeler avant toute mutation et après chaque "
        "advance_game_phase."
    ),
    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
)

GET_LEADERBOARD = Tool(
    name=ToolName.GET_LEADERBOARD,
    description=(
        f"{_READ}Classement des élèves par solde personnel (objectif de victoire). "
        "Effet : aucun. Utile pour cibler tax_user ou prioriser les alliances."
    ),
    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
)

UNLOCK_WITHDRAWAL_SLOT = Tool(
    name=ToolName.UNLOCK_WITHDRAWAL_SLOT,
    description=(
        f"{_WRITE}Prépare 1 retrait futur (ne crédite pas d'argent). "
        "Prérequis : session démarrée, slots < max_slots_banked, cooldown "
        "écoulé (voir unlock_cooldown_remaining_sec). Effet : +1 slot. "
        "Suivant obligatoire : withdraw_from_common_pot pour encaisser."
    ),
    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
)

WITHDRAW_FROM_COMMON_POT = Tool(
    name=ToolName.WITHDRAW_FROM_COMMON_POT,
    description=(
        f"{_WRITE}Retire des euros du pot commun vers votre solde personnel. "
        "Prérequis : ≥1 slot (unlock_withdrawal_slot), montant ≤ max_withdraw_eur "
        "(get_game_status, dépend de la phase et du % de pot restant). "
        "Effet : -pot, +votre solde, -1 slot, compteur fenêtre 20 min. "
        "Risque : être en tête du leaderboard attire tax_user."
    ),
    inputSchema=WITHDRAW_INPUT_SCHEMA,
)

TRANSFER_TO_USER = Tool(
    name=ToolName.TRANSFER_TO_USER,
    description=(
        f"{_WRITE}Envoie des euros à un autre élève (prénom exact, enum schema). "
        "Prérequis : solde suffisant, montant ≤ max_transfer_eur, "
        "destinataire ≠ animateur. Effet : -votre solde, +destinataire. "
        "Usage : alliances, pots communs informels, paiements entre joueurs."
    ),
    inputSchema=TRANSFER_INPUT_SCHEMA,
)

TAX_USER = Tool(
    name=ToolName.TAX_USER,
    description=(
        f"{_WRITE}Enregistre un vote pour taxer un élève. "
        "Si votes_needed atteints : confiscation 100 % du solde cible, "
        "redistribution égale à tous les autres élèves. "
        "votes_needed : 2 par défaut, 3 si cible alliée en phase pressure. "
        "1 vote par cible et par votant. Effet : irréversible si déclenché. "
        "Suivant : get_game_status.tax_pressure pour suivre les campagnes."
    ),
    inputSchema=TAX_INPUT_SCHEMA,
)

PROPOSE_ALLIANCE = Tool(
    name=ToolName.PROPOSE_ALLIANCE,
    description=(
        f"{_WRITE}Propose une alliance à un élève (1 alliance active max). "
        "Effet : proposition en attente côté cible. "
        "Suivant côté cible : respond_alliance. Si accepté : get_alliance_intel "
        "disponible sans frais d'espionnage."
    ),
    inputSchema=ALLIANCE_PROPOSE_SCHEMA,
)

RESPOND_ALLIANCE = Tool(
    name=ToolName.RESPOND_ALLIANCE,
    description=(
        f"{_WRITE}Accepte ou refuse une alliance en attente (proposer_name). "
        "Effet si accept : lien alliance, annulation des autres propositions "
        "liées. Vérifier pending_alliance_from via get_game_status."
    ),
    inputSchema=ALLIANCE_RESPOND_SCHEMA,
)

GET_ALLIANCE_INTEL = Tool(
    name=ToolName.GET_ALLIANCE_INTEL,
    description=(
        f"{_READ}Solde personnel de votre allié (alliance active uniquement). "
        "Effet : aucun. Alternative payante : spy_player_balance. "
        "Prérequis : alliance acceptée."
    ),
    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
)

SPY_PLAYER_BALANCE = Tool(
    name=ToolName.SPY_PLAYER_BALANCE,
    description=(
        f"{_WRITE}Révèle le solde d'un élève. Coût : {SPY_COST_EUR:.0f} € "
        "(débit immédiat, part vers le pot). Cooldown par cible. "
        "Prérequis : solde ≥ coût. Effet : -votre solde, information retournée. "
        "Préférer get_alliance_intel si vous êtes alliés."
    ),
    inputSchema=SPY_INPUT_SCHEMA,
)

HOST_START_GAME_SESSION = Tool(
    name=ToolName.HOST_START_GAME_SESSION,
    description=(
        f"{_WRITE}[ANIMATEUR] Démarre la session : débloque les mutations élèves, "
        "phase discovery. Effet : session_started_at, reset lobby. "
        "Appeler quand tout le monde a connecté le MCP."
    ),
    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
)

HOST_END_GAME_SESSION = Tool(
    name=ToolName.HOST_END_GAME_SESSION,
    description=(
        f"{_WRITE}[ANIMATEUR] Termine la partie : fige le classement, "
        "bloque toutes les mutations. Effet : phase frozen."
    ),
    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
)

HOST_ADVANCE_GAME_PHASE = Tool(
    name=ToolName.HOST_ADVANCE_GAME_PHASE,
    description=(
        f"{_WRITE}[ANIMATEUR] Passe discovery → pressure → finale. "
        "Effet : plafonds, cooldowns et règles de taxation mis à jour. "
        "Annoncer aux élèves de relire get_game_status après l'appel."
    ),
    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
)

ALL_TOOLS: tuple[Tool, ...] = (
    GET_BALANCES,
    GET_GAME_STATUS,
    GET_LEADERBOARD,
    UNLOCK_WITHDRAWAL_SLOT,
    WITHDRAW_FROM_COMMON_POT,
    TRANSFER_TO_USER,
    TAX_USER,
    PROPOSE_ALLIANCE,
    RESPOND_ALLIANCE,
    GET_ALLIANCE_INTEL,
    SPY_PLAYER_BALANCE,
    HOST_START_GAME_SESSION,
    HOST_END_GAME_SESSION,
    HOST_ADVANCE_GAME_PHASE,
)
