#!/usr/bin/env python3
"""Refresh the GitHub profile graphic from public GitHub and LeetCode data."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
TEMPLATE = ASSETS / "overview-template.svg"
README = ROOT / "README.md"
STATS_JSON = ROOT / "docs" / "stats.json"
GITHUB_USER = "aarushsharmawork"
LEETCODE_USER = "Aarush_Sharma_Work"
SVG_NS = "http://www.w3.org/2000/svg"


def get_json(url: str, data: dict | None = None) -> dict:
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": "aarush-profile-updater/1.0",
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if body else {}),
        },
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Could not load public stats from {url}: {last_error}")


def leetcode_stats() -> dict[str, int]:
    try:
        data = get_json(f"https://leetcode-api-faisalshohag.vercel.app/{LEETCODE_USER}")
        values = {
            "total": int(data["totalSolved"]),
            "easy": int(data["easySolved"]),
            "medium": int(data["mediumSolved"]),
            "hard": int(data["hardSolved"]),
        }
    except (KeyError, TypeError, ValueError, RuntimeError):
        data = get_json(
            "https://leetcode.com/graphql/",
            {
                "query": "query userStats($username: String!) { matchedUser(username: $username) { submitStatsGlobal { acSubmissionNum { difficulty count } } } }",
                "variables": {"username": LEETCODE_USER},
            },
        )
        rows = data["data"]["matchedUser"]["submitStatsGlobal"]["acSubmissionNum"]
        counts = {item["difficulty"].lower(): int(item["count"]) for item in rows}
        values = {key: counts[key] for key in ("easy", "medium", "hard")}
        values["total"] = counts["all"]
    if min(values.values()) < 0 or sum(values[key] for key in ("easy", "medium", "hard")) != values["total"]:
        raise ValueError("LeetCode returned inconsistent solved counts")
    return values


def set_text(root: ET.Element, element_id: str, value: str | int) -> None:
    element = root.find(f".//*[@id='{element_id}']")
    if element is None:
        raise ValueError(f"Missing SVG element: {element_id}")
    element.text = str(value)


def set_arc(root: ET.Element, element_id: str, count: int, total: int, offset: float) -> None:
    element = root.find(f".//*[@id='{element_id}']")
    if element is None:
        raise ValueError(f"Missing SVG element: {element_id}")
    circumference = 2 * 3.141592653589793 * 72
    length = circumference * count / max(total, 1)
    element.set("stroke-dasharray", f"{length:.2f} {circumference:.2f}")
    element.set("stroke-dashoffset", f"{-offset:.2f}")


def main() -> None:
    github = get_json(f"https://api.github.com/users/{GITHUB_USER}")
    github_counts = {key: int(github[key]) for key in ("public_repos", "followers", "public_gists")}
    leetcode = leetcode_stats()

    ET.register_namespace("", SVG_NS)
    tree = ET.parse(TEMPLATE)
    root = tree.getroot()
    for element_id, value in (
        ("github-repos", github_counts["public_repos"]),
        ("github-followers", github_counts["followers"]),
        ("github-gists", github_counts["public_gists"]),
        ("leetcode-total", leetcode["total"]),
        ("leetcode-easy", leetcode["easy"]),
        ("leetcode-medium", leetcode["medium"]),
        ("leetcode-hard", leetcode["hard"]),
    ):
        set_text(root, element_id, value)
    circumference = 2 * 3.141592653589793 * 72
    set_arc(root, "leetcode-easy-ring", leetcode["easy"], leetcode["total"], 0)
    set_arc(root, "leetcode-medium-ring", leetcode["medium"], leetcode["total"], circumference * leetcode["easy"] / max(leetcode["total"], 1))
    today = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y").lstrip("0")
    set_text(root, "snapshot-date", f"Stats updated · {today}")

    svg = ET.tostring(root, encoding="unicode") + "\n"
    digest = hashlib.sha256(svg.encode()).hexdigest()[:12]
    filename = f"overview-live-{digest}.svg"
    output = ASSETS / filename
    output.write_text(svg)

    readme = README.read_text()
    updated = re.sub(r"assets/overview(?:-expanded(?:-v2)?|-live-[a-f0-9]{12})?\.svg", f"assets/{filename}", readme)
    if updated == readme and f"assets/{filename}" not in readme:
        raise ValueError("Could not find the profile graphic in README.md")
    README.write_text(updated)
    STATS_JSON.write_text(
        json.dumps({"updated": today, "github": github_counts, "leetcode": leetcode}, indent=2, sort_keys=True) + "\n"
    )
    for stale in ASSETS.glob("overview-live-*.svg"):
        if stale != output:
            stale.unlink()
    print(f"Updated {filename}: {leetcode['total']} solved; {github_counts['public_repos']} repositories")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
