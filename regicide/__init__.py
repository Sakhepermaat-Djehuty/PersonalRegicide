"""PersonalRegicide — a pure-Python engine for Regicide and the Regicide Legacy campaign.

The package has no dependencies beyond the standard library so that it runs unchanged
on a Linux CI box (pytest), in a terminal (``python -m regicide.cli``) and inside
Pythonista on an iPhone (``app/main.py``). Everything that touches ``ui`` lives in
``app/``; nothing in this package imports it.
"""

__version__ = "0.1.0"
