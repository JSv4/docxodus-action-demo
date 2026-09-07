# Docxodus GitHub Action demo

[![NVCA comparison demo](https://github.com/JSv4/docxodus-action-demo/actions/workflows/demo.yml/badge.svg)](https://github.com/JSv4/docxodus-action-demo/actions/workflows/demo.yml)
[![PR redlines](https://github.com/JSv4/docxodus-action-demo/actions/workflows/redline-pr.yml/badge.svg?event=pull_request)](https://github.com/JSv4/docxodus-action-demo/actions/workflows/redline-pr.yml)

A standalone demonstration of automatic Word document comparison in GitHub
Actions, using the full **October 2025 NVCA Model Certificate of Incorporation**.
The action produces a `.docx` with native Word tracked changes and a
browser-viewable HTML redline.

The reusable action is published at
[`JSv4/Python-Redlines`](https://github.com/JSv4/Python-Redlines/blob/a84be23f0e3d333572a5b5a5d6db2205ae2cb5cf/action.yml).
It runs the **[Docxodus](https://github.com/JSv4/Docxodus) DocxDiff engine**.
This repository contains only the demo documents, workflows, and supporting scripts.

## See it work

**[Open the browser demo](https://jsv4.github.io/docxodus-action-demo/)** — no ZIP
download or local software needed.

1. Open **[the sample pull request](https://github.com/JSv4/docxodus-action-demo/pull/1)**.
   It replaces one binary Word file in `contracts/` with a revised version.
2. Read the **Word redline preview** comment directly in the PR. It includes
   formatted excerpts with preceding and following text, plus an expandable list of changed passages with
   underlined insertions and struck deletions.
3. Click **View full redline in your browser** for the complete HTML document,
   with **Previous**, **Next**, and a passage selector to navigate changes.
   Click **Expand in full document** beneath an excerpt (or the excerpt itself)
   to jump straight to that change. Context previews show the last few lines before
   an edit and the first few lines after it, with the changed paragraph in between.

The preview comment updates after each successful comparison. Images and links
identify the source run and commit. Use **Download Word** in the browser viewer
to get the tracked-changes DOCX directly, then choose **Review → All Markup** in Word
to accept and reject revisions.

For a comparison you can rerun at any time, open
**[NVCA comparison demo](https://github.com/JSv4/docxodus-action-demo/actions/workflows/demo.yml)**
and select **Run workflow** on `main`. Its **nvca-comparison-demo** artifact includes
both inputs, the redline DOCX, HTML preview, edit manifest, and verification report.
The generated files are under `documents/` inside that bundle.

The full artifact bundle remains available as an optional download. GitHub requires
sign-in for artifacts and retains them for up to 90 days. The current Pages deployment
remains available independently; subsequent publications rebuild from the latest
available successful runs.

GitHub does not embed arbitrary styled HTML in PR comments. This demo uses images
and restricted HTML for the inline review, and GitHub Pages for the complete
formatted document. The images are excerpts of the actual redline, not mockups.

## What changes

The original is a substantial legal template: **234 body paragraphs, 95 footnotes,
numbered provisions, cross-reference fields, bookmarks, and multiple sections**.
It is preserved byte-for-byte in [`documents/original.docx`](documents/original.docx).

[`documents/revised.docx`](documents/revised.docx) contains reproducible,
illustrative edits:

| Example | What to look for |
| --- | --- |
| Fill the corporation name | “Aurora Robotics, Inc.” in the title and recitals |
| Set capitalization | 15 million total shares; 10 million common and 5 million preferred |
| Set liquidation preference | Placeholder replaced with “1.5 times” |
| Change a deadline | 30 days → 45 days in Exhibit A |
| Insert a provision | “Demo delivery requirement” after Notices |
| Delete a paragraph | Advancement of Expenses of Employees and Agents |
| Move a provision | Insurance moved to the beginning of Exhibit A's provisions |
| Change paragraph formatting | 18 pt spacing before the Exhibit A subtitle |
| Edit a footnote | An added demonstration note in footnote 2 |
| Insert a table | A four-row terms snapshot at the end |

The pinned engine reports **45 revisions** for these fixtures. Revision counts
are engine-level groupings, not a count of edited words or raw XML elements.
The workflow checks actual insertion, deletion, move, paragraph-format, and
footnote markup, verifies the table is present, and requires an HTML preview.
It does not require a fixed revision count, so a later engine upgrade can be
evaluated without an arbitrary count-based failure.

See [`documents/changes.json`](documents/changes.json) for the complete edit
manifest and [`documents/SOURCE.md`](documents/SOURCE.md) for the source URL,
checksum, and attribution. The synthetic derivative retains the template's
other alternatives and placeholders; it is a software fixture, not a completed charter.

## Two action modes

[`demo.yml`](.github/workflows/demo.yml) compares an explicit original/revised pair
on pushes to `main` and on manual runs:

```yaml
- uses: JSv4/Python-Redlines@a84be23f0e3d333572a5b5a5d6db2205ae2cb5cf
  env:
    PIP_CONSTRAINT: ${{ github.workspace }}/constraints.txt
  with:
    original: documents/original.docx
    modified: documents/revised.docx
    engine: docxodus
    package-version: '==1.0.0'
    docx2html-version: '12.1.0'
    detect-moves: 'true'
    html-preview: 'true'
```

[`redline-pr.yml`](.github/workflows/redline-pr.yml) automatically discovers changed
Word documents and compares the PR merge-base to its head:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0
- uses: JSv4/Python-Redlines@a84be23f0e3d333572a5b5a5d6db2205ae2cb5cf
  env:
    PIP_CONSTRAINT: ${{ github.workspace }}/constraints.txt
  with:
    files: 'contracts/**/*.docx'
    engine: docxodus
    package-version: '==1.0.0'
    docx2html-version: '12.1.0'
    detect-moves: 'true'
    html-preview: 'true'
```

The action revision, Python wrapper, companion engine wheel, and HTML tool are
pinned; [`constraints.txt`](constraints.txt) fixes the action's engine dependency.
Both comparison workflows use `contents: read` and need no custom secrets or
external document service.

[`publish-previews.yml`](.github/workflows/publish-previews.yml) runs after a
successful comparison. It reads the latest demo and open-PR artifacts, renders
excerpts with Chromium, deploys the complete site to GitHub Pages, then updates
one bot-owned comment per PR. It uses `pages: write`, `id-token: write`, and
`pull-requests: write` through the built-in `GITHUB_TOKEN`.

Publishing code is checked out from `main`; it never executes code from a PR
artifact. This demo publishes same-repository PRs only. Pages must be enabled
with **GitHub Actions** as its source in the repository's Pages settings.

## Try your own edit

Create a branch from `main`, edit
[`contracts/certificate-of-incorporation.docx`](contracts/certificate-of-incorporation.docx)
in Word or LibreOffice, save it at the same path, commit, and open a pull request.
The PR workflow generates a new comparison automatically when you push more edits;
the publishing workflow then refreshes its inline and browser previews.
The sample PR is intentionally left open so its comparison is easy to inspect.

Added/deleted files appear in the action summary but cannot produce a two-sided
redline. Modify an existing file to demonstrate differencing. Keeping full Git
history with `fetch-depth: 0` lets the action resolve the actual PR merge-base.

## Reproduce locally

Use Python 3.12 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/build_fixture.py --check
python scripts/compare_local.py
```

The comparison engine ships in a prebuilt wheel; Word and the .NET SDK are not
needed for local DOCX comparison. To also render HTML, install the .NET 10 SDK
and the preview tool, then rerun the comparison:

```bash
dotnet tool install --tool-path .tools Docx2Html --version 12.1.0
export PATH="$PWD/.tools:$PATH"
python scripts/compare_local.py
python scripts/verify_results.py --demo \
  --docx redlines/documents/revised.redline.docx \
  --html redlines/documents/revised.redline.html
```

To change the scripted fixture, edit `scripts/build_fixture.py`, run it without
`--check`, and commit `documents/revised.docx` and `documents/changes.json` together.
The generator edits individual XML text runs to retain fields, footnote references,
and formatting, and preserves all package-part payloads except the body and footnotes.

Demo code is MIT licensed. The NVCA document and its derivatives are excluded;
see [source attribution](documents/SOURCE.md).
