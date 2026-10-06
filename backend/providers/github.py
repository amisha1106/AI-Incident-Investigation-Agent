"""
GitHub deployment provider for IncidentIQ.
"""

import os

import requests

from providers.base import DeploymentProvider


class GitHubDeploymentProvider(DeploymentProvider):
    """
    Retrieves deployment history from a GitHub repository.

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

    def get_deployments(self):
        if not self.owner or not self.repo:
            raise ValueError(
                "GitHub repository configuration is missing."
            )

        url = (
            f"{self.API_URL}/repos/"
            f"{self.owner}/{self.repo}/deployments"
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
            params={"per_page": 30},
            timeout=10,
        )

        response.raise_for_status()

        deployments = response.json()

        return [
            {
                "version": deployment.get("sha"),
                "service": deployment.get("environment")
                or deployment.get("original_environment")
                or "unknown",
                "timestamp": deployment.get("created_at"),
                "change_summary": deployment.get("description")
                or "Deployment recorded by GitHub.",
                "rollback_available": False,
                "deployment_id": deployment.get("id"),
                "ref": deployment.get("ref"),
            }
            for deployment in deployments
        ]