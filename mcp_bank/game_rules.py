"""Règles de session. Départ et fin par l'animateur via MCP."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class GamePhase(StrEnum):
    LOBBY = "lobby"
    DISCOVERY = "discovery"
    PRESSURE = "pressure"
    FINALE = "finale"
    FROZEN = "frozen"


PHASE_ORDER: tuple[GamePhase, ...] = (
    GamePhase.DISCOVERY,
    GamePhase.PRESSURE,
    GamePhase.FINALE,
)


@dataclass(frozen=True, slots=True)
class PhaseRules:
    label: str
    max_withdraw_eur: float
    max_transfer_eur: float
    unlock_cooldown_sec: int
    max_slots_banked: int
    taxation_votes_required: int
    hint: str


PHASE_RULES: dict[GamePhase, PhaseRules] = {
    GamePhase.LOBBY: PhaseRules(
        label="En attente du départ",
        max_withdraw_eur=0.0,
        max_transfer_eur=0.0,
        unlock_cooldown_sec=999_999,
        max_slots_banked=0,
        taxation_votes_required=99,
        hint="L'animateur n'a pas encore démarré la session.",
    ),
    GamePhase.DISCOVERY: PhaseRules(
        label="Phase 1 — Repérage",
        max_withdraw_eur=150.0,
        max_transfer_eur=400.0,
        unlock_cooldown_sec=120,
        max_slots_banked=2,
        taxation_votes_required=2,
        hint="Débloquez des slots, explorez le pot, formez des alliances.",
    ),
    GamePhase.PRESSURE: PhaseRules(
        label="Phase 2 — Pression",
        max_withdraw_eur=200.0,
        max_transfer_eur=500.0,
        unlock_cooldown_sec=90,
        max_slots_banked=3,
        taxation_votes_required=2,
        hint="La taxation accélère. Les alliances protègent (3 votes requis).",
    ),
    GamePhase.FINALE: PhaseRules(
        label="Phase 3 — Rush final",
        max_withdraw_eur=250.0,
        max_transfer_eur=600.0,
        unlock_cooldown_sec=60,
        max_slots_banked=3,
        taxation_votes_required=2,
        hint="Scripts et coordination décisifs.",
    ),
    GamePhase.FROZEN: PhaseRules(
        label="Session terminée",
        max_withdraw_eur=0.0,
        max_transfer_eur=0.0,
        unlock_cooldown_sec=999_999,
        max_slots_banked=0,
        taxation_votes_required=99,
        hint="Consultez le classement. Plus aucune mutation.",
    ),
}

POT_INITIAL_EUR = float(os.getenv("GAME_POT_INITIAL_EUR", "1000000"))

MAX_WITHDRAWALS_PER_WINDOW = int(os.getenv("GAME_MAX_WITHDRAWS_WINDOW", "5"))
WITHDRAW_WINDOW_MIN = int(os.getenv("GAME_WITHDRAW_WINDOW_MINUTES", "20"))

MIN_TRANSACTION_EUR = 0.01

# Plafond de retrait réduit quand le pot commun baisse (ratio pot / initial).
POT_SCARCITY_TIERS: tuple[tuple[float, float], ...] = (
    (0.70, 1.0),
    (0.40, 0.75),
    (0.15, 0.50),
    (0.0, 0.25),
)
ALLIANCE_MAX_PER_USER = 1
SPY_COST_EUR = float(os.getenv("GAME_SPY_COST_EUR", "30"))
SPY_COOLDOWN_MIN = int(os.getenv("GAME_SPY_COOLDOWN_MINUTES", "8"))


def rules_for_phase(phase: GamePhase) -> PhaseRules:
    return PHASE_RULES[phase]


def pot_scarcity_multiplier(pot_ratio: float) -> float:
    """Multiplicateur sur max_withdraw_eur (1.0 = plein pot, moins si pot épuisé)."""
    for threshold, multiplier in POT_SCARCITY_TIERS:
        if pot_ratio >= threshold:
            return multiplier
    return POT_SCARCITY_TIERS[-1][1]


def next_play_phase(current: GamePhase) -> GamePhase | None:
    if current not in PHASE_ORDER:
        return GamePhase.DISCOVERY
    idx = PHASE_ORDER.index(current)
    if idx >= len(PHASE_ORDER) - 1:
        return None
    return PHASE_ORDER[idx + 1]
