"""
GitHub commit provider for IncidentIQ.
"""

import os

import requests


class GitHubCommitProvider:
    """
    Retrieves recent commits from a GitHub repository.

    The token is read from the environment and is never exposed
    in returned data or logs.
    """

    API_URL = "https://api.github.com"

    def __init__(
        self,
        owner: str | None = None,
        repo: str | None = None,
        token: str | None = None,
    ):
        self.owner = owner or os.getenv("GITHUB_REPO_OWNER", "")
        self.repo = repo or os.getenv("GITHUB_REPO_NAME", "")
        self.token = token or os.getenv("GITHUB_TOKEN", "")

    def get_commits(self, per_page: int = 20):
        if not self.owner or not self.repo:
            raise ValueError(
                "GitHub repository configuration is missing."
            )

        url = (
            f"{self.API_URL}/repos/"
            f"{self.owner}/{self.repo}/commits"
        )

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        response = requests.get(
            url,
            headers=headers,
            params={"per_page": per_page},
            timeout=10,
        )

        response.raise_for_status()

        commits = response.json()

        return [
            {
                "sha": commit.get("sha"),
                "message": (
                    commit.get("commit", {})
                    .get("message", "")
                    .splitlines()[0]
                ),
                "author": (
                    commit.get("commit", {})
                    .get("author", {})
                    .get("name")
                ),
                "timestamp": (
                    commit.get("commit", {})
                    .get("author", {})
                    .get("date")
                ),
                "url": commit.get("html_url"),
            }
            for commit in commits
        ]