# PersonalRegicide

A personal, phone-first digital replica of **Regicide** (Badgers From Mars) and the
**Regicide Legacy** campaign. Pure-Python engine, text client, and a Pythonista touch
UI for iPhone. Not affiliated with or endorsed by Badgers From Mars; this shares no art
or text with the published games. Buy the real thing: https://badgersfrommars.com

## Layout

    regicide/          pure-Python engine (no dependencies; Python 3.8+ / Pythonista 3.4+)
      cards.py         cards, suits, deck builders
      rules.py         setup table, GameConfig, rule hooks that Legacy missions override
      engine.py        Game: state, legal actions, play/yield/suffer/jester, save/load
      bots.py          heuristic players (tests, autoplay, hints)
      cli.py           text client for a terminal or the Pythonista console
      campaign/        Legacy campaign framework and missions (Stage 3+)
    app/               Pythonista `ui` client (Stage 2)
    tools/fakeui/      headless stand-in for Pythonista's `ui` so screens can be rendered
                       to PNG and tested on Linux
    tests/             pytest suite (rules, invariants over thousands of bot games)
    docs/              RULES_BASE.md (the spec the engine follows), LEGACY_CAMPAIGN.md
                       (spoilers), PLAN.md is at the root

## Quick start (desktop)

    pip install -r requirements-dev.txt
    python -m pytest
    python -m regicide.cli --players 1            # play solo in the terminal
    python -m regicide.cli --players 3 --bots 2,3 # you plus two bot teammates
    python -m regicide.cli --bot --seed 7         # watch the bot

## On the phone

See PLAN.md ("Getting it onto the phone") and `app/README.md`.
