"""Build the sound picker page from the built candidates (tools/audio/build.py first).

    python3 tools/audio/picker.py <dest dir>

Writes <dest>/index.html and <dest>/a/<event>/<id>.mp3 (the previews), and prints the
list of published paths for the Artifact tool's ``files``. The page plays every candidate,
lets the owner pick one per event (or none) and a track for the menus, the table and the
Kings, and saves the picks to the artifact's db (doc "picks/current") as they are made.
"""
from __future__ import annotations

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from build import OUT, load_manifests  # noqa: E402
from catalog import EVENTS  # noqa: E402

TEMPLATE = os.path.join(HERE, "picker_template.html")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dest = argv[0]
    man = load_manifests()
    events = []
    paths = []
    for ev in EVENTS:
        cands = [r for k, r in sorted(man.items()) if r["event"] == ev.id and not r["problems"]]
        if not cands:
            continue
        items = []
        for r in sorted(cands, key=lambda r: (r.get("family", ""), r["id"])):
            src = os.path.join(OUT, ev.id, r["id"] + ".mp3")
            rel = "a/%s/%s.mp3" % (ev.id, r["id"])
            os.makedirs(os.path.join(dest, "a", ev.id), exist_ok=True)
            shutil.copyfile(src, os.path.join(dest, rel))
            paths.append(rel)
            items.append({"id": r["id"], "name": r["name"], "note": r["note"], "tags": r.get("tags", []),
                          "secs": r["stats"]["seconds"], "src": rel})
        events.append({"id": ev.id, "group": ev.group, "title": ev.title, "when": ev.when, "kind": ev.kind,
                       "items": items})
    data = json.dumps({"events": events}, ensure_ascii=False, separators=(",", ":"))
    page = open(TEMPLATE, encoding="utf-8").read().replace("/*__DATA__*/null", data)
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    with open(os.path.join(dest, "files.json"), "w") as f:
        json.dump([{"path": p} for p in paths], f)
    n = sum(len(e["items"]) for e in events)
    size = sum(os.path.getsize(os.path.join(dest, p)) for p in paths)
    print("%d events, %d candidates, %.1f MB of previews -> %s" % (len(events), n, size / 1e6, dest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
