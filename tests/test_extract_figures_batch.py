import hashlib
import json
from pathlib import Path

import extract_figures_batch as batch
import pytest
from PIL import Image


class FakeRender:
    def to_pil(self):
        return Image.new("RGB", (200, 200), "white")


class FakePage:
    def __init__(self):
        self.render_calls = 0

    def render(self, scale=None):
        self.render_calls += 1
        return FakeRender()


def make_options(tmp_path):
    return {
        "scale": 3.0,
        "left": 18.0,
        "right": 18.0,
        "caption_padding": 4.0,
        "top_from_page": None,
        "allow_low_confidence": False,
        "outdir": str(tmp_path),
        "pdf_sha256": "fake-pdf-hash",
    }


def make_fig(label, page=3, output=None):
    return {"label": label, "page": page, "output": output}


def canned_caption(**overrides):
    caption = {
        "caption_bottom": 100.0,
        "caption_top": 60.0,
        "caption_text": "Fig. 3 caption text",
        "caption_line_count": 3,
        "boundary_reason": "large_vertical_gap",
        "boundary_gap": None,
        "next_text_top": 40.0,
        "next_text_preview": "",
        "confidence": "high",
        "warnings": [],
    }
    caption.update(overrides)
    return caption


def canned_report(label, outdir):
    return {
        "label": label,
        "output": str(Path(outdir) / f"{label}.png"),
        "confidence": "high",
        "warnings": [],
        "caption_text": "Fig. 3 caption text",
        "caption_line_count": 3,
        "caption_boundary_reason": "large_vertical_gap",
        "caption_gap_points": None,
        "next_text_preview": "",
        "top_detection": {"confidence": "high", "reason": "manual"},
        "crop_box_pixels": [0, 0, 100, 100],
        "rendered_page_pixels": [200, 200],
    }


class TestParseFigSpecs:
    def test_parses_label_page(self):
        assert batch.parse_fig_specs(["Fig. 2:5"]) == [
            {"label": "Fig. 2", "page": 5, "output": None}
        ]

    def test_parses_label_page_output(self):
        assert batch.parse_fig_specs(["Fig. 2:5:Fig2.png"]) == [
            {"label": "Fig. 2", "page": 5, "output": Path("Fig2.png")}
        ]

    def test_rejects_bad_page(self):
        with pytest.raises(ValueError):
            batch.parse_fig_specs(["Fig. 2:abc"])

    def test_rejects_too_many_parts(self):
        with pytest.raises(ValueError):
            batch.parse_fig_specs(["Fig. 2:5:a:b"])

    def test_rejects_empty_label(self):
        with pytest.raises(ValueError):
            batch.parse_fig_specs([" :5"])

    def test_parses_per_fig_top(self):
        assert batch.parse_fig_specs(["Fig. 2:5:Fig2.png:120"]) == [
            {"label": "Fig. 2", "page": 5, "output": Path("Fig2.png"), "top": 120.0}
        ]

    def test_parses_per_fig_top_without_output(self):
        assert batch.parse_fig_specs(["Fig. 2:5::120"]) == [
            {"label": "Fig. 2", "page": 5, "output": None, "top": 120.0}
        ]

    def test_rejects_invalid_top(self):
        with pytest.raises(ValueError):
            batch.parse_fig_specs(["Fig. 2:5:Fig2.png:abc"])

    def test_rejects_too_many_parts_with_top(self):
        with pytest.raises(ValueError):
            batch.parse_fig_specs(["Fig. 2:5:a:b:c"])


class TestValidateSpecs:
    def test_duplicate_page_label_rejected(self):
        figures = batch.parse_fig_specs(["Fig. 1:3:one.png", "Fig. 1:3:two.png"])
        with pytest.raises(ValueError):
            batch.validate_specs(figures)

    def test_output_collision_rejected(self):
        figures = batch.parse_fig_specs(["Fig. 1:3:same.png", "Fig. 2:4:same.png"])
        with pytest.raises(ValueError):
            batch.validate_specs(figures)

    def test_distinct_specs_accepted(self):
        figures = batch.parse_fig_specs(["Fig. 1:3:one.png", "Fig. 2:4:two.png"])
        assert batch.validate_specs(figures) is None


class TestExtractPage:
    def test_renders_page_once_for_multiple_figures(
        self, tmp_path, monkeypatch
    ):
        page = FakePage()
        options = make_options(tmp_path)

        def fake_caption(page_obj, page_height, label):
            return canned_caption()

        def fake_crop(rendered, page_width, page_height, caption, label, output, **kwargs):
            return canned_report(label, options["outdir"])

        monkeypatch.setattr(batch, "caption_for_page", fake_caption)
        monkeypatch.setattr(batch, "crop_from_rendered", fake_crop)

        figures = [make_fig("Fig. 1"), make_fig("Fig. 2")]
        reports = batch.extract_page(
            page, 600.0, 800.0, figures, options, page_index=3, pdf_path="x.pdf"
        )

        assert page.render_calls == 1
        assert len(reports) == 2
        assert all("error" not in report for report in reports)

    def test_reports_carry_source_metadata(
        self, tmp_path, monkeypatch
    ):
        page = FakePage()
        options = make_options(tmp_path)

        def fake_caption(page_obj, page_height, label):
            return canned_caption()

        def fake_crop(rendered, page_width, page_height, caption, label, output, **kwargs):
            return canned_report(label, options["outdir"])

        monkeypatch.setattr(batch, "caption_for_page", fake_caption)
        monkeypatch.setattr(batch, "crop_from_rendered", fake_crop)

        reports = batch.extract_page(
            page, 600.0, 800.0, [make_fig("Fig. 1")], options, page_index=3, pdf_path="x.pdf"
        )
        assert reports[0]["source"]["pdf_sha256"] == "fake-pdf-hash"
        assert reports[0]["source"]["page"] == 3
        assert reports[0]["source"]["label"] == "Fig. 1"

    def test_no_render_when_all_captions_fail(self, tmp_path, monkeypatch):
        page = FakePage()
        options = make_options(tmp_path)

        def fake_caption(page_obj, page_height, label):
            raise ValueError("caption label not found")

        monkeypatch.setattr(batch, "caption_for_page", fake_caption)

        reports = batch.extract_page(
            page, 600.0, 800.0, [make_fig("Fig. 1"), make_fig("Fig. 2")],
            options, page_index=3, pdf_path="x.pdf",
        )
        assert page.render_calls == 0
        assert len(reports) == 2
        assert all("error" in report for report in reports)

    def test_per_fig_top_forwarded_to_crop(self, tmp_path, monkeypatch):
        page = FakePage()
        options = make_options(tmp_path)
        captured = {}

        def fake_caption(page_obj, page_height, label):
            return canned_caption()

        def fake_crop(rendered, page_width, page_height, caption, label, output, **kwargs):
            captured[label] = kwargs.get("top_from_page")
            return canned_report(label, options["outdir"])

        monkeypatch.setattr(batch, "caption_for_page", fake_caption)
        monkeypatch.setattr(batch, "crop_from_rendered", fake_crop)

        figures = [make_fig("Fig. 1"), {"label": "Fig. 2", "page": 3, "output": None, "top": 150.0}]
        batch.extract_page(
            page, 600.0, 800.0, figures, options, page_index=3, pdf_path="x.pdf"
        )
        assert captured["Fig. 1"] is None
        assert captured["Fig. 2"] == 150.0

    def test_figure_error_does_not_break_other_figures(
        self, tmp_path, monkeypatch
    ):
        page = FakePage()
        options = make_options(tmp_path)

        def fake_caption(page_obj, page_height, label):
            if label == "Fig. 1":
                raise ValueError("caption label not found")
            return canned_caption()

        def fake_crop(rendered, page_width, page_height, caption, label, output, **kwargs):
            return canned_report(label, options["outdir"])

        monkeypatch.setattr(batch, "caption_for_page", fake_caption)
        monkeypatch.setattr(batch, "crop_from_rendered", fake_crop)

        reports = batch.extract_page(
            page, 600.0, 800.0, [make_fig("Fig. 1"), make_fig("Fig. 2")],
            options, page_index=3, pdf_path="x.pdf",
        )

        assert page.render_calls == 1
        assert len(reports) == 2
        errors = [r for r in reports if "error" in r]
        successes = [r for r in reports if "error" not in r]
        assert len(errors) == 1
        assert errors[0]["label"] == "Fig. 1"
        assert errors[0]["page"] == 3
        assert "caption label not found" in errors[0]["error"]
        assert len(successes) == 1
        assert successes[0]["label"] == "Fig. 2"


CACHE_SOURCE = {"pdf_sha256": "x", "page": 3, "label": "Fig. 1"}


class TestCacheHit:
    def write_crop(self, tmp_path, *, report=None, output_bytes=b"png-bytes"):
        output = tmp_path / "Fig1.png"
        output.write_bytes(output_bytes)
        payload = report
        if payload is None:
            payload = {
                "schema_version": 2,
                "source": CACHE_SOURCE,
                "output": str(output),
                "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
            }
        report_path = tmp_path / "Fig1.png.crop.json"
        report_path.write_text(
            payload if isinstance(payload, str) else json.dumps(payload),
            encoding="utf-8",
        )
        return report_path, output

    def test_missing_report_misses(self, tmp_path):
        output = tmp_path / "Fig1.png"
        output.write_bytes(b"png")
        assert batch.cache_hit(
            tmp_path / "Fig1.png.crop.json", CACHE_SOURCE, output
        ) is False

    def test_missing_output_misses(self, tmp_path):
        report_path, output = self.write_crop(tmp_path)
        output.unlink()
        assert batch.cache_hit(report_path, CACHE_SOURCE, output) is False

    def test_corrupt_report_misses(self, tmp_path):
        report_path, output = self.write_crop(tmp_path, report="{broken")
        assert batch.cache_hit(report_path, CACHE_SOURCE, output) is False

    def test_non_object_report_misses(self, tmp_path):
        report_path, output = self.write_crop(tmp_path, report="[]")
        assert batch.cache_hit(report_path, CACHE_SOURCE, output) is False

    def test_matching_report_and_output_hits(self, tmp_path):
        report_path, output = self.write_crop(tmp_path)
        assert batch.cache_hit(report_path, CACHE_SOURCE, output) is True

    def test_wrong_schema_version_misses(self, tmp_path):
        report = {
            "schema_version": 1,
            "source": CACHE_SOURCE,
            "output_sha256": hashlib.sha256(b"png-bytes").hexdigest(),
        }
        report_path, output = self.write_crop(tmp_path, report=report)
        assert batch.cache_hit(report_path, CACHE_SOURCE, output) is False

    def test_mismatched_source_misses(self, tmp_path):
        report_path, output = self.write_crop(tmp_path)
        changed = {**CACHE_SOURCE, "pdf_sha256": "new"}
        assert batch.cache_hit(report_path, changed, output) is False

    def test_legacy_report_without_source_misses(self, tmp_path):
        report = {
            "schema_version": 2,
            "output_sha256": hashlib.sha256(b"png-bytes").hexdigest(),
        }
        report_path, output = self.write_crop(tmp_path, report=report)
        assert batch.cache_hit(report_path, CACHE_SOURCE, output) is False

    def test_missing_output_sha256_misses(self, tmp_path):
        report = {"schema_version": 2, "source": CACHE_SOURCE}
        report_path, output = self.write_crop(tmp_path, report=report)
        assert batch.cache_hit(report_path, CACHE_SOURCE, output) is False

    def test_changed_output_png_misses(self, tmp_path):
        report_path, output = self.write_crop(tmp_path)
        output.write_bytes(b"different-png-bytes")
        assert batch.cache_hit(report_path, CACHE_SOURCE, output) is False


class TestBatchAggregation:
    def test_finalize_writes_successes_in_order_and_reports_errors(
        self, tmp_path
    ):
        outdir = tmp_path / "figs"
        outdir.mkdir()
        specs = [make_fig("Fig. 1", page=3), make_fig("Fig. 2", page=4), make_fig("Fig. 3", page=5)]
        results = {
            (4, "Fig. 2"): canned_report("Fig. 2", str(outdir)),
            (5, "Fig. 3"): {
                "pdf": "x.pdf",
                "page": 5,
                "label": "Fig. 3",
                "output": str(outdir / "Fig. 3.png"),
                "error": "ValueError: low confidence",
            },
        }
        reports, errors = batch.finalize_batch(specs, results)
        assert len(reports) == 1
        assert reports[0]["label"] == "Fig. 2"
        assert len(errors) == 2
        assert errors[0]["label"] == "Fig. 1"
        assert errors[0]["page"] == 3
        assert errors[1]["label"] == "Fig. 3"
        assert "low confidence" in errors[1]["error"]
