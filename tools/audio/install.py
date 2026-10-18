"""Install the owner's picks from the sound picker page into the game.

    python3 tools/audio/install.py <picks.json>

``picks.json`` is the picker page's saved document ("picks/current"): {"effects": {event:
candidate id}, "music": {slot: candidate id}}. Each picked effect or jingle is copied from
tools/audio/out/<event>/<id>.wav (build.py first) to app/sounds/effects/<event>.wav, each
picked track from tools/audio/out/music/<id>.m4a to app/sounds/music/<slot>.m4a. An event
or slot left unpicked (or picked as "none") has no file, so the game is silent there.
The info pop-ups' clips the owner has not picked yet get a default (``defaults``: the
first candidate its family lists, the Whistle jig for the Jester cards), so every card has
its tune. Their clips are low-passed at 7.5 kHz, so they are installed at 22.05 kHz (half
the size, nothing lost). app/sounds/PICKS.json records what was installed.
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from catalog import EVENT_BY_ID, EVENTS  # noqa: E402
import synth as A  # noqa: E402

OUT = os.path.join(HERE, "out")
SOUNDS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "app", "sounds")
SLOTS = ("menu", "jack", "queen", "king")


def defaults() -> dict:
    """The default clip of every info pop-up event: the first candidate its family lists
    (the Whistle jig where there is one)."""
    fam_dir = os.path.join(HERE, "families")
    sys.path.insert(0, fam_dir)
    found: dict = {}
    for f in sorted(os.listdir(fam_dir)):
        if f.startswith("tunes_") and f.endswith(".py"):
            for c in getattr(importlib.import_module(f[:-3]), "CANDIDATES", []):
                found.setdefault(c.event, [])
                found[c.event].append(c.id)
    out = {}
    for ev in EVENTS:
        ids = found.get(ev.id) or []
        if ev.group == "Info pop-ups" and ids:
            out[ev.id] = "whistle_jig" if "whistle_jig" in ids else ids[0]
    return out


def _copy_info(src: str, dst: str) -> None:
    """An info clip at half the rate (its content stops at 7.5 kHz)."""
    from scipy import signal
    from scipy.io import wavfile
    sr, x = wavfile.read(src)
    y = signal.resample_poly(x.astype(np.float64) / 32768.0, 1, 2)
    A.write_wav(dst, y, sr // 2)


def install(picks: dict, sounds: str = SOUNDS, use_defaults: bool = True) -> dict:
    """Copy the picked files into ``sounds``; returns what was installed."""
    effects = dict((k, v) for k, v in (picks.get("effects") or {}).items() if v)
    defaulted = []
    if use_defaults:
        for event, cid in defaults().items():
            if event not in (picks.get("effects") or {}):
                effects[event] = cid
                defaulted.append(event)
    music = dict((k, v) for k, v in (picks.get("music") or {}).items() if v and k in SLOTS)
    eff_dir, mus_dir = os.path.join(sounds, "effects"), os.path.join(sounds, "music")
    os.makedirs(eff_dir, exist_ok=True)
    os.makedirs(mus_dir, exist_ok=True)
    missing = []
    for event, cid in sorted(effects.items()):
        if event not in EVENT_BY_ID or EVENT_BY_ID[event].kind == "music":
            missing.append("%s: not an effect" % event)
            continue
        src = os.path.join(OUT, event, cid + ".wav")
        if not os.path.exists(src):
            missing.append("%s/%s: not built" % (event, cid))
            continue
        if EVENT_BY_ID[event].group == "Info pop-ups":
            _copy_info(src, os.path.join(eff_dir, event + ".wav"))
        else:
            shutil.copyfile(src, os.path.join(eff_dir, event + ".wav"))
    for slot, cid in sorted(music.items()):
        src = os.path.join(OUT, "music", cid + ".m4a")
        if not os.path.exists(src):
            missing.append("music/%s: not built" % cid)
            continue
        shutil.copyfile(src, os.path.join(mus_dir, slot + ".m4a"))
    # what is not picked any more goes
    for name in os.listdir(eff_dir):
        if name.endswith(".wav") and name[:-4] not in effects:
            os.remove(os.path.join(eff_dir, name))
    for name in os.listdir(mus_dir):
        if name.endswith(".m4a") and name[:-4] not in music:
            os.remove(os.path.join(mus_dir, name))
    record = {"effects": effects, "music": music, "defaults": sorted(defaulted)}
    with open(os.path.join(sounds, "PICKS.json"), "w") as f:
        json.dump(record, f, indent=1, sort_keys=True)
    if missing:
        raise SystemExit("not installed:\n  " + "\n  ".join(missing))
    return record


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    picks = json.load(open(argv[0]))
    picks = picks.get("data", picks)          # the db document as the Artifact tool returns it
    record = install(picks)
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(SOUNDS) for f in fs)
    print("%d effects (%d by default), %d tracks installed (%.1f MB) -> %s" % (
        len(record["effects"]), len(record["defaults"]), len(record["music"]), size / 1e6, SOUNDS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
