# Automatic DOCX review demo

[![Word document review](https://github.com/JSv4/docxodus-action-demo/actions/workflows/publish-previews.yml/badge.svg)](https://github.com/JSv4/docxodus-action-demo/actions/workflows/publish-previews.yml)

A consumer demo of [**JSv4/docx-actions**](https://github.com/JSv4/docx-actions):
**every changed Word document is discovered and rendered automatically**.
There is no file list, glob filter, original/revised pair, or custom preview script
in the workflow.

**[Open the sample PR](https://github.com/JSv4/docxodus-action-demo/pull/1)** ·
**[Read the browser previews](https://jsv4.github.io/docxodus-action-demo/)**

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

One automatic **Word document review** comment lists all documents, revision
counts, browser links, and Word downloads. Expand a document's preview to see
changes with preceding/following context and **Expand in full document** links.
Multi-document previews start collapsed; a single-document PR opens its preview
automatically. The browser viewer includes every changed passage and
Previous/Next navigation. Images are rendered from the actual comparison output.

The complete artifact bundle remains available in Actions, but reading the
redlines does not require downloading a ZIP.

## The complete workflow

[`.github/workflows/publish-previews.yml`](.github/workflows/publish-previews.yml)
is the only workflow:

```yaml
name: Word document review
on:
  pull_request_target:
    types: [opened, synchronize, reopened, closed]
  workflow_dispatch:
permissions:
  contents: read
  actions: read
  pull-requests: write
  pages: write
  id-token: write
jobs:
  review:
    uses: JSv4/docx-actions/.github/workflows/review.yml@3334b4276cd0f21056b8a3217c2c4813a69b2ab2
```

There is deliberately **no `with:` block**. Discovery, Git history, engine setup,
HTML rendering, screenshots, Pages deployment, and comment updates are packaged
in `docx-actions`. GitHub Pages is enabled once with **GitHub Actions** as its
source. No personal token or custom secrets are used.

The workflow reads the PR's Word document blobs in a job with read-only repository
access; it never checks out or executes PR code. The action owns the Pages site
and publishes complete documents there. See its
[installation documentation](https://github.com/JSv4/docx-actions#install-once)
for use in another repository.

## Try any Word document

Edit an existing `.docx` **anywhere in this repository**, commit, and open a pull
request. Every matching changed document gets a comparison against the PR's
merge-base. Added and deleted files get clearly labeled full-document views.
Rename a document and its previous path is retained. Push again to update the
same bot-owned comment.

There is no document-path configuration to update when adding a folder or file.
Manual runs rebuild the preview index from existing artifacts. Previews for open
PRs remain available while their comparison artifacts are retained (90 days).

## Source and reproducibility

[`documents/original.docx`](documents/original.docx) preserves the NVCA download
byte-for-byte. The three review documents on `main` are copies of that baseline.
[`documents/revised.docx`](documents/revised.docx) is the reproducible synthetic
fixture used to construct the sample revisions; these files are source material,
not configured inputs to the GitHub workflow.

[`documents/changes.json`](documents/changes.json) describes the illustrative
negotiation edits. The sample variants apply those edits with corporation names
Aurora Robotics, Harbor Analytics, and Aurora Labs. They retain the template's
other alternatives and placeholders and are software fixtures, not completed
charters.

To check the fixture generator locally:

```bash
python -m pip install -r requirements.txt
python scripts/build_fixture.py --check
```

See [source attribution](documents/SOURCE.md) for the original URL and checksum.
Demo code is MIT licensed; the NVCA template and its derivatives are excluded.
