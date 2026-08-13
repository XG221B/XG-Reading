from extract_figure_region import crop_from_rendered
from PIL import Image


def make_caption():
    return {
        "caption_bottom": 100.0,
        "caption_top": 80.0,
        "caption_text": "Fig. 1 caption",
        "caption_line_count": 3,
        "boundary_reason": "large_vertical_gap",
        "boundary_gap": None,
        "next_text_top": 60.0,
        "next_text_preview": "",
        "confidence": "high",
        "warnings": [],
    }


class TestCropFromRendered:
    def test_saves_valid_png_and_leaves_no_temp(self, tmp_path):
        image = Image.new("RGB", (200, 100), "white")
        output = tmp_path / "Fig1.png"
        report = crop_from_rendered(
            image,
            600.0,
            800.0,
            make_caption(),
            "Fig. 1",
            output,
            scale=3.0,
            left=0.0,
            right=0.0,
            caption_padding=4.0,
            top_from_page=10.0,
            allow_low_confidence=True,
        )
        assert output.exists()
        with Image.open(output) as saved:
            assert saved.format == "PNG"
        assert not [p for p in tmp_path.iterdir() if ".tmp" in p.name]
        assert "output" in report
