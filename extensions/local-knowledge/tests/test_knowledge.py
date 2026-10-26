from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from knowledge import Knowledge, chunks, extract


class Embeddings:
    def __init__(self):
        self.calls = []
        self.unloads = 0
        self.identity = "test-model-v1"
        self.fail = False

    def digest(self, model):
        return self.identity

    def embed(self, model, texts):
        self.calls.extend(texts)
        if self.fail:
            raise RuntimeError("Embedding service unavailable")
        return [[float("orchard" in text.lower()), float("network" in text.lower())] +
                [0.01] * 766 for text in texts]

    def unload(self, model):
        self.unloads += 1


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "notes"
        self.root.mkdir()
        self.embedder = Embeddings()
        self.config = {"roots": [str(self.root)], "database": str(self.base / "state/index.sqlite3")}
        self.knowledge = Knowledge(self.config, self.embedder)

    def test_semantic_ranking_citations_and_cached_query(self):
        (self.root / "garden.md").write_text("Orchard trees need water.\nHarvest starts in July.\n")
        (self.root / "computers.md").write_text("Network cable connects the computers.")
        self.assertEqual(self.knowledge.refresh()["indexed"], 2)
        result = self.knowledge.search("orchard", limit=1)
        self.assertEqual(Path(result["results"][0]["source"]).name, "garden.md")
        self.assertEqual(result["results"][0]["start_line"], 1)
        self.assertEqual(result["results"][0]["end_line"], 2)
        self.assertTrue(result["results"][0]["text"].startswith("L1: Orchard"))
        self.assertTrue(result["results"][0]["citation"].endswith(":1-2"))
        self.assertIn("Harvest", result["results"][0]["text"])
        calls = len(self.embedder.calls)
        self.assertTrue(self.knowledge.search("orchard")["query_cached"])
        self.assertEqual(len(self.embedder.calls), calls)

    def test_incremental_refresh_skips_unchanged_and_removes_deleted(self):
        path = self.root / "note.txt"
        path.write_text("Orchard")
        self.knowledge.refresh()
        calls = len(self.embedder.calls)
        unloads = self.embedder.unloads
        self.assertEqual(self.knowledge.refresh()["unchanged"], 1)
        self.assertEqual(len(self.embedder.calls), calls)
        self.assertEqual(self.embedder.unloads, unloads)
        path.unlink()
        self.assertEqual(self.knowledge.refresh()["removed"], 1)
        self.assertEqual(self.knowledge.status()["chunks"], 0)

    def test_changed_file_is_not_returned_until_refreshed(self):
        path = self.root / "note.md"
        path.write_text("Old orchard instructions")
        self.knowledge.refresh()
        path.write_text("New network instructions")
        self.assertEqual(self.knowledge.search("orchard")["results"], [])
        self.knowledge.refresh()
        self.assertIn("New network", self.knowledge.search("network")["results"][0]["text"])

    def test_scope_hidden_files_and_symlinks(self):
        (self.root / "good.md").write_text("Orchard")
        (self.root / ".secret.md").write_text("secret")
        outside = self.base / "private.md"
        outside.write_text("private network")
        (self.root / "linked.md").symlink_to(outside)
        (self.root / "linked-dir").symlink_to(self.base, target_is_directory=True)
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules/hidden.md").write_text("private")
        self.assertEqual(self.knowledge.refresh()["indexed"], 1)
        self.knowledge.roots = [self.base / "different"]
        self.assertEqual(self.knowledge.search("orchard")["results"], [])

    def test_embedding_errors_unload_and_do_not_replace_valid_rows(self):
        path = self.root / "note.md"
        path.write_text("Orchard")
        self.knowledge.refresh()
        self.embedder.fail = True
        before = self.embedder.unloads
        with self.assertRaises(RuntimeError):
            self.knowledge.search("network")
        self.assertEqual(self.embedder.unloads, before + 1)
        path.write_text("New network")
        self.assertEqual(len(self.knowledge.refresh()["skipped"]), 1)
        self.assertEqual(self.knowledge.search("network")["results"], [])

    def test_embedding_model_change_requires_rebuild(self):
        (self.root / "note.md").write_text("Orchard")
        self.knowledge.refresh()
        self.embedder.identity = "test-model-v2"
        with self.assertRaisesRegex(ValueError, "rebuild"):
            self.knowledge.search("orchard")
        self.assertEqual(self.knowledge.refresh()["indexed"], 1)
        self.assertFalse(self.knowledge.search("orchard")["query_cached"])

    def test_chunk_bounds_unicode_overlap_and_lines(self):
        text = ("Résumé 日本語 🌲\n" * 200)
        pieces = list(chunks(text))
        self.assertGreater(len(pieces), 2)
        for first, last, value in pieces:
            self.assertLessEqual(len(value.encode("utf-8")), 1400)
            self.assertLessEqual(first, last)
        for a, b in zip(pieces, pieces[1:]):
            self.assertTrue(any(a[2].encode().endswith(b[2].encode()[:n]) for n in range(197, 201)))

    def test_bounds_fail_before_loading_model(self):
        with self.assertRaises(ValueError):
            self.knowledge.search("x" * 1401)
        with self.assertRaises(ValueError):
            self.knowledge.search("query", 7)
        (self.root / "a.txt").write_text("Orchard")
        (self.root / "b.txt").write_text("Network")
        with patch("knowledge.MAX_FILES", 1):
            with self.assertRaises(ValueError):
                self.knowledge.refresh()
        self.assertEqual(self.embedder.calls, [])

    def test_docx_paragraphs_and_empty_pdf_are_handled(self):
        path = self.root / "brief.docx"
        with zipfile.ZipFile(path, "w") as document:
            document.writestr("word/document.xml", '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Orchard project</w:t></w:r></w:p><w:p><w:r><w:t>Harvest in July</w:t></w:r></w:p></w:body></w:document>''')
        self.assertEqual(extract(path), "Orchard project\nHarvest in July")
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(self.root / "scan.pdf")
        report = self.knowledge.refresh()
        self.assertEqual(report["indexed"], 1)
        self.assertIn("OCR", report["skipped"][0]["reason"])

    def test_file_and_chunk_limits_do_not_silently_truncate(self):
        (self.root / "large.txt").write_text("x" * 100)
        with patch("knowledge.MAX_FILE_BYTES", 50):
            self.assertEqual(self.knowledge.refresh()["indexed"], 0)
        with patch("knowledge.MAX_CHUNKS", 0):
            report = self.knowledge.refresh()
            self.assertIn("Index limit", report["skipped"][0]["reason"])
        self.assertEqual(self.embedder.calls, [])


if __name__ == "__main__":
    unittest.main()
