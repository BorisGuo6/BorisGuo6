#!/usr/bin/env python3
"""Generate stable GitHub profile cards from the GitHub API."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


API_ROOT = "https://api.github.com"
GRAPHQL_URL = f"{API_ROOT}/graphql"
CARD_WIDTH = 495
CARD_HEIGHT = 195

LANGUAGE_COLORS = {
    "C": "#555555",
    "C#": "#178600",
    "C++": "#f34b7d",
    "CSS": "#563d7c",
    "Cuda": "#3A4E3A",
    "Go": "#00ADD8",
    "HTML": "#e34c26",
    "Java": "#b07219",
    "JavaScript": "#f1e05a",
    "Jupyter Notebook": "#DA5B0B",
    "Lua": "#000080",
    "MATLAB": "#e16737",
    "Makefile": "#427819",
    "Nix": "#7e7eff",
    "Objective-C": "#438eff",
    "PHP": "#4F5D95",
    "Python": "#3572A5",
    "R": "#198CE7",
    "Rust": "#dea584",
    "SCSS": "#c6538c",
    "Shell": "#89e051",
    "Swift": "#F05138",
    "TeX": "#3D6117",
    "TypeScript": "#3178c6",
    "Vue": "#41b883",
}

FALLBACK_COLORS = (
    "#4895EF",
    "#4CC9F0",
    "#4361EE",
    "#7209B7",
    "#F72585",
    "#52B788",
    "#FFB703",
    "#FB8500",
)


@dataclass(frozen=True)
class ProfileStats:
    stars: int
    contributions: int
    public_repositories: int
    followers: int


@dataclass(frozen=True)
class ContributionActivity:
    total: int
    followers: int
    commits: int
    pull_requests: int
    issues: int
    reviews: int


def api_request(
    url: str,
    token: str,
    *,
    payload: dict[str, Any] | None = None,
) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "BorisGuo6-profile-card-generator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, headers=headers, data=data)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed ({error.code}): {detail}") from error


def fetch_repositories(username: str, token: str) -> list[dict[str, Any]]:
    repositories: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = api_request(
            f"{API_ROOT}/users/{username}/repos"
            f"?type=owner&sort=updated&per_page=100&page={page}",
            token,
        )
        if not isinstance(batch, list):
            raise RuntimeError("GitHub repositories response was not a list")
        repositories.extend(batch)
        if len(batch) < 100:
            return repositories
        page += 1


def fetch_contribution_stats(username: str, token: str) -> ContributionActivity:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=364)
    query = """
      query ProfileContributions($login: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $login) {
          followers { totalCount }
          contributionsCollection(from: $from, to: $to) {
            contributionCalendar { totalContributions }
            totalCommitContributions
            totalPullRequestContributions
            totalIssueContributions
            totalPullRequestReviewContributions
          }
        }
      }
    """
    response = api_request(
        GRAPHQL_URL,
        token,
        payload={
            "query": query,
            "variables": {
                "login": username,
                "from": start.isoformat(),
                "to": now.isoformat(),
            },
        },
    )
    if response.get("errors"):
        raise RuntimeError(f"GitHub GraphQL request failed: {response['errors']}")
    user = response.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user not found: {username}")
    contributions = user["contributionsCollection"]
    return ContributionActivity(
        total=int(contributions["contributionCalendar"]["totalContributions"]),
        followers=int(user["followers"]["totalCount"]),
        commits=int(contributions["totalCommitContributions"]),
        pull_requests=int(contributions["totalPullRequestContributions"]),
        issues=int(contributions["totalIssueContributions"]),
        reviews=int(contributions["totalPullRequestReviewContributions"]),
    )


def fetch_language_totals(
    repositories: Iterable[dict[str, Any]], token: str
) -> dict[str, int]:
    totals: defaultdict[str, int] = defaultdict(int)
    for repository in repositories:
        if repository.get("fork") or repository.get("disabled"):
            continue
        languages_url = repository.get("languages_url")
        if not languages_url:
            continue
        languages = api_request(languages_url, token)
        if not isinstance(languages, dict):
            raise RuntimeError(f"Languages response was invalid for {repository.get('name')}")
        for language, byte_count in languages.items():
            totals[str(language)] += int(byte_count)
    return dict(totals)


def language_color(language: str) -> str:
    if language in LANGUAGE_COLORS:
        return LANGUAGE_COLORS[language]
    digest = hashlib.sha256(language.encode("utf-8")).digest()
    return FALLBACK_COLORS[digest[0] % len(FALLBACK_COLORS)]


def svg_shell(title: str, body: str, footer: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" role="img" aria-labelledby="title desc">
  <title id="title">{html.escape(title)}</title>
  <desc id="desc">{html.escape(footer)}</desc>
  <style>
    .title {{ fill: #4895EF; font: 600 18px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; }}
    .label {{ fill: #8B949E; font: 400 12px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; }}
    .value {{ fill: #C9D1D9; font: 600 20px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; }}
    .legend {{ fill: #C9D1D9; font: 500 12px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; }}
    .footer {{ fill: #6E7681; font: 400 10px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; }}
  </style>
  <rect x="0.5" y="0.5" width="494" height="194" rx="6" fill="#0D1117" stroke="#30363D"/>
  <text x="24" y="32" class="title">{html.escape(title)}</text>
{body}
  <text x="24" y="178" class="footer">{html.escape(footer)}</text>
</svg>
"""


def render_stats_card(username: str, stats: ProfileStats) -> str:
    metrics = (
        ("Total stars earned", stats.stars, 24, 65),
        ("Contributions (365 days)", stats.contributions, 258, 65),
        ("Public repositories", stats.public_repositories, 24, 120),
        ("Followers", stats.followers, 258, 120),
    )
    rows = []
    for label, value, x, y in metrics:
        rows.append(f'  <text x="{x}" y="{y}" class="label">{html.escape(label)}</text>')
        rows.append(f'  <text x="{x}" y="{y + 26}" class="value">{value:,}</text>')
    return svg_shell(
        f"{username}'s GitHub Stats",
        "\n".join(rows),
        "Generated from GitHub API data; contributions use a rolling 365-day window.",
    )


def render_languages_card(username: str, totals: dict[str, int]) -> str:
    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:8]
    total_bytes = sum(value for _, value in ranked)
    body: list[str] = []

    if not ranked or total_bytes <= 0:
        body.append('  <text x="24" y="95" class="label">No public language data available.</text>')
    else:
        bar_x = 24.0
        bar_width = 447.0
        consumed = 0.0
        for index, (language, byte_count) in enumerate(ranked):
            width = bar_width * byte_count / total_bytes
            if index == len(ranked) - 1:
                width = bar_width - consumed
            body.append(
                f'  <rect x="{bar_x + consumed:.2f}" y="51" width="{max(width, 0):.2f}" '
                f'height="10" fill="{language_color(language)}"/>'
            )
            consumed += width

        for index, (language, byte_count) in enumerate(ranked):
            column = index % 2
            row = index // 2
            x = 24 + column * 234
            y = 86 + row * 20
            percentage = 100 * byte_count / total_bytes
            body.append(
                f'  <circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{language_color(language)}"/>'
            )
            body.append(
                f'  <text x="{x + 16}" y="{y}" class="legend">'
                f'{html.escape(language)} {percentage:.1f}%</text>'
            )

    return svg_shell(
        f"{username}'s Top Languages",
        "\n".join(body),
        "Calculated by byte count across public, non-fork repositories.",
    )


def render_contribution_card(username: str, activity: ContributionActivity) -> str:
    metrics = (
        ("Commits", activity.commits, 24, 65),
        ("Pull requests", activity.pull_requests, 258, 65),
        ("Issues opened", activity.issues, 24, 120),
        ("Code reviews", activity.reviews, 258, 120),
    )
    rows = []
    for label, value, x, y in metrics:
        rows.append(f'  <text x="{x}" y="{y}" class="label">{html.escape(label)}</text>')
        rows.append(f'  <text x="{x}" y="{y + 26}" class="value">{value:,}</text>')
    return svg_shell(
        f"{username}'s Contribution Mix",
        "\n".join(rows),
        "Generated from visible GitHub contribution activity over the last 365 days.",
    )


def write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="BorisGuo6")
    parser.add_argument("--output-dir", type=Path, default=Path("assets/profile"))
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN or GH_TOKEN is required", file=sys.stderr)
        return 2

    repositories = fetch_repositories(args.username, token)
    activity = fetch_contribution_stats(args.username, token)
    language_totals = fetch_language_totals(repositories, token)
    stats = ProfileStats(
        stars=sum(int(repository.get("stargazers_count", 0)) for repository in repositories),
        contributions=activity.total,
        public_repositories=len(repositories),
        followers=activity.followers,
    )

    changed = []
    if write_if_changed(
        args.output_dir / "github-stats.svg", render_stats_card(args.username, stats)
    ):
        changed.append("github-stats.svg")
    if write_if_changed(
        args.output_dir / "top-languages.svg",
        render_languages_card(args.username, language_totals),
    ):
        changed.append("top-languages.svg")
    if write_if_changed(
        args.output_dir / "contribution-mix.svg",
        render_contribution_card(args.username, activity),
    ):
        changed.append("contribution-mix.svg")

    if changed:
        print(f"Updated: {', '.join(changed)}")
    else:
        print("Profile cards are already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
