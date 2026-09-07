"""Check the trust boundary between a comparison artifact and published markup."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lxml import etree as ET

from build_preview import prepare_document


class PreviewTests(unittest.TestCase):
    def test_preserves_revisions_and_bookmarks_without_active_content(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "input.html"
            target = Path(directory) / "output.html"
            source.write_text('''<html xmlns="http://www.w3.org/1999/xhtml"><head><style>.rev-ins{color:green}</style></head>
<body><p id="original-bookmark" onclick="alert(1)">Within <del>30</del> <ins>45</ins> days.
<a href="javascript:alert(1)">link</a></p><script>alert(1)</script><iframe src="https://example.com"/>
<p>Unchanged text.</p><p class="rev-para-format-change">Formatted heading</p></body></html>''')
            changes = prepare_document(source, target)
            result = target.read_text()
            self.assertEqual(len(changes), 2)
            self.assertIn('<del>30</del> <ins>45</ins>', changes[0]["markup"])
            self.assertIn('id="original-bookmark"', result)
            self.assertIn('id="review-change-1"', result)
            self.assertIn('Unchanged text.', result)
            self.assertIn('Content-Security-Policy', result)
            self.assertNotIn('onclick', result)
            self.assertNotIn('javascript:', result)
            root = ET.parse(str(target))
            self.assertFalse(root.xpath('//*[local-name()="script" or local-name()="iframe"]'))
            self.assertEqual(changes[1]["kind"], 'Formatting')


if __name__ == "__main__":
    unittest.main()
