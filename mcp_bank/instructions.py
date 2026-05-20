SERVER_INSTRUCTIONS = """\
Tu es connecté à L'Élite MCP Bank (démo pédagogique promo IA 2026).

Workflow recommandé :
1. Consulter les soldes avec l'outil get_balances (ou la ressource bank://balances).
2. Utiliser les autres outils pour agir (retrait, transfert, vote de taxation).

Règles :
- Pot commun partagé : 1 000 000 € au départ.
- Retraits du pot commun : entre 0,01 € et 1 000 € par opération.
- Transferts entre élèves : entre 0,01 € et 1 000 €, solde suffisant requis.
- Taxation : 2 votes uniques contre un élève confisquent son solde et le \
redistribuent aux autres.
- Utilise les prénoms exacts listés dans les schémas (enum).
- Pour les soldes : get_balances en priorité (visible dans Claude), ou bank://balances.
"""
