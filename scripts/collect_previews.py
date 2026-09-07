"""Collect successful comparison artifacts; never check out or run PR code."""

import json
import os
from pathlib import Path
import subprocess


def api(path):
    return json.loads(subprocess.check_output(["gh", "api", path], text=True))


def collect():
    repo = os.environ["GITHUB_REPOSITORY"]
    root = Path("_preview_inputs")
    root.mkdir(exist_ok=True)
    pulls = api(f"repos/{repo}/pulls?state=open&per_page=100")
    demo_runs = api(f"repos/{repo}/actions/workflows/demo.yml/runs?status=success&branch=main&per_page=30")["workflow_runs"]
    pr_runs = api(f"repos/{repo}/actions/workflows/redline-pr.yml/runs?status=success&event=pull_request&per_page=100")["workflow_runs"]
    selections = []
    if demo_runs:
        selections.append(("demo", "NVCA comparison demo", None, demo_runs[0], "nvca-comparison-demo"))
    for pr in pulls:
        if not pr["head"]["repo"] or pr["head"]["repo"]["full_name"].lower() != repo.lower():
            continue
        matches = [run for run in pr_runs if any(p["number"] == pr["number"] for p in run["pull_requests"])]
        if matches:
            selections.append((f"pr/{pr['number']}", pr["title"], pr, matches[0], "nvca-pr-redlines"))
    catalog = []
    for route, title, pr, run, artifact_name in selections:
        artifacts = api(f"repos/{repo}/actions/runs/{run['id']}/artifacts")["artifacts"]
        if not any(a["name"] == artifact_name and not a["expired"] for a in artifacts):
            continue
        destination = root / route
        subprocess.run(["gh", "run", "download", str(run["id"]), "--repo", repo,
                        "--name", artifact_name, "--dir", str(destination)], check=True)
        catalog.append({
            "route": route, "title": title, "run_id": run["id"], "run_url": run["html_url"],
            "sha": run["head_sha"], "pr": pr["number"] if pr else None,
            "pr_url": pr["html_url"] if pr else None,
            "current_head": pr["head"]["sha"] if pr else run["head_sha"],
            "input_dir": str(destination),
        })
    if not catalog:
        raise RuntimeError("No successful comparison artifacts are available to publish")
    (root / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
    print(f"Collected {len(catalog)} comparisons")


if __name__ == "__main__":
    collect()
