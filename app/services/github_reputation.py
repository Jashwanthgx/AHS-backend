# backend/github_reputation.py
"""
Builds a persistent candidate reputation profile from GitHub data.
Called once per application submission and cached in DB.
"""
import os
import httpx
from pydantic import BaseModel
from typing import Optional

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
} if GITHUB_TOKEN else {}

class ReputationProfile(BaseModel):
    github_username: str
    total_commits_12mo: int
    public_repos: int
    avg_stars: float
    oss_contributions: int
    skill_confidence: dict          # {"React": 92, "Python": 85, ...}
    consistency_score: int          # 0-100
    reputation_score: int           # 0-100
    badges: list[str]
    raw_languages: dict             # {"JavaScript": 45000, ...}

async def fetch_github_profile(github_url: str) -> Optional[ReputationProfile]:
    """
    Fetches and analyses a GitHub profile. Returns None on any failure
    so the ATS pipeline is never blocked by GitHub being unavailable.
    """
    username = _extract_username(github_url)
    if not username:
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Parallel requests for efficiency
            user_res, repos_res = await _parallel_fetch(client, username)

            if user_res.status_code != 200:
                return None

            user = user_res.json()
            repos = repos_res.json() if repos_res.status_code == 200 else []
            if not isinstance(repos, list):
                repos = []

            # Aggregate language stats across repos
            language_totals: dict[str, int] = {}
            star_counts = []
            for repo in repos[:30]:   # cap to avoid rate limits
                stars = repo.get("stargazers_count", 0)
                star_counts.append(stars)
                lang = repo.get("language")
                if lang:
                    language_totals[lang] = language_totals.get(lang, 0) + (repo.get("size", 100))

            total_bytes = max(sum(language_totals.values()), 1)
            skill_confidence = {
                lang: round((bytes_ / total_bytes) * 100)
                for lang, bytes_ in sorted(language_totals.items(), key=lambda x: -x[1])[:8]
            }

            public_repos = user.get("public_repos", 0)
            avg_stars = round(sum(star_counts) / max(len(star_counts), 1), 1)
            oss_contributions = user.get("public_gists", 0) + len([
                r for r in repos if not r.get("fork") and r.get("stargazers_count", 0) > 5
            ])

            # Heuristic: contribution consistency from public event count
            commits_estimate = min(user.get("public_repos", 0) * 40 + public_repos * 10, 2000)
            consistency = _compute_consistency(repos)
            reputation = _compute_reputation(commits_estimate, avg_stars, oss_contributions, consistency)

            badges = _assign_badges(commits_estimate, oss_contributions, consistency, repos)

            return ReputationProfile(
                github_username=username,
                total_commits_12mo=commits_estimate,
                public_repos=public_repos,
                avg_stars=avg_stars,
                oss_contributions=oss_contributions,
                skill_confidence=skill_confidence,
                consistency_score=consistency,
                reputation_score=reputation,
                badges=badges,
                raw_languages=language_totals,
            )
    except Exception as e:
        print(f"[!] GitHub reputation fetch failed for {username}: {e}")
        return None

async def _parallel_fetch(client, username):
    import asyncio
    return await asyncio.gather(
        client.get(f"https://api.github.com/users/{username}", headers=HEADERS),
        client.get(f"https://api.github.com/users/{username}/repos?per_page=30&sort=updated", headers=HEADERS),
    )

def _extract_username(url: str) -> Optional[str]:
    import re
    match = re.search(r"github\.com/([a-zA-Z0-9_-]+)", url or "")
    return match.group(1) if match else None

def _compute_consistency(repos: list) -> int:
    if not repos:
        return 50
    updated_recently = sum(1 for r in repos if r.get("pushed_at", "") > "2024-01-01")
    ratio = updated_recently / max(len(repos), 1)
    return min(int(ratio * 100 + 20), 100)

def _compute_reputation(commits, avg_stars, oss, consistency) -> int:
    score = 0
    score += min(commits / 20, 40)          # up to 40pts for commits
    score += min(avg_stars * 2, 20)          # up to 20pts for stars
    score += min(oss * 3, 20)                # up to 20pts for OSS
    score += consistency * 0.2               # up to 20pts for consistency
    return max(0, min(100, round(score)))

def _assign_badges(commits, oss, consistency, repos) -> list[str]:
    badges = []
    if commits > 500: badges.append("Consistent committer")
    if oss > 5: badges.append("Open source contributor")
    if consistency > 70: badges.append("Active maintainer")
    gaps = _detect_gaps(repos)
    if not gaps: badges.append("No employment gaps")
    return badges

def _detect_gaps(repos) -> bool:
    """Returns True if there's a >6-month gap in push activity."""
    from datetime import datetime
    dates = sorted([
        datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00"))
        for r in repos if r.get("pushed_at")
    ], reverse=True)
    for i in range(len(dates) - 1):
        if (dates[i] - dates[i+1]).days > 180:
            return True
    return False
