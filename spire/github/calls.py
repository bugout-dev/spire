"""
Processing requests to GitHub API.
"""
import json
import logging
from typing import Any, cast, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class GitHubAPIFailed(Exception):
    """
    Raised on actions that involve calls to GitHub API which are failed.
    """


async def get_org_repos(token: str) -> List[Dict[str, Any]]:
    """
    Extract all repositories accessible to the installation.

    GitHub REST API documentation:
    https://docs.github.com/en/free-pro-team@latest/rest/reference/apps#list-repositories-accessible-to-the-app-installation
    """
    # We have to page over all repositories available to the installation.
    per_page = 30
    current_page = 1
    url_template = (
        "https://api.github.com/installation/repositories?per_page={}&page={}"
    )

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }

    repositories: List[Dict[str, Any]] = []
    while True:
        installation_repositories_response: Dict[str, Any] = {}
        url = url_template.format(per_page, current_page)
        try:
            r = requests.get(url, headers=headers, timeout=2)
            r.raise_for_status()
            installation_repositories_response = r.json()
        except Exception as e:
            logger.error(repr(e))
            raise GitHubAPIFailed("Error due extract repositories via GitHub API")

        repositories.extend(installation_repositories_response.get("repositories", []))

        total_repos = cast(int, installation_repositories_response["total_count"])
        if current_page * per_page >= total_repos:
            break
        current_page += 1

    return repositories


async def post_comment(comments_url: str, token: str, message) -> Dict[str, Any]:
    """
    Post comment directly to GitHub Pull Request/Issue web page.
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }
    data = {"body": message}
    data_str = json.dumps(data)

    try:
        r = requests.post(comments_url, data=data_str, headers=headers, timeout=2)
        r.raise_for_status()
        response_body = r.json()
    except Exception as e:
        logger.error(repr(e))
        raise GitHubAPIFailed("Error due posting comment to pr/issue via GitHub API")

    return response_body


async def remove_comment(comment_url: str, token: str) -> None:
    """
    Remove comment directly from GitHub Pull Request/Issue web page.
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }

    try:
        r = requests.delete(comment_url, headers=headers, timeout=2)
        r.raise_for_status()
    except Exception as e:
        logger.error(repr(e))
        raise GitHubAPIFailed(
            "Error due removing previous locust report in comment via GitHub API"
        )


async def create_check_request(
    installation_url: str, repo_name: str, token: str, check_name: str, head_sha: str
) -> Dict[str, Any]:
    """
    Initiate Check after Pull Request was created.
    It contains terminal hash from PR, name, unique github id.
    """
    org_name = installation_url.rstrip("/").split("/")[-1]
    url = f" https://api.github.com/repos/{org_name}/{repo_name}/check-runs"

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }
    data = {
        "name": check_name,
        "head_sha": head_sha,
    }
    data_str = json.dumps(data)

    try:
        r = requests.post(url, data=data_str, headers=headers, timeout=2)
        r.raise_for_status()
        response_body = r.json()

    except Exception as e:
        logger.error(repr(e))
        raise GitHubAPIFailed("Error due creating check requests via GitHub API")

    return response_body


async def update_check_run_request(
    check_id: str,
    repo_name: str,
    org_name: str,
    token: str,
    check_name: str,
    status: str,
    conclusion: str,
    summary: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update GitHub Check status.

    Docs:
    https://docs.github.com/en/free-pro-team@latest/rest/reference/checks#update-a-check-run
    """
    url = f"https://api.github.com/repos/{org_name}/{repo_name}/check-runs/{check_id}"

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }
    data: Dict[str, Any] = {
        "name": check_name,
        "status": status,
        "conclusion": conclusion,
    }

    if summary is not None:
        data["output"] = {"title": check_name, "summary": summary}

    data_str = json.dumps(data)

    try:
        r = requests.patch(url, data=data_str, headers=headers, timeout=2)
        r.raise_for_status()
        response_body = r.json()
    except Exception as e:
        logger.error(repr(e))
        raise GitHubAPIFailed("Error due updating check requests via GitHub API")

    return response_body


def get_pr_commits(
    repo_name: str, org_name: str, token: str, pull_number: int
) -> List[Dict[str, Any]]:
    """
    Return list of commits for Pull Request.

    Docs: https://docs.github.com/en/rest/reference/pulls#list-commits-on-a-pull-request
    """
    url = f"https://api.github.com/repos/{org_name}/{repo_name}/pulls/{pull_number}/commits"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }

    try:
        r = requests.get(url, headers=headers, timeout=2)
        r.raise_for_status()
        response_body = r.json()
    except Exception as e:
        logger.error(repr(e))
        raise GitHubAPIFailed("Error due posting comment to pr/issue via GitHub API")

    return response_body


def get_pr_comments(
    repo_name: str, org_name: str, token: str, pull_number: int
) -> List[Dict[str, Any]]:
    """
    Return list of comments for Pull Request or Issue.

    Docs: https://docs.github.com/en/rest/reference/pulls#list-commits-on-a-pull-request
    """
    url = f"https://api.github.com/repos/{org_name}/{repo_name}/issues/{pull_number}/comments"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }

    try:
        r = requests.get(url, headers=headers, timeout=2)
        r.raise_for_status()
        response_body = r.json()
    except Exception as e:
        logger.error(repr(e))
        raise GitHubAPIFailed("Error due posting comment to pr/issue via GitHub API")

    return response_body


def get_pr_info(
    repo_name: str, org_name: str, token: str, pull_number: int
) -> Dict[str, Any]:
    """
    Return information about Pull Request or Issue.

    Docs: https://docs.github.com/en/rest/reference/pulls#list-commits-on-a-pull-request
    """
    url = f"https://api.github.com/repos/{org_name}/{repo_name}/pulls/{pull_number}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }

    try:
        r = requests.get(url, headers=headers, timeout=2)
        r.raise_for_status()
        response_body = r.json()
    except Exception as e:
        logger.error(repr(e))
        raise GitHubAPIFailed("Error due posting comment to pr/issue via GitHub API")

    return response_body
