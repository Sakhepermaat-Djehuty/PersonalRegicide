"""One-file installer / updater for Pythonista.

Paste this file into a new Pythonista script (any name), run it. It downloads the
repository as a zip from GitHub, unpacks it into ~/Documents/PersonalRegicide and
leaves your saves alone (they live in ~/Documents/PersonalRegicide-saves). Run it again
to update. Works on a desktop too (installs next to the current directory).
"""
import io
import os
import shutil
import sys
import urllib.request
import zipfile

REPO = "Sakhepermaat-Djehuty/PersonalRegicide"
BRANCH = os.environ.get("REGICIDE_BRANCH", "main")
URL = "https://github.com/%s/archive/refs/heads/%s.zip" % (REPO, BRANCH)


def target_dir():
    if sys.platform == "ios" or "Pythonista" in sys.executable:
        return os.path.join(os.path.expanduser("~/Documents"), "PersonalRegicide")
    return os.path.join(os.getcwd(), "PersonalRegicide")


def main():
    dest = target_dir()
    print("Downloading", URL)
    data = urllib.request.urlopen(URL, timeout=60).read()
    zf = zipfile.ZipFile(io.BytesIO(data))
    root = zf.namelist()[0].split("/")[0]
    tmp = dest + ".new"
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    zf.extractall(tmp)
    extracted = os.path.join(tmp, root)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.move(extracted, dest)
    shutil.rmtree(tmp, ignore_errors=True)
    print("Installed to", dest)
    print("Now open and run:", os.path.join(dest, "app", "main.py"))


if __name__ == "__main__":
    main()
