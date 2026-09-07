"""Reproduce the edited NVCA fixture without round-tripping unrelated DOCX parts."""

import argparse
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "d75600769c12724990de48149d7a2bb161f3522daa54b1783672f93697d87d29"
SOURCE_URL = "https://nvca.org/wp-content/uploads/2025/10/NVCA-Model-COI-10-1-2025.docx"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def tag(name):
    return f"{{{W}}}{name}"


def text(element):
    return "".join(element.xpath(".//w:t/text()", namespaces=NS))


def paragraph(value, properties=None):
    p = ET.Element(tag("p"))
    if properties is not None:
        p.append(deepcopy(properties))
    run = ET.SubElement(p, tag("r"))
    node = ET.SubElement(run, tag("t"))
    node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    node.text = value
    return p


def replace_once(p, before, after):
    """Replace across Word runs while preserving run styles and field/footnote nodes."""
    full = text(p)
    start = full.index(before)
    end = start + len(before)
    offset = 0
    inserted = False
    for node in p.xpath(".//w:t", namespaces=NS):
        value = node.text or ""
        next_offset = offset + len(value)
        if offset < end and next_offset > start:
            left = max(0, start - offset)
            right = min(len(value), end - offset)
            node.text = value[:left] + (after if not inserted else "") + value[right:]
            node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            inserted = True
        offset = next_offset
    assert text(p) == full[:start] + after + full[end:]


def build():
    source = (ROOT / "documents/original.docx").read_bytes()
    assert sha256(source).hexdigest() == SOURCE_SHA256, "The source fixture changed"
    edits = []
    with ZipFile(BytesIO(source)) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        footnotes = ET.fromstring(archive.read("word/footnotes.xml"))
        body = document.find("w:body", NS)

        def find(prefix):
            matches = [p for p in body.findall("w:p", NS) if text(p).startswith(prefix)]
            assert len(matches) == 1, (prefix, len(matches))
            return matches[0]

        def change(prefix, before, after, label):
            replace_once(find(prefix), before, after)
            edits.append({"kind": "replace", "location": label, "before": before, "after": after})

        change("AMENDED AND RESTATEDCERTIFICATE OF INCORPORATIONOF", "[_________]", "Aurora Robotics, Inc.", "Charter title")
        change("[____________], a corporation", "[____________]", "Aurora Robotics, Inc.", "Introductory recital")
        change("That the name of this corporation", "[_______________]", "Aurora Robotics, Inc.", "Corporate name recital")
        change(":\u00a0The name of this corporation", "[_______________]", "Aurora Robotics, Inc.", "Article First")

        capital = find(":\u00a0The total number of shares")
        for before, after in [
            ("[______]", "15,000,000"), ("[two]", "two"),
            ("[_____]", "10,000,000"), ("$[_____]", "$0.0001"),
            ("[______]", "5,000,000"), ("$[______]", "$0.0001"), ("[all]", "all"),
        ]:
            replace_once(capital, before, after)
            edits.append({"kind": "replace", "location": "Article Fourth — capitalization", "before": before, "after": after})

        change("Preferential Payments to Holders of Preferred Stock.", "[__ times]", "1.5 times", "Non-participating liquidation preference")
        change("Claims by Directors and Officers.", "within 30 days", "within 45 days", "Exhibit A — claims deadline")

        notices = find("Notices. Any notice")
        added = "Demo delivery requirement. The Corporation shall retain an electronic copy of each notice and its delivery confirmation for five years."
        properties = deepcopy(notices.find("w:pPr", NS))
        if properties is not None:
            for num in properties.findall("w:numPr", NS):
                properties.remove(num)
        notices.addnext(paragraph(added, properties))
        edits.append({"kind": "insert", "location": "After Notices", "after": added})

        deleted = find("Advancement of Expenses of Employees and Agents.")
        edits.append({"kind": "delete", "location": "Exhibit A", "before": text(deleted)})
        body.remove(deleted)

        moved = find("Insurance. The Board of Directors")
        find("Right to Indemnification of Directors and Officers.").addprevious(moved)
        edits.append({"kind": "move", "location": "Exhibit A", "text": text(moved), "after": "Before Right to Indemnification of Directors and Officers"})

        heading = find("(Alternative Indemnification Provisions)")
        props = heading.find("w:pPr", NS)
        if props is None:
            props = ET.Element(tag("pPr"))
            heading.insert(0, props)
        spacing = props.find("w:spacing", NS)
        if spacing is None:
            spacing = ET.SubElement(props, tag("spacing"))
        old_spacing = spacing.get(tag("before"))
        assert old_spacing != "360"
        spacing.set(tag("before"), "360")
        edits.append({"kind": "format", "location": "Exhibit A subtitle", "before": old_spacing, "after": "18 pt spacing before"})

        note = footnotes.xpath("w:footnote[@w:id='2']/w:p", namespaces=NS)[-1]
        note_text = " Demo note: this footnote is intentionally expanded to exercise comparison outside the document body."
        note.append(paragraph(note_text).find("w:r", NS))
        edits.append({"kind": "footnote", "location": "Footnote 2", "after": note_text})

        table = ET.Element(tag("tbl"))
        table_props = ET.SubElement(table, tag("tblPr"))
        width = ET.SubElement(table_props, tag("tblW"))
        width.set(tag("w"), "9000")
        width.set(tag("type"), "dxa")
        borders = ET.SubElement(table_props, tag("tblBorders"))
        for side in ["top", "left", "bottom", "right", "insideH", "insideV"]:
            border = ET.SubElement(borders, tag(side))
            for key, value in [("val", "single"), ("sz", "4"), ("color", "808080")]:
                border.set(tag(key), value)
        grid = ET.SubElement(table, tag("tblGrid"))
        for _ in range(2):
            ET.SubElement(grid, tag("gridCol")).set(tag("w"), "4500")
        rows = [("DEMO ONLY — term", "Proposed value"), ("Authorized common shares", "10,000,000"), ("Authorized preferred shares", "5,000,000"), ("Liquidation preference", "1.5 times")]
        for values in rows:
            row = ET.SubElement(table, tag("tr"))
            for value in values:
                cell = ET.SubElement(row, tag("tc"))
                cell_props = ET.SubElement(cell, tag("tcPr"))
                cell_width = ET.SubElement(cell_props, tag("tcW"))
                cell_width.set(tag("w"), "4500")
                cell_width.set(tag("type"), "dxa")
                cell.append(paragraph(value))
        section = body.find("w:sectPr", NS)
        index = body.index(section) if section is not None else len(body)
        body.insert(index, paragraph("DEMONSTRATION ONLY — TERMS SNAPSHOT"))
        body.insert(index + 1, table)
        # Word requires a paragraph after a table at the end of a story.
        body.insert(index + 2, paragraph("Synthetic edits for software testing; the model's other alternatives and placeholders remain."))
        edits.append({"kind": "table", "location": "End of document", "after": rows})

        changed = {
            "word/document.xml": ET.tostring(document, xml_declaration=True, encoding="UTF-8", standalone=True),
            "word/footnotes.xml": ET.tostring(footnotes, xml_declaration=True, encoding="UTF-8", standalone=True),
        }
        output = BytesIO()
        with ZipFile(output, "w") as result:
            for info in archive.infolist():
                # Stored members keep fixture bytes stable across zlib versions.
                entry = deepcopy(info)
                entry.compress_type = ZIP_STORED
                result.writestr(entry, changed.get(info.filename, archive.read(info.filename)))
        revised = output.getvalue()
        with ZipFile(BytesIO(revised)) as check:
            assert check.namelist() == archive.namelist(), "Package parts were added or lost"
            actual_changed = {
                name for name in archive.namelist()
                if archive.read(name) != check.read(name)
            }
            assert actual_changed == set(changed), actual_changed
            for name in check.namelist():
                if name.endswith(".xml"):
                    ET.fromstring(check.read(name))
        original_body = ET.fromstring(archive.read("word/document.xml"))
        for expression in (".//w:footnoteReference/@w:id", ".//w:instrText/text()"):
            assert sorted(original_body.xpath(expression, namespaces=NS)) == sorted(document.xpath(expression, namespaces=NS)), expression
        manifest = {
            "source_url": SOURCE_URL,
            "source_sha256": SOURCE_SHA256,
            "revised_sha256": sha256(revised).hexdigest(),
            "modified_package_parts": list(changed),
            "original_body_paragraphs": len(original_body.findall("w:body/w:p", NS)),
            "positive_id_footnotes": len(footnotes.xpath("w:footnote[number(@w:id) > 0]", namespaces=NS)),
            "edits": edits,
        }
        return revised, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify checked-in fixtures are reproducible")
    args = parser.parse_args()
    revised, manifest = build()
    for path, content in [("documents/revised.docx", revised), ("documents/changes.json", manifest)]:
        target = ROOT / path
        if args.check:
            assert target.read_bytes() == content, f"Regenerate {path}"
        else:
            target.write_bytes(content)
        print(("Verified " if args.check else "Wrote ") + path)


if __name__ == "__main__":
    main()
