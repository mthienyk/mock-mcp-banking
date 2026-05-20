from mcp_bank.branding import PRODUCT_NAME
from mcp_bank.game_rules import SPY_COST_EUR
import services

_HOST = services.HOST_NAME

SERVER_INSTRUCTIONS = f"""\
Tu es connecté à {PRODUCT_NAME}, simulateur bancaire MCP pour un atelier Claude Code.

OBJECTIF DE PARTIE : maximiser votre solde personnel (get_leaderboard) avant \
end_game_session. Le pot commun est partagé et fini : le vider trop vite \
réduit les plafonds de retrait pour tout le monde.

OUTILS — LECTURE SEULE (aucun effet sur les soldes) :
- get_balances, bank://balances — votre solde et le pot commun
- get_game_status, bank://game — phase, limites, slots, rareté du pot, \
  pression fiscale (tax_pressure)
- get_leaderboard, bank://leaderboard — classement

OUTILS — MUTATIONS (effets réels, session démarrée requise) :
- unlock_withdrawal_slot puis withdraw_from_common_pot — retrait du pot \
  (1 slot consommé par retrait ; cooldown entre déblocages)
- transfer_to_user — envoi à un autre élève (animateur interdit)
- tax_user — vote pour confisquer 100 % du solde d'une cible et le \
  redistribuer aux autres (2 votes, 3 si cible alliée en phase 2)
- propose_alliance / respond_alliance / get_alliance_intel — pacte \
  (1 alliance max) ; intel gratuite sur le solde allié
- spy_player_balance — solde d'un rival (coût {SPY_COST_EUR:.0f} €, cooldown)

WORKFLOW RECOMMANDÉ (Claude Code) :
1. Plan Mode : stratégie (extracteur / diplomate / analyste) avant mutations.
2. get_game_status — vérifier phase, pot_remaining_pct, tax_pressure.
3. Agir selon la stratégie ; re-consulter get_game_status après chaque phase \
   animateur.

RISQUES GAME DESIGN :
- Leader au classement = cible naturelle de tax_user (voir tax_pressure).
- Farm retrait seul : plafonds baissent si le pot < 70 % / 40 % / 15 %.
- Alliances : protection fiscale partielle en phase 2 (3 votes requis).

AVANT LE DÉPART : mutations bloquées tant que l'animateur n'a pas appelé \
start_game_session.

OUTILS ANIMATEUR ({_HOST} uniquement) : start_game_session, \
advance_game_phase, end_game_session.
"""
