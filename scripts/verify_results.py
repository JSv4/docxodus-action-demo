"""Check the action's actual artifacts, including native revisions in the NVCA demo."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
REVISION_TYPES = ("ins", "del", "moveFrom", "moveTo", "pPrChange", "rPrChange")


def revision_text(root, kind):
    return " ".join(
        node.text or ""
        for revision in root.findall(f".//w:{kind}", NS)
        for node in revision.iter()
        if node.tag in (f"{{{W}}}t", f"{{{W}}}delText")
    )


def verify(path, preview, demo=False):
    assert path.is_file() and path.stat().st_size > 0, path
    assert preview.is_file() and preview.stat().st_size > 0, preview
    html = preview.read_text(encoding="utf-8-sig")
    assert "<html" in html.lower() and "<body" in html.lower(), "Invalid HTML preview"
    with ZipFile(path) as archive:
        assert archive.testzip() is None, "Corrupt DOCX ZIP member"
        roots = {
            name: ET.fromstring(archive.read(name))
            for name in archive.namelist()
            if name.endswith(".xml")
        }
        body = roots["word/document.xml"]
        counts = Counter()
        for root in roots.values():
            for kind in REVISION_TYPES:
                counts[kind] += len(root.findall(f".//w:{kind}", NS))
        if demo:
            for kind in ("ins", "del", "moveFrom", "moveTo", "pPrChange"):
                assert counts[kind] > 0, f"Missing native {kind} revisions"
            inserted = revision_text(body, "ins")
            deleted = revision_text(body, "del")
            assert "Aurora" in inserted and "45" in inserted, "Missing text replacements"
            assert "30" in deleted, "Missing deleted claims deadline"
            assert "Advancement" in deleted, "Missing deleted paragraph"
            assert "delivery requirement" in inserted, "Missing inserted clause"
            assert "Insurance" in revision_text(body, "moveFrom"), "Missing move source"
            assert "Insurance" in revision_text(body, "moveTo"), "Missing move destination"
            assert body.findall(".//w:tbl", NS), "Missing inserted terms table"
            notes = roots["word/footnotes.xml"]
            assert len(notes.findall("w:footnote", NS)) == 97, "Footnotes were lost"
            assert "intentionally expanded" in revision_text(notes, "ins"), "Missing footnote edit"
            assert "Aurora" in html and "Insurance" in html, "Missing rendered content"
            # The preview must actually render the revision markup.
            assert "<ins" in html and "<del" in html, "HTML lacks visible tracked changes"
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--docx", type=Path)
    parser.add_argument("--html", type=Path)
    args = parser.parse_args()
    reports = []
    if args.docx:
        assert args.html, "Supply --html with --docx"
        reports.append({"redline": str(args.docx), "markup_elements": verify(args.docx, args.html, args.demo)})
    else:
        records = json.loads(os.environ["REDLINES"])
        count = int(os.environ["COUNT"])
        assert count == sum(bool(record["redline"]) for record in records), records
        if args.demo:
            assert count == 1 and len(records) == 1, records
            assert records[0]["revisions"] > 0, records
        for record in records:
            assert not record.get("error"), record
            if not record["redline"]:
                assert record["status"] in ("added", "deleted", "renamed") or record["revisions"] == 0, record
                continue
            assert record["html"], "Every generated redline must have an HTML preview"
            reports.append({**record, "markup_elements": verify(Path(record["redline"]), Path(record["html"]), args.demo)})
    result = json.dumps(reports, indent=2) + "\n"
    print(result)
    if reports:
        output_dir = Path("redlines")
        output_dir.mkdir(exist_ok=True)
        (output_dir / "verification.json").write_text(result)


if __name__ == "__main__":
    main()
