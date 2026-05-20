SERVER_INSTRUCTIONS = """\
Tu es connecté à L'Élite MCP Bank (démo pédagogique promo IA 2026).

Workflow recommandé :
1. Lire la ressource bank://balances (lecture seule, sans effet de bord).
2. Utiliser les outils uniquement pour agir (retrait, transfert, vote de taxation).

Règles :
- Pot commun partagé : 1 000 000 € au départ.
- Retraits du pot commun : entre 0,01 € et 1 000 € par opération.
- Transferts entre élèves : entre 0,01 € et 1 000 €, solde suffisant requis.
- Taxation : 2 votes uniques contre un élève confisquent son solde et le \
redistribuent aux autres.
- Utilise les prénoms exacts listés dans les schémas (enum).
- Ne jamais utiliser un outil pour consulter les soldes : utilise bank://balances.
"""
