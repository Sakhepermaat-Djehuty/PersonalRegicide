# Running on the phone (Pythonista 3)

1. In Pythonista, create a new empty script, paste the contents of `app/bootstrap.py`
   into it and run it. It downloads this repository and installs it at
   `~/Documents/PersonalRegicide`.
2. Open `PersonalRegicide/app/main.py` and run it. The game presents fullscreen; use
   the in-game Quit button to leave.
3. Updating: run the bootstrap script again. Saves and settings are in
   `~/Documents/PersonalRegicide-saves`, which the installer never touches.

Home-screen icon: in Pythonista's script menu use "Shortcuts" → "Home Screen" for
`app/main.py` (or add a Shortcuts-app action that runs the script).

Requirements: Pythonista 3.4 or newer (Python 3.10). Only the `ui` and `console`
modules are used.

## Desktop preview

The same code runs headlessly with the stand-in in `tools/fakeui`:

    python tools/render_screens.py        # writes PNGs of every screen to tools/out/
    python -m pytest tests/test_app.py    # drives the UI through a game
