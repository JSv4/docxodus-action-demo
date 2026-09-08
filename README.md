# Automatic DOCX review demo

[![Word document review](https://github.com/JSv4/docxodus-action-demo/actions/workflows/publish-previews.yml/badge.svg)](https://github.com/JSv4/docxodus-action-demo/actions/workflows/publish-previews.yml)

A consumer demo of [**JSv4/docx-actions**](https://github.com/JSv4/docx-actions):
**every changed Word document is discovered and rendered automatically**.
There is no file list, glob filter, original/revised pair, or custom preview script
in the workflow.

**[Open the sample PR](https://github.com/JSv4/docxodus-action-demo/pull/1)** ·
**[Open the optional Pages viewer](https://jsv4.github.io/docxodus-action-demo/)**

## See automatic discovery work

The sample PR changes three substantial legal documents:

| Changed document | What it demonstrates |
|---|---|
| `charter.DOCX` | A root-level file with an uppercase extension. |
| `contracts/certificate-of-incorporation.docx` | A nested Word document. |
| `subsidiary/certificate-of-incorporation.docx` | The same filename in a different folder, with its own comparison. |

Each is based on the complete **October 2025 NVCA Model Certificate of
Incorporation**: 234 body paragraphs, 95 footnotes, numbered provisions,
cross-references, bookmarks, and multiple sections. The variants use different
corporation names while demonstrating text edits, moved provisions, formatting,
footnotes, and a newly inserted table.

The default **Word document review** comment lists all documents and revision
counts, with styled screenshot excerpts, surrounding context, and expandable
text redlines and change logs. Click **Enlarge excerpt** for a full-size image.
Download the complete Word/HTML review and change logs from its Actions artifact
link. PNG previews are hosted on the dedicated `docx-previews` branch using the
standard Actions token. This workflow has no Pages or OIDC permissions.

The optional Pages mode adds full-document links
and Previous/Next navigation. Run **Actions → Try review options → Run workflow**
to try `redline`, `latest`, or `both`, choose image hosting, and explicitly enable Pages if desired.
Latest mode renders the current documents without running a comparison. None of
these controls configure which document paths are discovered.

Styled image excerpts, text redlines, and change logs are readable directly in
GitHub. Full document layout is available in the download and, when enabled, in
the Pages viewer.

## The complete workflow

[`.github/workflows/publish-previews.yml`](.github/workflows/publish-previews.yml)
is the automatic workflow:

```yaml
name: Word document review
on:
  pull_request_target:
    types: [opened, synchronize, reopened, closed]
  workflow_dispatch:
permissions:
  contents: write
  actions: read
  pull-requests: write
jobs:
  review:
    uses: JSv4/docx-actions/.github/workflows/review.yml@v2.1.0
    with:
      image-host: branch
```

The demo is pinned to the published `@v2.1.0` release.
The only `with:` setting controls image hosting. **No document paths or comparison
pairs are configured.**
Discovery, Git history, engine setup,
HTML rendering, change logs, comment updates, and optional Pages publication
are packaged in `docx-actions`. No personal token or custom secrets are used.
The separate manual `review-options.yml` exposes presentation controls and grants
Pages permissions for the explicit opt-in. An already-deployed Pages site is
left untouched by default runs.

The image branch is separate from the source history and contains only generated
PNGs and metadata. Image URLs are pinned to commits; previous excerpts remain
in Git history after a PR closes or its Actions artifacts expire. Branch image
hosting is an opt-in feature for public repositories. Other installations can
keep the action's text-only default with `contents: read`.

The workflow reads the PR's Word document blobs in a job with read-only repository
access; it never checks out or executes PR code. When explicitly enabled, the action owns the Pages site and publishes complete
documents there; it checks ownership before replacing existing content. See its
[installation documentation](https://github.com/JSv4/docx-actions#install-once)
for use in another repository.

## Try any Word document

Edit an existing `.docx` **anywhere in this repository**, commit, and open a pull
request. Every matching changed document gets a comparison against the PR's
merge-base. Added and deleted files get clearly labeled full-document views.
Rename a document and its previous path is retained. Push again to update the
same bot-owned comment.

There is no document-path configuration to update when adding a folder or file.
Manual runs of the automatic workflow rebuild comments from existing artifacts.
**Try review options** recomputes the selected PR in the selected mode. Complete
downloadable reviews remain available while their artifacts are retained (90
days). Published comment images remain in the image branch's Git history.

## Source and reproducibility

[`documents/original.docx`](documents/original.docx) preserves the NVCA download
byte-for-byte. The three review documents on `main` are copies of that baseline.
[`documents/revised.docx`](documents/revised.docx) is the reproducible synthetic
fixture used to construct the sample revisions; these files are source material,
not configured inputs to the GitHub workflow.

[`documents/changes.json`](documents/changes.json) describes the illustrative
negotiation edits. The sample variants apply those edits with corporation names
Aurora Robotics, Harbor Analytics, and Aurora Labs. Harbor retains the original
30-day claims deadline; Aurora Labs adds an electronic notice register sentence.
These small variations produce different revision counts. They retain the template's
other alternatives and placeholders and are software fixtures, not completed
charters.

To check the fixture generator locally:

```bash
python -m pip install -r requirements.txt
python scripts/build_fixture.py --check
```

See [source attribution](documents/SOURCE.md) for the original URL and checksum.
Demo code is MIT licensed; the NVCA template and its derivatives are excluded.
