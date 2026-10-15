#!/usr/bin/env python3
"""Build the download for players and the server host:  python3 dev/make_release.py
-> dist/c3resume-<version>.zip  (one folder c3resume-<version>/ with everything except dev/ and the GitHub files).
Runs dev/check.py first and stops if it finds a problem."""
import re
import time
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".github", "dev", "dist", "__pycache__", "data"}
SKIP_FILES = {".gitignore", ".gitattributes"}


def main():
    if subprocess.run([sys.executable, str(ROOT / "dev" / "check.py")]).returncode:
        sys.exit("Not building: fix the problems above first.")
    version = re.search(r'^VERSION = "(.+)"', (ROOT / "installer-linux" / "c3resume.py").read_text(), re.M).group(1)
    top = "c3resume-%s" % version
    out = ROOT / "dist" / (top + ".zip")
    out.parent.mkdir(exist_ok=True)
    files = sorted(p for p in ROOT.rglob("*") if p.is_file()
                   and not (set(p.relative_to(ROOT).parts[:-1]) & SKIP_DIRS) and p.name not in SKIP_FILES)
    with zipfile.ZipFile(str(out), "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            rel = p.relative_to(ROOT).as_posix()
            data = p.read_bytes()
            if p.suffix in (".bat", ".ps1"):                     # Windows files with Windows line ends
                data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            info = zipfile.ZipInfo("%s/%s" % (top, rel), date_time=time.localtime()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            executable = p.suffix in (".sh", ".py")
            info.external_attr = ((0o100755 if executable else 0o100644) << 16)
            z.writestr(info, data)
    print("built %s (%d files, %d KB)" % (out.relative_to(ROOT), len(files), out.stat().st_size // 1024))


if __name__ == "__main__":
    main()
