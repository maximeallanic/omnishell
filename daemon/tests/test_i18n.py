"""Translation catalogues of po/ (domain google-hub): they compile, and keep the placeholders of their msgids."""
import gettext
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PO_DIR = Path(__file__).resolve().parents[2] / "po"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


@unittest.skipUnless(shutil.which("msgfmt"), "msgfmt (gettext) missing")
class CatalogueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def compiled(self, po: Path) -> gettext.GNUTranslations:
        lang = po.stem
        out = Path(self.tmp.name, lang, "LC_MESSAGES")
        out.mkdir(parents=True)
        subprocess.run(["msgfmt", "--check", "-o", str(out / "google-hub.mo"), str(po)],
                       check=True, capture_output=True)
        return gettext.translation("google-hub", localedir=self.tmp.name, languages=[lang])

    def test_catalogues_keep_placeholders(self):
        pos = sorted(PO_DIR.glob("*.po"))
        self.assertTrue(pos, "no catalogue in po/")
        for po in pos:
            for key, msgstr in self.compiled(po)._catalog.items():
                msgid = key[0] if isinstance(key, tuple) else key
                if not msgid:
                    continue  # header
                with self.subTest(po=po.name, msgid=msgid):
                    self.assertEqual(set(PLACEHOLDER.findall(msgstr)), set(PLACEHOLDER.findall(msgid)))

    def test_french_plural_forms(self):
        fr = self.compiled(PO_DIR / "fr.po")
        self.assertEqual(fr.ngettext("{n} task today", "{n} tasks today", 1).format(n=1), "1 tâche aujourd’hui")
        self.assertEqual(fr.ngettext("{n} task today", "{n} tasks today", 0).format(n=0), "0 tâche aujourd’hui")
        self.assertEqual(fr.ngettext("{n} task overdue", "{n} tasks overdue", 2).format(n=2), "2 tâches en retard")
        self.assertEqual(fr.gettext("Ask Gemini: “{query}”").format(query="chat"), "Demander à Gemini : « chat »")


if __name__ == "__main__":
    unittest.main()
