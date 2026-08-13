import pytest
import reader_workspace as workspace


class TestSafeFolderName:
    def test_replaces_invalid_chars(self):
        assert workspace.safe_folder_name('a<b>c:d"e/f\\g|h?i*j') == "a-b-c-d-e-f-g-h-i-j"

    def test_strips_trailing_dots_and_spaces(self):
        assert workspace.safe_folder_name("title... ") == "title"

    def test_collapses_whitespace(self):
        assert workspace.safe_folder_name("a   b  c") == "a b c"

    def test_tab_replaced_as_invalid_char(self):
        assert workspace.safe_folder_name("a\tb") == "a-b"

    def test_truncates_to_140(self):
        name = workspace.safe_folder_name("x" * 200)
        assert len(name) == 140

    def test_empty_input_raises(self):
        with pytest.raises(ValueError):
            workspace.safe_folder_name("   ")

    @pytest.mark.parametrize("name", ["CON", "con", "PRN", "AUX", "NUL", "COM1", "com3", "LPT9", "nul.txt"])
    def test_windows_reserved_names_rejected(self, name):
        with pytest.raises(ValueError):
            workspace.safe_folder_name(name)

    @pytest.mark.parametrize("name", ["CON paper", "NUL report", "COM3 paper"])
    def test_reserved_word_with_suffix_accepted(self, name):
        assert workspace.safe_folder_name(name) == name


class TestCompareSources:
    def test_changed_file_warns(self):
        previous = {
            "sources": [
                {
                    "role": "main_paper",
                    "path": "C:/p/paper.pdf",
                    "sha256": "old",
                }
            ]
        }
        current = [
            {
                "role": "main_paper",
                "path": "C:/p/paper.pdf",
                "sha256": "new",
            }
        ]
        warnings = workspace.compare_sources(previous, current)
        assert len(warnings) == 1
        assert "main_paper" in warnings[0]
        assert "paper.pdf" in warnings[0]

    def test_unchanged_file_no_warning(self):
        previous = {
            "sources": [
                {"role": "supplement", "path": "C:/p/s.pdf", "sha256": "same"}
            ]
        }
        current = [
            {"role": "supplement", "path": "C:/p/s.pdf", "sha256": "same"}
        ]
        assert workspace.compare_sources(previous, current) == []

    def test_previous_entries_without_hash_ignored(self):
        previous = {"sources": [{"role": "movie", "path": "C:/p/m.mov"}]}
        current = [{"role": "movie", "path": "C:/p/m.mov", "sha256": "new"}]
        assert workspace.compare_sources(previous, current) == []

    def test_missing_previous_sources_ignored(self):
        previous = {"sources": []}
        current = [
            {"role": "main_paper", "path": "C:/p/paper.pdf", "sha256": "new"}
        ]
        assert workspace.compare_sources(previous, current) == []

    def test_non_matching_role_path_ignored(self):
        previous = {
            "sources": [
                {"role": "main_paper", "path": "C:/p/old.pdf", "sha256": "old"}
            ]
        }
        current = [
            {"role": "main_paper", "path": "C:/p/new.pdf", "sha256": "new"}
        ]
        assert workspace.compare_sources(previous, current) == []
