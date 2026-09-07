"""Update one bot-owned preview comment per PR after Pages has deployed."""

import json
import os
from pathlib import Path
import subprocess

from collect_previews import api


def post():
    repo = os.environ["GITHUB_REPOSITORY"]
    previews = json.loads(Path("_preview_comments.json").read_text())
    for preview in previews:
        pr = api(f"repos/{repo}/pulls/{preview['pr']}")
        # Never label a previous commit's output as the current PR comparison.
        if pr["state"] != "open" or pr["head"]["sha"] != preview["sha"]:
            continue
        comments = json.loads(subprocess.check_output([
            "gh", "api", "--paginate", "--slurp",
            f"repos/{repo}/issues/{preview['pr']}/comments?per_page=100"], text=True))
        existing = next((c for page in comments for c in page
                         if c["user"]["login"] == "github-actions[bot]"
                         and c["body"].startswith("<!-- docxodus-inline-preview -->")), None)
        if existing and existing["body"] == preview["body"]:
            continue
        endpoint = f"repos/{repo}/issues/comments/{existing['id']}" if existing else f"repos/{repo}/issues/{preview['pr']}/comments"
        subprocess.run(["gh", "api", endpoint, "--method", "PATCH" if existing else "POST", "--input", "-"],
                       input=json.dumps({"body": preview["body"]}), text=True,
                       stdout=subprocess.DEVNULL, check=True)
        print(f"Updated preview on PR #{preview['pr']}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
            summary.write("## Browser previews\n\n[Open the redline viewer](https://jsv4.github.io/docxodus-action-demo/)\n\n")
            for preview in previews:
                summary.write(preview["body"] + "\n\n")


if __name__ == "__main__":
    post()
