"""
GitHub Integration (official REST API)
Authenticates with a Personal Access Token stored in config.json credentials
block (`github_token`, `github_username`). No browser automation is used.

Capabilities: get_user, list_repos, create_repo, create_issue, list_issues,
create_branch, list_commits, create_pr, list_pull_requests, search_repos.
"""

import json
import requests
from typing import Dict, Any, List, Optional
from urllib.parse import quote

from app.integrations.credentials import get_setting, is_configured, missing_for

API = "https://api.github.com"


def _headers() -> Dict[str, str]:
    token = get_setting("github_token")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _gh(method: str, url: str, **kwargs) -> Dict[str, Any]:
    try:
        resp = requests.request(method, url, headers=_headers(), timeout=20, **kwargs)
        if resp.status_code in (200, 201, 204):
            data = resp.json() if resp.content else {}
            return {"success": True, "status_code": resp.status_code, "data": data}
        return {"success": False, "status_code": resp.status_code, "error": resp.text[:300]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _require() -> Dict[str, Any]:
    if not is_configured("github_token"):
        _, hint = missing_for("github_token")
        return {"success": False, "error": "GitHub API requires a personal access token.", "hint": hint}
    return {"success": True}


def _login() -> str:
    return get_setting("github_username") or "octocat"


def get_user(username: str = None) -> Dict[str, Any]:
    target = username or _login()
    res = _gh("GET", f"{API}/users/{quote(target)}")
    if not res.get("success"):
        return res
    d = res["data"]
    return {"success": True, "username": d.get("login"), "name": d.get("name"), "public_repos": d.get("public_repos"),
            "followers": d.get("followers"), "bio": d.get("bio"), "url": d.get("html_url"),
            "output": f"{d.get('login')} has {d.get('public_repos')} public repos."}


def list_repos(username: str = None, sort: str = "updated") -> Dict[str, Any]:
    """Lists repositories for the authenticated (or given) user."""
    target = username or _login()
    res = _gh("GET", f"{API}/users/{quote(target)}/repos", params={"sort": sort, "per_page": 30})
    if not res.get("success"):
        return res
    repos = [{"name": r.get("name"), "full_name": r.get("full_name"), "description": r.get("description"),
              "language": r.get("language"), "stars": r.get("stargazers_count"), "url": r.get("html_url"),
              "private": r.get("private")} for r in res["data"]]
    return {"success": True, "username": target, "repos": repos, "count": len(repos),
            "output": f"Found {len(repos)} repositories for {target}."}


def search_repos(query: str, limit: int = 5) -> Dict[str, Any]:
    if not query:
        return {"success": False, "error": "No search query provided."}
    res = _gh("GET", f"{API}/search/repositories", params={"q": query, "per_page": limit})
    if not res.get("success"):
        return res
    items = [{"name": r.get("full_name"), "description": r.get("description"), "stars": r.get("stargazers_count"),
              "language": r.get("language"), "url": r.get("html_url")} for r in res["data"].get("items", [])]
    return {"success": True, "query": query, "repos": items, "count": len(items), "output": f"Found {len(items)} repos for '{query}'."}


def get_repository(repo: str) -> Dict[str, Any]:
    """Fetches a repo, resolving the org/owner automatically if only a short name is given."""
    if "/" not in repo:
        repo = f"{_login()}/{repo}"
    res = _gh("GET", f"{API}/repos/{repo}")
    if not res.get("success"):
        return res
    d = res["data"]
    return {"success": True, "full_name": d.get("full_name"), "description": d.get("description"),
            "default_branch": d.get("default_branch"), "stars": d.get("stargazers_count"),
            "forks": d.get("forks_count"), "url": d.get("html_url"),
            "output": f"{d.get('full_name')}: {d.get('description') or 'no description'}."}


def create_repo(name: str, description: str = "", private: bool = False, auto_init: bool = True) -> Dict[str, Any]:
    """Creates a repository under the authenticated account."""
    if not name:
        return {"success": False, "error": "Repository name is required."}
    req = _require()
    if not req.get("success"):
        return req
    res = _gh("POST", f"{API}/user/repos", json={"name": name, "description": description,
                                                 "private": private, "auto_init": auto_init})
    if not res.get("success"):
        return res
    d = res["data"]
    return {"success": True, "full_name": d.get("full_name"), "url": d.get("html_url"),
            "output": f"Created repository '{d.get('full_name')}'."}


def create_issue(repo: str, title: str, body: str = "", labels: List[str] = None) -> Dict[str, Any]:
    if "/" not in repo:
        repo = f"{_login()}/{repo}"
    if not title:
        return {"success": False, "error": "Issue title is required."}
    req = _require()
    if not req.get("success"):
        return req
    res = _gh("POST", f"{API}/repos/{repo}/issues", json={"title": title, "body": body, "labels": labels or []})
    if not res.get("success"):
        return res
    d = res["data"]
    return {"success": True, "url": d.get("html_url"), "number": d.get("number"),
            "output": f"Created issue #{d.get('number')}: {title}."}


def list_issues(repo: str, state: str = "open", limit: int = 20) -> Dict[str, Any]:
    if "/" not in repo:
        repo = f"{_login()}/{repo}"
    res = _gh("GET", f"{API}/repos/{repo}/issues", params={"state": state, "per_page": limit})
    if not res.get("success"):
        return res
    issues = [{"number": i.get("number"), "title": i.get("title"), "state": i.get("state"),
               "user": i.get("user", {}).get("login"), "url": i.get("html_url")} for i in res["data"]]
    return {"success": True, "repo": repo, "issues": issues, "count": len(issues),
            "output": f"Found {len(issues)} {state} issue(s) in {repo}."}


def get_issue(repo: str, number: int) -> Dict[str, Any]:
    if "/" not in repo:
        repo = f"{_login()}/{repo}"
    res = _gh("GET", f"{API}/repos/{repo}/issues/{number}")
    if not res.get("success"):
        return res
    d = res["data"]
    return {"success": True, "title": d.get("title"), "body": d.get("body"), "state": d.get("state"),
            "user": d.get("user", {}).get("login"), "comments": d.get("comments"),
            "output": f"#{d.get('number')} {d.get('title')} ({d.get('state')})."}


def create_branch(repo: str, branch: str, from_branch: str = None) -> Dict[str, Any]:
    """
    Creates a branch from the repo's default branch (or a given base branch)
    using the Git Data API reference mechanics.
    """
    if "/" not in repo:
        repo = f"{_login()}/{repo}"
    req = _require()
    if not req.get("success"):
        return req
    repo_info = get_repository(repo)
    if not repo_info.get("success"):
        return repo_info
    base = from_branch or repo_info["default_branch"]
    ref_res = _gh("GET", f"{API}/repos/{repo}/git/ref/heads/{base}")
    if not ref_res.get("success"):
        return ref_res
    sha = ref_res["data"]["object"].get("sha")
    res = _gh("POST", f"{API}/repos/{repo}/git/refs",
              json={"ref": f"refs/heads/{branch}", "sha": sha})
    if not res.get("success"):
        return res
    return {"success": True, "repo": repo, "branch": branch, "sha": sha,
            "output": f"Created branch '{branch}' (from {base}) in {repo}."}


def list_branches(repo: str, limit: int = 20) -> Dict[str, Any]:
    if "/" not in repo:
        repo = f"{_login()}/{repo}"
    res = _gh("GET", f"{API}/repos/{repo}/branches", params={"per_page": limit})
    if not res.get("success"):
        return res
    branches = [{"name": b.get("name"), "sha": b.get("commit", {}).get("sha")} for b in res["data"]]
    return {"success": True, "repo": repo, "branches": branches, "count": len(branches),
            "output": f"Found {len(branches)} branch(es) in {repo}."}


def list_commits(repo: str, branch: str = None, limit: int = 20) -> Dict[str, Any]:
    if "/" not in repo:
        repo = f"{_login()}/{repo}"
    params = {"per_page": limit}
    if branch:
        params["sha"] = branch
    res = _gh("GET", f"{API}/repos/{repo}/commits", params=params)
    if not res.get("success"):
        return res
    commits = [{"sha": c.get("sha", "")[:10], "message": c.get("commit", {}).get("message", "").splitlines()[0],
                "author": c.get("commit", {}).get("author", {}).get("name"), "date": c.get("commit", {}).get("author", {}).get("date")}
               for c in res["data"]]
    return {"success": True, "repo": repo, "commits": commits, "count": len(commits),
            "output": f"Found {len(commits)} commit(s) in {repo}."}


def create_pr(repo: str, title: str, head: str, base: str = None, body: str = "") -> Dict[str, Any]:
    """
    Creates a pull request. get_repository resolves base to the default branch
    when not supplied.
    """
    if "/" not in repo:
        repo = f"{_login()}/{repo}"
    req = _require()
    if not req.get("success"):
        return req
    if not base:
        info = get_repository(repo)
        if not info.get("success"):
            return info
        base = info["default_branch"]
    res = _gh("POST", f"{API}/repos/{repo}/pulls", json={"title": title, "head": head, "base": base, "body": body})
    if not res.get("success"):
        return res
    d = res["data"]
    return {"success": True, "url": d.get("html_url"), "number": d.get("number"),
            "output": f"Created PR #{d.get('number')}: {title} (from {head} into {base})."}


def list_pull_requests(repo: str, state: str = "open", limit: int = 20) -> Dict[str, Any]:
    if "/" not in repo:
        repo = f"{_login()}/{repo}"
    res = _gh("GET", f"{API}/repos/{repo}/pulls", params={"state": state, "per_page": limit})
    if not res.get("success"):
        return res
    prs = [{"number": p.get("number"), "title": p.get("title"), "state": p.get("state"),
            "user": p.get("user", {}).get("login"), "url": p.get("html_url")} for p in res["data"]]
    return {"success": True, "repo": repo, "pull_requests": prs, "count": len(prs),
            "output": f"Found {len(prs)} {state} PR(s) in {repo}."}