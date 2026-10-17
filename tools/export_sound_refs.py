"""Run in Pythonista: copy the built-in sounds the owner picked as references into
Documents/sound_refs and zip them (Documents/sound_refs.zip), with any credits or licence
file in the app that names their maker, so they can be shared back for study. The game does
not use them: they are models for our own sounds.

Share the zip from Pythonista's file browser (long-press it, Share) and attach it in the chat.
"""
import os
import shutil
import sys

WANTED = {
    "cardplace1": "card select",
    "cardplace4": "card deselect",
    "cardshuffle": "draw (less shuffle, more single cards)",
    "cardfan1": "shuffle (a bit less speedy)",
    "cardtakeoutpackage2": "discard (wanted: a few cards put on a stack)",
    "switch21": "button (or something deeper)",
}
AUDIO = (".caf", ".wav", ".mp3", ".m4a", ".aif", ".aiff", ".ogg")
TEXT = (".txt", ".md", ".html", ".htm", ".rtf", ".plist", "")


def roots():
    out = [os.path.dirname(sys.executable)]
    try:
        import sound
        out.append(os.path.dirname(os.path.dirname(os.path.abspath(sound.__file__))))
    except Exception:
        pass
    return [r for i, r in enumerate(out) if r and r not in out[:i]]


def main():
    dest = os.path.expanduser("~/Documents/sound_refs")
    os.makedirs(dest, exist_ok=True)
    found, credits, seen = {}, [], 0
    for root in roots():
        for d, _, files in os.walk(root):
            for f in files:
                base, ext = os.path.splitext(f)
                ext = ext.lower()
                if ext in AUDIO:
                    seen += 1
                    if base.lower() in WANTED and base.lower() not in found:
                        found[base.lower()] = os.path.join(d, f)
                low = f.lower()
                if ext in TEXT and any(k in low for k in ("licen", "credit", "acknowledg", "readme")):
                    p = os.path.join(d, f)
                    try:
                        if os.path.getsize(p) < 2000000 and "kenney" in open(p, errors="ignore").read().lower():
                            credits.append(p)
                    except Exception:
                        pass
    for key, path in found.items():
        shutil.copy(path, os.path.join(dest, os.path.basename(path)))
    for i, path in enumerate(credits[:5]):
        shutil.copy(path, os.path.join(dest, "credits_%d_%s" % (i, os.path.basename(path))))
    zip_path = shutil.make_archive(dest, "zip", dest)
    print("Searched %d sound files." % seen)
    for key, what in WANTED.items():
        print(("found   " if key in found else "MISSING ") + key + "  (" + what + ")")
    print("Credits files naming Kenney: %d" % len(credits))
    print("Wrote", zip_path)
    if len(found) < len(WANTED):
        print("Some were not found: send the zip anyway, with the names above.")


if __name__ == "__main__":
    main()
