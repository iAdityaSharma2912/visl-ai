import os
import requests

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}


def extract_username(github_url: str) -> str:
    if not github_url:
        return ""
    return github_url.rstrip("/").split("/")[-1].replace("@", "")


def analyze_github(github_url: str) -> dict:
    username = extract_username(github_url)
    if not username:
        return {"github_score": 0, "details": "No GitHub URL provided"}

    try:
        user_resp = requests.get(
            f"https://api.github.com/users/{username}", headers=HEADERS, timeout=15
        )
        if user_resp.status_code != 200:
            return {"github_score": 0, "details": f"GitHub user not found ({user_resp.status_code})"}
        user_data = user_resp.json()

        repos_resp = requests.get(
            f"https://api.github.com/users/{username}/repos?sort=updated&per_page=20",
            headers=HEADERS, timeout=15
        )
        repos = repos_resp.json()
        if not isinstance(repos, list):
            return {"github_score": 0, "details": "Could not fetch repos"}

        original_repos = [r for r in repos if not r.get("fork")]
        total_stars = sum(r.get("stargazers_count", 0) for r in repos)
        languages = set(r.get("language") for r in repos if r.get("language"))

        top_repos = []
        for r in sorted(original_repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:5]:
            top_repos.append({
                "name": r.get("name"),
                "stars": r.get("stargazers_count", 0),
                "forks": r.get("forks_count", 0),
                "language": r.get("language"),
                "description": r.get("description"),
                "updated_at": r.get("pushed_at"),
            })

        # Explainable scoring formula (transparent, capped at 100)
        repo_count_score = min(len(original_repos) * 5, 30)   # up to 30 pts
        star_score = min(total_stars * 2, 25)                  # up to 25 pts
        language_diversity_score = min(len(languages) * 5, 20) # up to 20 pts
        activity_score = 15 if len(repos) > 0 and any(r.get("pushed_at") for r in repos) else 0  # 15 pts
        profile_completeness_score = 10 if user_data.get("bio") or user_data.get("blog") else 0  # 10 pts

        score = round(
            repo_count_score + star_score + language_diversity_score
            + activity_score + profile_completeness_score, 2
        )

        return {
            "github_score": score,
            "score_breakdown": {
                "repo_count_score": repo_count_score,
                "star_score": star_score,
                "language_diversity_score": language_diversity_score,
                "activity_score": activity_score,
                "profile_completeness_score": profile_completeness_score,
            },
            "public_repos": user_data.get("public_repos"),
            "followers": user_data.get("followers"),
            "languages": list(languages),
            "top_repos": top_repos,
            "total_stars": total_stars,
        }
    except Exception as e:
        return {"github_score": 0, "details": str(e)}
