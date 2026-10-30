#!/usr/bin/env python3
"""Capture the portfolio's main section for the GitHub profile README."""

from __future__ import annotations

import hashlib
import http.server
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
README = ROOT / "README.md"
DOCS = ROOT / "docs"
MAC_CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def chrome_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    if MAC_CHROME.exists():
        return str(MAC_CHROME)
    raise FileNotFoundError("Chrome or Chromium is required to capture the portfolio")


def main() -> None:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory() as temporary:
            capture = Path(temporary) / "portfolio.png"
            profile = Path(temporary) / "chrome-profile"
            url = f"http://127.0.0.1:{server.server_port}/index.html?profile=1"
            subprocess.run(
                [
                    chrome_path(),
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    "--force-device-scale-factor=2",
                    "--window-size=1050,850",
                    "--virtual-time-budget=5000",
                    f"--user-data-dir={profile}",
                    f"--screenshot={capture}",
                    url,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=45,
            )
            pixels = capture.read_bytes()
    finally:
        server.shutdown()

    digest = hashlib.sha256(pixels).hexdigest()[:12]
    output = ASSETS / f"portfolio-live-{digest}.png"
    output.write_bytes(pixels)
    readme = README.read_text()
    updated, count = re.subn(
        r"assets/(?:overview(?:-expanded(?:-v2)?|-live-[a-f0-9]{12})?\.svg|portfolio-live-[a-f0-9]{12}\.png)",
        f"assets/{output.name}",
        readme,
    )
    if count != 1:
        raise ValueError(f"Expected one profile image reference, found {count}")
    README.write_text(updated)
    for stale in (*ASSETS.glob("portfolio-live-*.png"), *ASSETS.glob("overview-live-*.svg")):
        if stale != output:
            stale.unlink()
    print(f"Captured portfolio as {output.name}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
