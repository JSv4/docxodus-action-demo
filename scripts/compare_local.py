"""Run the same pinned Docxodus engine locally, without GitHub Actions."""

from pathlib import Path
import shutil
import subprocess

from python_redlines import DocxodusEngine

ROOT = Path(__file__).resolve().parents[1]
output = ROOT / "redlines/documents"
output.mkdir(parents=True, exist_ok=True)
redline, stdout, stderr = DocxodusEngine().run_redline(
    "Demo Reviewer",
    (ROOT / "documents/original.docx").read_bytes(),
    (ROOT / "documents/revised.docx").read_bytes(),
    detect_moves=True,
)
target = output / "revised.redline.docx"
target.write_bytes(redline)
print(stdout)
if stderr:
    print(stderr)
print(f"Wrote {target}")
previewer = shutil.which("docx2html")
if previewer:
    subprocess.run([previewer, str(target), str(target.with_suffix(".html")), "--track-changes"], check=True)
else:
    print("Install the optional Docx2Html 12.1.0 tool for an HTML preview; see README.md.")
