#!/usr/bin/env python3
"""Refresh cached public GitHub and LeetCode data for the portfolio."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
STATS_JSON = ROOT / "docs" / "stats.json"
GITHUB_USER = "aarushsharmawork"
LEETCODE_USER = "Aarush_Sharma_Work"


def get_json(url: str, data: dict | None = None) -> dict:
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": "aarush-profile-updater/1.0",
            "Accept": "application/json",
            **({"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"} if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN") else {}),
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
    except (KeyError, TypeError, ValueError, RuntimeError):
        data = get_json(f"https://leetcode-api-faisalshohag.vercel.app/{LEETCODE_USER}")
        values = {
            "total": int(data["totalSolved"]),
            "easy": int(data["easySolved"]),
            "medium": int(data["mediumSolved"]),
            "hard": int(data["hardSolved"]),
        }
    if min(values.values()) < 0 or sum(values[key] for key in ("easy", "medium", "hard")) != values["total"]:
        raise ValueError("LeetCode returned inconsistent solved counts")
    return values


def main() -> None:
    try:
        github = get_json(f"https://api.github.com/users/{GITHUB_USER}")
        github_counts = {key: int(github[key]) for key in ("public_repos", "followers", "public_gists")}
    except (KeyError, TypeError, ValueError, RuntimeError):
        github_counts = json.loads(STATS_JSON.read_text())["github"]
        print("GitHub API unavailable; retaining the last saved GitHub counts")
    leetcode = leetcode_stats()

    today = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y").lstrip("0")
    STATS_JSON.write_text(
        json.dumps({"updated": today, "github": github_counts, "leetcode": leetcode}, indent=2, sort_keys=True) + "\n"
    )
    print(f"Updated stats: {leetcode['total']} solved; {github_counts['public_repos']} repositories")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
