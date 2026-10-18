"""Render every candidate in families/*.py, master it, check it and write it out.

    python3 tools/audio/build.py                  # everything
    python3 tools/audio/build.py cards combat     # only these family modules
    python3 tools/audio/build.py --event hit      # only one event's candidates

Writes, under tools/audio/out/ (ignored by git):
    <event>/<id>.wav     the file the phone would play (effects and jingles: mono 16-bit)
    <event>/<id>.m4a     music only: the phone's file (AAC)
    <event>/<id>.mp3     the picker page's preview
    <event>/<id>.png     a spectrogram, to look at the sound
    manifests/<family>.json   each family's candidates with their stats and any problems
                         (one file per family, so families can be built at the same time)

A problem (too long, too short, clipped, silent, a click at the start or end, a music
loop whose seam jumps) is printed and recorded; ``--strict`` makes it fail.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import synth as A  # noqa: E402
from catalog import EVENT_BY_ID, Candidate  # noqa: E402

OUT = os.path.join(HERE, "out")


def family_modules(names):
    fam_dir = os.path.join(HERE, "families")
    sys.path.insert(0, fam_dir)
    found = sorted(f[:-3] for f in os.listdir(fam_dir) if f.endswith(".py") and not f.startswith("_"))
    for name in (names or found):
        yield name, importlib.import_module(name)


PHONE_HZ = 350.0     # roughly where a phone speaker stops
PHONE_REF = -1.5     # the info clips' usual loudness through it, against full band (dB)
PHONE_K = 0.6        # how much of a clip's difference from that is made up


def phone_offset(x: np.ndarray) -> float:
    """How much quieter ``x`` is through a phone-speaker high-pass than full band (dB)."""
    return A._rms_db(A.highpass(x, PHONE_HZ)) - A._rms_db(x)


def check(c: Candidate, x: np.ndarray) -> list:
    ev = EVENT_BY_ID[c.event]
    st = A.stats(x)
    problems = []
    if st["seconds"] > ev.max_seconds + 1e-6:
        problems.append("longer than %.2fs (%.2fs)" % (ev.max_seconds, st["seconds"]))
    if st["seconds"] < ev.min_seconds:
        problems.append("shorter than %.2fs" % ev.min_seconds)
    if st["clipped"]:
        problems.append("clipped samples: %d" % st["clipped"])
    if st["peak_db"] < -40:
        problems.append("nearly silent")
    if abs(st["dc"]) > 0.01:
        problems.append("DC offset %.3f" % st["dc"])
    if ev.kind != "music":
        if st["end_db"] > -40:
            problems.append("ends abruptly (last samples at %.1f dB)" % st["end_db"])
        if x.ndim != 1:
            problems.append("effects and jingles are mono")
    else:
        if x.ndim != 2:
            problems.append("music is stereo")
        if c.loop_seconds and abs(st["seconds"] - c.loop_seconds) > 0.01:
            problems.append("loop length %.3fs, expected %.3fs" % (st["seconds"], c.loop_seconds))
        # the seam: the jump from the last sample back to the first should be like any
        # other step in the track
        steps = np.abs(np.diff(x, axis=0)).max(axis=1)
        seam = float(np.max(np.abs(x[0] - x[-1])))
        if seam > max(0.05, 4 * float(np.percentile(steps, 99.9))):
            problems.append("loop seam jumps by %.3f" % seam)
    return problems


def build(c: Candidate) -> dict:
    ev = EVENT_BY_ID[c.event]
    t0 = time.time()
    raw = c.render()
    if ev.kind == "music":
        x = A.master(raw, ev.loudness_db, -1.0, fade_out=0.0)
    else:
        x = A.master(A.trim(raw, -70.0, 0.01), ev.loudness_db, -1.0, fade_out=0.008)
        if ev.group == "Info pop-ups":
            # a phone speaker hardly plays below ~350 Hz, so a clip low in register sounds
            # up to 5 dB quieter there than a bright one at the same loudness: lift or ease
            # each clip part of the way toward the family's usual balance
            shift = PHONE_K * (PHONE_REF - phone_offset(x))
            x = A.master(A.trim(raw, -70.0, 0.01), ev.loudness_db + shift, -1.0, fade_out=0.008)
    d = os.path.join(OUT, c.event)
    base = os.path.join(d, c.id)
    if ev.kind == "music":
        A.write_m4a(base + ".m4a", x, 96)
        A.write_mp3(base + ".mp3", x, 96)
    else:
        A.write_wav(base + ".wav", x)
        A.write_mp3(base + ".mp3", x, 128)
    A.spectrogram_png(base + ".png", x)
    st = A.stats(x)
    return {"event": c.event, "id": c.id, "name": c.name, "note": c.note, "tags": list(c.tags),
            "kind": ev.kind, "group": ev.group, "stats": st, "problems": check(c, x),
            "loop_seconds": c.loop_seconds, "bpm": c.bpm, "render_seconds": round(time.time() - t0, 2)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("families", nargs="*")
    p.add_argument("--event")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    os.makedirs(os.path.join(OUT, "manifests"), exist_ok=True)
    bad = 0
    seen = set()
    total = 0
    for name, mod in family_modules(args.families):
        man_path = os.path.join(OUT, "manifests", name + ".json")
        manifest = json.load(open(man_path)) if (args.event and os.path.exists(man_path)) else {}
        for c in getattr(mod, "CANDIDATES", []):
            if c.event not in EVENT_BY_ID:
                print("!! %s: unknown event %r" % (name, c.event))
                bad += 1
                continue
            if args.event and c.event != args.event:
                continue
            if c.key() in seen:
                print("!! duplicate candidate %s" % c.key())
                bad += 1
                continue
            seen.add(c.key())
            try:
                rec = build(c)
            except Exception:
                print("!! %s failed:\n%s" % (c.key(), traceback.format_exc()))
                bad += 1
                continue
            rec["family"] = name
            manifest[c.key()] = rec
            flag = "  " if not rec["problems"] else "!!"
            print("%s %-28s %5.2fs peak %6.1f loud %6.1f %s" % (
                flag, c.key(), rec["stats"]["seconds"], rec["stats"]["peak_db"], rec["stats"]["loudness_db"],
                "; ".join(rec["problems"])))
            bad += bool(rec["problems"])
        with open(man_path, "w") as f:
            json.dump(manifest, f, indent=1, sort_keys=True)
        total += len(manifest)
    print("%d candidates built; %d with problems" % (total, bad))
    return 1 if (bad and args.strict) else 0


def load_manifests() -> dict:
    """Every family's manifest, merged (for the picker page)."""
    d = os.path.join(OUT, "manifests")
    merged = {}
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith(".json"):
            merged.update(json.load(open(os.path.join(d, f))))
    return merged


if __name__ == "__main__":
    sys.exit(main())
