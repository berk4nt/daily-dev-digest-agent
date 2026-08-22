"""Minimal GitHub REST API client using only the Python standard library.

Fetches yesterday's commits, merged pull requests, and new/updated issues
for a single repository. No third-party dependencies so the Lambda deploys
with zero pip installs.
"""

import json
import urllib.error
import urllib.request

GITHUB_API = "https://api.github.com"


def _get(url: str, token: str) -> list | dict:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "daily-dev-digest-agent",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {body}") from exc


def fetch_activity(repo: str, token: str, since_iso: str, until_iso: str) -> dict:
    """Return commits, merged PRs, and issues touched in [since_iso, until_iso)."""
    owner_repo = repo.strip("/")

    commits = _get(
        f"{GITHUB_API}/repos/{owner_repo}/commits?since={since_iso}&until={until_iso}&per_page=100",
        token,
    )

    pulls = _get(
        f"{GITHUB_API}/repos/{owner_repo}/pulls?state=closed&sort=updated&direction=desc&per_page=30",
        token,
    )
    merged_pulls = [
        pr
        for pr in pulls
        if pr.get("merged_at") and since_iso <= pr["merged_at"] < until_iso
    ]

    issues = _get(
        f"{GITHUB_API}/repos/{owner_repo}/issues?since={since_iso}&state=all&per_page=50",
        token,
    )
    real_issues = [issue for issue in issues if "pull_request" not in issue]

    return {
        "commits": [
            {
                "sha": c["sha"][:7],
                "author": (c.get("commit", {}).get("author") or {}).get("name", "unknown"),
                "message": c.get("commit", {}).get("message", "").splitlines()[0],
            }
            for c in commits
        ],
        "merged_pulls": [
            {
                "number": pr["number"],
                "title": pr["title"],
                "author": pr.get("user", {}).get("login", "unknown"),
                "url": pr["html_url"],
            }
            for pr in merged_pulls
        ],
        "issues": [
            {
                "number": issue["number"],
                "title": issue["title"],
                "state": issue["state"],
                "url": issue["html_url"],
            }
            for issue in real_issues
        ],
    }
