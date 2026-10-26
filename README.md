# FPL Helper

A simple Fantasy Premier League helper: load your team, see form and fixtures, and get clear transfer / captain / XI suggestions.

## Run locally

```bash
pip install -r requirements.txt
streamlit run fpl_analyzer/ui/app.py
```

Optional CLI:

```bash
python3 -m fpl_analyzer.main <team_id>
```

Your Team ID is the number in  
`https://fantasy.premierleague.com/entry/<team_id>/`.

## What it does

1. Rebuilds your 15-man squad, bank, and selling prices from the official FPL API  
2. Scores players on form, minutes, availability, and fixtures  
3. Compares hold vs 1 vs 2 transfers under FPL constraints  
4. Suggests captain, vice, starting XI, and bench order  

No login required — public FPL endpoints only.
