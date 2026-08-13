from pathlib import Path

import build_reader_docx as builder
import pytest


class FakeDocument:
    def __init__(self, error=None):
        self.error = error
        self.saved_to = None

    def save(self, path):
        self.saved_to = path
        if self.error:
            raise self.error


class TestSaveDocument:
    def test_permission_error_becomes_friendly_message(self):
        document = FakeDocument(PermissionError("denied"))
        with pytest.raises(RuntimeError, match="open in Word"):
            builder.save_document(document, Path("out.docx"))

    def test_normal_save_passes_through(self):
        document = FakeDocument()
        builder.save_document(document, Path("out.docx"))
        assert document.saved_to == Path("out.docx")
