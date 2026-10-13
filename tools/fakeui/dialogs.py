"""Fake ``dialogs`` module (unused by the app, kept for completeness)."""


def alert(title, message="", button1="OK", button2=None, button3=None, hide_cancel_button=False):
    return 1


def list_dialog(title="", items=(), multiple=False):
    return items[0] if items else None
