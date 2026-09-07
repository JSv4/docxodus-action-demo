"""Publish formatted redlines and image/Markdown excerpts from the action's HTML."""

import argparse
from copy import deepcopy
from hashlib import sha256
import html
import json
import os
from pathlib import Path
import re
import shutil

from lxml import etree as ET
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
NS = {"h": "http://www.w3.org/1999/xhtml"}
H = "{" + NS["h"] + "}"


def plain(node):
    return " ".join("".join(node.itertext()).split())


def inline(node):
    """A small safe HTML subset that GitHub renders inside a Markdown comment."""
    value = html.escape(node.text or "")
    for child in node:
        value += inline(child) + html.escape(child.tail or "")
    tag = ET.QName(node).localname
    if tag in ("ins", "del") and value.strip():
        return f"<{tag}>{value}</{tag}>"
    if tag == "br":
        return " "
    return value


def prepare_document(source, destination):
    parser = ET.XMLParser(resolve_entities=False, no_network=True)
    root = ET.fromstring(source.read_bytes(), parser)
    for node in list(root.iter()):
        local = ET.QName(node).localname
        if local in ("script", "iframe", "object", "embed", "form", "base", "link") or (local == "meta" and node.get("http-equiv")):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
            continue
        for name, value in list(node.attrib.items()):
            if name.lower().startswith("on") or name in ("srcdoc", "action"):
                del node.attrib[name]
            elif name in ("href", "src") and re.match(r"\s*(javascript|vbscript):", value, re.I):
                del node.attrib[name]
    head = root.find("h:head", NS)
    csp = ET.Element(H + "meta")
    csp.set("http-equiv", "Content-Security-Policy")
    csp.set("content", "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; base-uri 'none'; form-action 'none'")
    head.insert(0, csp)
    style = ET.SubElement(head, H + "style")
    style.text = "html{background:#edf0f2} body{box-sizing:border-box;max-width:816px;margin:24px auto;padding:48px 64px;background:white;box-shadow:0 3px 20px #18232d12} [data-review-change]{scroll-margin:24px} @media(max-width:700px){body{margin:0;padding:24px 20px}}"
    changed = []
    for node in root.xpath("//h:p | //h:h1 | //h:h2 | //h:h3 | //h:tr", namespaces=NS):
        # Table rows have one anchor; avoid listing every cell paragraph again.
        if node.xpath("ancestor::h:tr", namespaces=NS):
            continue
        revisions = node.xpath(".//h:ins | .//h:del | .//*[contains(@class,'rev-')]", namespaces=NS)
        if not revisions and "rev-" not in node.get("class", ""):
            continue
        if not plain(node):
            continue
        number = len(changed) + 1
        identifier = f"review-change-{number}"
        # Add an anchor without replacing any existing bookmark identifier.
        node.set("data-review-change", str(number))
        anchor = ET.Element(H + "a", id=identifier)
        node.insert(0, anchor)
        classes = " ".join(e.get("class", "") for e in node.iter())
        kind = "Moved" if "rev-move-" in classes else "Formatting" if "format-change" in classes else "Text"
        accepted = " ".join("".join(node.xpath(".//text()[not(ancestor::h:del)]", namespaces=NS)).split())
        changed.append({"id": identifier, "number": number, "label": (accepted or plain(node))[:100],
                        "kind": kind, "markup": inline(node), "node": node})
    destination.write_bytes(ET.tostring(root, encoding="UTF-8", method="xml"))
    return changed


def shell(title, content, prefix="./"):
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · Docxodus demo</title><link rel="stylesheet" href="{prefix}assets/preview.css"></head>
<body>{content}</body></html>'''


def neighboring_block(node, direction):
    """Find adjacent document text in the same section or table, skipping blanks."""
    sibling = node.getprevious() if direction == "before" else node.getnext()
    while sibling is not None:
        if isinstance(sibling.tag, str) and plain(sibling):
            return sibling
        sibling = sibling.getprevious() if direction == "before" else sibling.getnext()
    return None


def append_block(parent, node):
    fragment = deepcopy(node)
    if ET.QName(fragment).localname == "tr":
        source_table = node.xpath("ancestor::h:table[1]", namespaces=NS)
        table = ET.SubElement(parent, H + "table", **(dict(source_table[0].attrib) if source_table else {}))
        table.append(fragment)
    else:
        parent.append(fragment)


def contextual_excerpt(document, change, index, total):
    root = ET.parse(str(document)).getroot()
    body = root.find("h:body", NS)
    for child in list(body):
        body.remove(child)
    style = ET.SubElement(root.find("h:head", NS), H + "style")
    style.text = (ROOT / "preview/assets/excerpt.css").read_text()
    card = ET.SubElement(body, H + "section", {"class": "review-excerpt"})
    header = ET.SubElement(card, H + "header", {"class": "excerpt-header"})
    ET.SubElement(header, H + "span").text = f"EXCERPT {index} OF {total}"
    ET.SubElement(header, H + "strong").text = f"Passage {change['number']} · {change['kind']} change"
    before = neighboring_block(change["node"], "before")
    after = neighboring_block(change["node"], "after")
    for label, node in [("Before", before), ("Changed passage", change["node"]), ("After", after)]:
        if node is None:
            continue
        role = "focus" if label == "Changed passage" else label.lower()
        section = ET.SubElement(card, H + "div", {"class": f"excerpt-section excerpt-{role}"})
        ET.SubElement(section, H + "div", {"class": "excerpt-label"}).text = label
        window = ET.SubElement(section, H + "div", {"class": "excerpt-window"})
        append_block(window, node)
    footer = ET.SubElement(card, H + "footer", {"class": "excerpt-footer"})
    ET.SubElement(footer, H + "span", {"class": "excerpt-hint"}).text = "Continue reading with all surrounding text."
    ET.SubElement(footer, H + "span", {"class": "excerpt-expand"}).text = "⤢ Expand in full document ↗"
    return root


def render_images(browser, document, changes, output):
    if not changes:
        return []
    # Prefer a dense text edit and a move to show distinct capabilities.
    ranked = sorted(changes, key=lambda c: len(c["node"].xpath(".//h:ins | .//h:del", namespaces=NS)), reverse=True)
    selected = [next((c for c in ranked if c["kind"] == "Text"), ranked[0])]
    second = next((c for c in changes if c["kind"] == "Moved" and len(c["label"]) > 30), None)
    if second and second != selected[0]:
        selected.append(second)
    images = []
    page = browser.new_page(viewport={"width": 1000, "height": 1000}, device_scale_factor=1.5)
    page.route(re.compile(r"https?://"), lambda route: route.abort())
    for index, change in enumerate(selected, 1):
        # Preserve the neighboring paragraphs and document styling around the edit.
        root = contextual_excerpt(document, change, index, len(selected))
        excerpt = output / f"excerpt-{index}.html"
        excerpt.write_bytes(ET.tostring(root, encoding="UTF-8"))
        page.goto(excerpt.resolve().as_uri())
        page.evaluate("document.fonts.ready")
        page.evaluate("""document.querySelectorAll('.excerpt-before .excerpt-window, .excerpt-after .excerpt-window').forEach(window => {
            window.toggleAttribute('data-clipped', window.firstElementChild.getBoundingClientRect().height > window.clientHeight + 1);
        })""")
        name = f"preview-{index}.png"
        page.locator(".review-excerpt").screenshot(path=str(output / name))
        # GitHub proxies comment images; a content hash prevents stale cached crops.
        fingerprint = sha256((output / name).read_bytes()).hexdigest()[:12]
        hashed_name = f"preview-{index}-{fingerprint}.png"
        (output / name).replace(output / hashed_name)
        name = hashed_name
        excerpt.unlink()
        images.append({"name": name, "anchor": change["id"], "label": change["label"], "kind": change["kind"]})
    page.close()
    return images


def build(catalog_path, output, base_url):
    catalog = json.loads(catalog_path.read_text())
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "preview/assets", output / "assets", dirs_exist_ok=True)
    cards, comments = [], []
    with sync_playwright() as playwright:
        browser_args = {"headless": True}
        if os.environ.get("CHROME_PATH"):
            browser_args["executable_path"] = os.environ["CHROME_PATH"]
        browser = playwright.chromium.launch(**browser_args)
        for item in catalog:
            source = Path(item["input_dir"]).resolve()
            route = item["route"]
            assert re.fullmatch(r"demo|pr/[1-9][0-9]*", route), route
            run_path = f"{route}/run-{int(item['run_id'])}"
            reports_path = source / "verification.json"
            reports = json.loads(reports_path.read_text()) if reports_path.exists() else []
            report_by_name = {Path(r["html"]).name: r for r in reports if r.get("html")}
            comment = ["<!-- docxodus-inline-preview -->", "## Word redline preview", "",
                       f"Compared commit `{item['sha'][:12]}` · [Action run]({item['run_url']})", "",
                       "**Underlined text is inserted; struck text is deleted. Purple marks moved text in the images.**", ""]
            previews = []
            for file_index, source_html in enumerate(sorted(source.rglob("*.redline.html")), 1):
                assert source_html.resolve().is_relative_to(source), "Artifact path escaped its directory"
                docx = source_html.with_suffix(".docx")
                assert docx.resolve().is_relative_to(source) and docx.is_file(), docx
                relative = f"{run_path}/file-{file_index}"
                directory = output / relative
                directory.mkdir(parents=True, exist_ok=True)
                document = directory / "document.html"
                changes = prepare_document(source_html, document)
                shutil.copyfile(docx, directory / "redline.docx")
                images = render_images(browser, document, changes, directory)
                report = report_by_name.get(source_html.name, {})
                count = report.get("revisions")
                count_label = f"{count} revisions" if count is not None else f"{len(changes)} changed passages"
                filename = str(source_html.relative_to(source)).replace(".redline.html", ".docx")
                options = "".join(f'<option value="{c["id"]}">{c["number"]}. {html.escape(c["label"][:80])}</option>' for c in changes)
                prefix = "../" * len(Path(relative).parts)
                context_url = item.get("pr_url") or item["run_url"]
                content = f'''<header class="toolbar"><a class="brand" href="{prefix}index.html">Docxodus <span>/ review</span></a>
<div class="toolbar-actions"><a href="{html.escape(context_url)}">Open in GitHub ↗</a><a class="button small" href="redline.docx" download>Download Word</a></div></header>
<main class="review"><div class="review-title"><div><p class="eyebrow">{html.escape(item['title'])}</p><h1>{html.escape(Path(filename).name)}</h1><p class="muted">{count_label} · {len(changes)} changed passages · commit {item['sha'][:12]}</p></div><div class="legend"><span class="insert">Inserted</span><span class="delete">Deleted</span><span class="move">Moved</span></div></div>
<nav class="change-nav" aria-label="Navigate changes"><button id="previous" aria-label="Previous changed passage">← Previous</button><select id="changes" aria-label="Changed passage">{options}</select><button id="next" aria-label="Next changed passage">Next →</button><span id="position" aria-live="polite"></span></nav>
<iframe id="document" title="Full document with tracked changes" sandbox="allow-same-origin" src="document.html"></iframe></main>
<script src="{prefix}assets/viewer.js"></script>'''
                (directory / "index.html").write_text(shell(filename, content, prefix))
                url = f"{base_url.rstrip('/')}/{relative}/"
                comment.extend([f"### {html.escape(Path(filename).name)}", "", f"**[{count_label} — View full redline in your browser]({url})** · [Download Word]({url}redline.docx)", ""])
                comment.extend([f"Showing {len(images)} excerpts with surrounding text. Expand an excerpt to continue at that passage in the full document; all {len(changes)} changed passages are listed below.", ""])
                for index, image in enumerate(images, 1):
                    comment.extend([f'[![{image["kind"]} change with preceding and following context]({url}{image["name"]})]({url}#{image["anchor"]})', "",
                                    f'**[⤢ Expand excerpt {index} in full document ↗]({url}#{image["anchor"]})**', ""])
                comment.extend(["<details>", f"<summary>Read all {len(changes)} changed passages directly in GitHub</summary>", ""])
                # Bound comment size; every passage remains accessible in the full viewer.
                for change in changes:
                    line = f'**{change["number"]}. {change["kind"]}** · [Open passage]({url}#{change["id"]})\n\n<p>{change["markup"]}</p>\n'
                    if len("\n".join(comment)) + len(line) > 48000:
                        comment.append(f"[Continue in the full redline]({url})")
                        break
                    comment.append(line)
                comment.extend(["", "</details>", ""])
                previews.append({"url": url, "relative": relative, "filename": filename, "count": count_label, "images": images})
            if not previews:
                continue
            first = previews[0]
            cover = f'<img class="card-preview" src="{first["relative"]}/{first["images"][0]["name"]}" alt="A formatted excerpt of the actual document redline" loading="lazy">' if first["images"] else ""
            links = "".join(f'<a class="button" href="{p["relative"]}/">View full redline ↗</a>' for p in previews)
            label = f"Pull request #{item['pr']}" if item["pr"] else "Rerunnable demo"
            cards.append(f'<article class="card"><div class="card-content"><p class="eyebrow">{label}</p><h2>{html.escape(item["title"])}</h2><p class="muted">{first["count"]} · commit {item["sha"][:12]}</p><div class="card-actions">{links}<a href="{html.escape(item.get("pr_url") or item["run_url"])}">Open in GitHub ↗</a></div></div><a href="{first["relative"]}/">{cover}</a></article>')
            if item["pr"] and item["sha"] == item["current_head"]:
                comments.append({"pr": item["pr"], "sha": item["sha"], "body": "\n".join(comment), "run_id": item["run_id"]})
        browser.close()
    content = f'''<header class="toolbar"><a class="brand" href="./">Docxodus <span>/ action demo</span></a><a href="https://github.com/JSv4/docxodus-action-demo">View repository ↗</a></header>
<main class="landing"><div class="hero"><p class="eyebrow">WORD DOCUMENT REVIEW · GITHUB ACTIONS</p><h1>Read the changes.<br>Keep the document.</h1><p class="intro">A full NVCA model charter, compared with Docxodus. Review insertions, deletions, moves, and formatting in your browser.</p><div class="legend"><span class="insert">Inserted</span><span class="delete">Deleted</span><span class="move">Moved</span></div></div><div class="cards">{''.join(cards)}</div><footer>Generated from successful comparison runs. The PR contains inline previews; Word downloads preserve native tracked changes. <a href="https://github.com/JSv4/docxodus-action-demo/blob/main/documents/SOURCE.md">NVCA source and attribution</a>.</footer></main>'''
    (output / "index.html").write_text(shell("Word redline previews", content))
    (output / ".nojekyll").touch()
    Path("_preview_comments.json").write_text(json.dumps(comments, indent=2) + "\n")
    print(f"Built {len(cards)} comparisons and {len(comments)} PR previews in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("_preview_inputs/catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("_site"))
    parser.add_argument("--base-url", default="https://jsv4.github.io/docxodus-action-demo")
    args = parser.parse_args()
    build(args.catalog, args.output, args.base_url)
