"""Fake ``console`` module: alerts return a scripted answer instead of blocking."""
from __future__ import annotations

_answers = []
history = []


def script_answers(*answers):
    """Queue answers (1-based button indices) for upcoming alert() calls."""
    _answers.extend(answers)


def alert(title, message="", button1="OK", button2=None, button3=None, hide_cancel_button=False):
    history.append(("alert", title, message, button1, button2, button3))
    if _answers:
        return _answers.pop(0)
    return 1


def hud_alert(message, icon="success", duration=1.0):
    history.append(("hud", message))


def input_alert(title, message="", input="", ok_button_title="OK", hide_cancel_button=False):
    history.append(("input", title))
    if _answers:
        return _answers.pop(0)
    return input
