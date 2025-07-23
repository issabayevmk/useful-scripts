import requests
import base64
import re

GITHUB_API = "https://api.github.com"
ORG = "your-org-name"  # replace with GitHub org or username
TOKEN = "ghp_..."  # replace with your GitHub PAT
ARTIFACTORY_ALLOWED = "private.artifactory" # replace with your artifact storage

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def list_repositories(org):
    url = f"{GITHUB_API}/users/{org}/repos"
    repos = []
    page = 1
    while True:
        resp = requests.get(url, headers=HEADERS, params={"per_page": 100, "page": page})
        if resp.status_code != 200:
            raise Exception(f"Failed to fetch repos: {resp.text}")
        data = resp.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return [repo["name"] for repo in repos]

def find_dockerfiles(owner, repo):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return []
    data = resp.json()
    return [item['path'] for item in data.get("tree", []) if 'Dockerfile' in item['path']]

def get_file_content(owner, repo, path):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return None
    content = resp.json().get("content", "")
    return base64.b64decode(content).decode("utf-8")

def scan_dockerfile(content, repo, path):
    issues = []
    lines = content.splitlines()

    for line in lines:
        if line.strip().startswith("FROM"):
            match = re.match(r"FROM\s+(.+)", line.strip(), re.IGNORECASE)
            if match:
                image = match.group(1)
                if image.startswith("${ARTIFACTORY}") or "ARTIFACTORY" in image:
                    if ARTIFACTORY_ALLOWED not in image:
                        issues.append(f"❌ {repo}/{path}: Invalid ARTIFACTORY usage in FROM: {image}")
        if re.match(r"^\s*USER\s+root", line):
            issues.append(f"❌ {repo}/{path}: Using root user")
    
    if not any("USER" in line for line in lines):
        issues.append(f"⚠️ {repo}/{path}: No USER directive found")

    return issues

def main():
    all_alerts = []
    repos = list_repositories(ORG)
    for repo in repos:
        print(f"🔍 Scanning repo: {repo}")
        dockerfiles = find_dockerfiles(ORG, repo)
        for path in dockerfiles:
            content = get_file_content(ORG, repo, path)
            if content:
                alerts = scan_dockerfile(content, repo, path)
                all_alerts.extend(alerts)

    print("\n--- Alerts ---")
    if all_alerts:
        for alert in all_alerts:
            print(alert)
    else:
        print("✅ No issues found")

if __name__ == "__main__":
    main()
