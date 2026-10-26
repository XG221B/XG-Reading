"""Documentation consistency tests for reference modules and domain routing.

These tests keep the prose contracts in sync with the reference files on disk:

* every ``references/*.md`` path named in ``SKILL.md`` must resolve;
* the domain-module set under the "Read the selected module completely" list must
  equal the set of modules named in ``references/biology-routing.md`` (so a new
  module must be added to both places, without pinning a hard-coded file count);
* the six domain modules currently documented are all listed;
* the new micro/nano-robotics module has its key sections and real content;
* ``SKILL.md`` frontmatter and both READMEs advertise the new domain.

Scope boundary (E01): these are documentation-wiring checks only. Section
titles, keywords, and file lengths do not prove that the scientific guidance is
appropriate; that needs agent-reviewed paper samples, not regex assertions.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skill" / "xg-reading"
REFERENCES_DIR = SKILL_DIR / "references"
SKILL_MD = SKILL_DIR / "SKILL.md"
ROUTING_MD = REFERENCES_DIR / "biology-routing.md"
README_CN = REPO_ROOT / "README.md"
README_EN = REPO_ROOT / "README_EN.md"

MODULE_LIST_MARKER = "Read the selected module completely"
MODULE_BULLET = re.compile(r"-\s+`references/([A-Za-z0-9_-]+)\.md`")
NUMBERED_ITEM = re.compile(r"\d+\.\s")
SKILL_REFERENCE_PATH = re.compile(r"`(references/[^`\n]+?\.md)`")
ROUTING_MODULE_PATH = re.compile(r"`([A-Za-z0-9_-]+)\.md`")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\s*(?:\r?\n|\Z)", re.DOTALL)

# The domain modules the skill currently documents. This is a floor, not a pin:
# adding a new module only requires listing it in SKILL.md and routing to it.
REQUIRED_DOMAIN_MODULES = (
    "molecular-cellular",
    "omics-computational",
    "immunology-microbiology",
    "structural-methods",
    "translational-engineering",
    "micro-nano-robotics",
)

MICRO_NANO_MODULE = REFERENCES_DIR / "micro-nano-robotics.md"
MICRO_NANO_SECTIONS = (
    "Actuation and propulsion",
    "Navigation, control, and imaging",
    "Cargo loading, targeting, and release",
    "Functional validation and biological response",
    "Common overclaims",
)


def read_text(path: Path) -> str:
    # The skill's own artifact readers tolerate a UTF-8 BOM; match that here.
    return path.read_text(encoding="utf-8-sig")


def skill_module_stems(skill_text: str | None = None) -> set[str]:
    """Parse the domain modules under "Read the selected module completely"."""
    text = read_text(SKILL_MD) if skill_text is None else skill_text
    lines = text.splitlines()
    if MODULE_LIST_MARKER not in text:
        raise AssertionError(f"SKILL.md is missing the module-list marker: {MODULE_LIST_MARKER}")
    start = next(
        index for index, line in enumerate(lines) if MODULE_LIST_MARKER in line
    )
    stems = set()
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        if NUMBERED_ITEM.match(stripped):
            break
        match = MODULE_BULLET.fullmatch(stripped)
        if match:
            stems.add(match.group(1))
    return stems


def routing_module_stems(routing_text: str | None = None) -> set[str]:
    """Collect the modules named in biology-routing.md (``name.md`` references)."""
    text = read_text(ROUTING_MD) if routing_text is None else routing_text
    return {
        Path(name).stem
        for name in ROUTING_MODULE_PATH.findall(text)
    }


def frontmatter_description(skill_text: str | None = None) -> str:
    text = read_text(SKILL_MD) if skill_text is None else skill_text
    match = FRONTMATTER.match(text)
    assert match is not None, "SKILL.md must start with YAML frontmatter"
    for line in match.group(1).splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("SKILL.md frontmatter lacks a description field")


class TestSkillModuleList:
    def test_module_list_is_present_and_non_empty(self):
        assert MODULE_LIST_MARKER in read_text(SKILL_MD)
        assert skill_module_stems()

    def test_module_bullets_are_unique(self):
        text = read_text(SKILL_MD)
        bullets = [
            line.strip()
            for line in text.splitlines()
            if MODULE_BULLET.fullmatch(line.strip())
        ]
        assert len(bullets) == len(set(bullets))

    @pytest.mark.parametrize("stem", REQUIRED_DOMAIN_MODULES)
    def test_required_module_is_listed(self, stem):
        assert stem in skill_module_stems()

    def test_every_listed_module_file_exists(self):
        for stem in skill_module_stems():
            path = REFERENCES_DIR / f"{stem}.md"
            assert path.is_file(), f"SKILL.md lists missing module file: {path}"

    def test_listed_modules_match_routing_modules_bidirectionally(self):
        skill_modules = skill_module_stems()
        routed_modules = routing_module_stems()
        assert skill_modules == routed_modules, (
            "SKILL.md module list and biology-routing.md are out of sync: "
            f"skill_only={skill_modules - routed_modules}, "
            f"routing_only={routed_modules - skill_modules}"
        )

    def test_documented_module_set_covers_the_required_domains(self):
        # Set equality above keeps a future module addition from silently
        # diverging; this floor makes sure none of today's modules disappear.
        assert set(REQUIRED_DOMAIN_MODULES) <= skill_module_stems()


class TestBiologyRouting:
    def test_routing_mentions_micro_nano_robotics(self):
        assert "`micro-nano-robotics.md`" in read_text(ROUTING_MD)

    def test_routing_has_a_micro_nano_section(self):
        assert "## Micro/nano robotics and active delivery" in read_text(ROUTING_MD)

    def test_routing_contains_hybrid_examples_for_micro_nano(self):
        routing = read_text(ROUTING_MD).lower()
        assert "micro/nano robotics primary" in routing
        assert "secondary" in routing

    def test_routing_mentions_every_skill_listed_module(self):
        routing = read_text(ROUTING_MD)
        for stem in skill_module_stems():
            assert f"`{stem}.md`" in routing, stem


class TestMicroNanoRoboticsModule:
    def test_module_file_is_not_trivial(self):
        assert MICRO_NANO_MODULE.is_file()
        text = read_text(MICRO_NANO_MODULE)
        assert len(text.strip()) > 1000
        assert len(text.splitlines()) > 30

    def test_module_has_a_title(self):
        first_line = read_text(MICRO_NANO_MODULE).splitlines()[0]
        assert first_line == "# Micro/nano robotics and active delivery"

    @pytest.mark.parametrize("section", MICRO_NANO_SECTIONS)
    def test_key_section_heading_is_present(self, section):
        text = read_text(MICRO_NANO_MODULE)
        pattern = re.compile(rf"^##\s+{re.escape(section)}\s*$", re.MULTILINE)
        assert pattern.search(text), f"missing section: {section}"

    def test_key_sections_have_body_text(self):
        text = read_text(MICRO_NANO_MODULE)
        for section in MICRO_NANO_SECTIONS:
            pattern = re.compile(
                rf"^##\s+{re.escape(section)}\s*$(.*?)(?=^##\s+|\Z)",
                re.MULTILINE | re.DOTALL,
            )
            match = pattern.search(text)
            assert match is not None, section
            assert match.group(1).strip(), f"empty section: {section}"


class TestModuleListParsing:
    """The set-equality contract must come from parsing, not a hard-coded list."""

    def test_parser_collects_every_bullet_in_the_section(self):
        text = (
            "3. Read the selected module completely:\n"
            "   - `references/alpha.md`\n"
            "   - `references/beta.md`\n"
            "4. Read `references/next.md`\n"
        )
        assert skill_module_stems(text) == {"alpha", "beta"}

    def test_parser_stops_at_the_next_numbered_step(self):
        text = (
            "3. Read the selected module completely:\n"
            "   - `references/alpha.md`\n"
            "4. Next step\n"
            "   - `references/beta.md`\n"
        )
        assert skill_module_stems(text) == {"alpha"}

    def test_routing_parser_collects_backticked_module_files(self):
        text = "Use `alpha.md` when X dominates; add `beta.md` only when needed."
        assert routing_module_stems(text) == {"alpha", "beta"}


class TestSkillAndReadmeKeywords:
    def test_skill_frontmatter_description_mentions_micro_nano_robotics(self):
        assert "微纳机器人" in frontmatter_description()

    def test_readme_cn_mentions_micro_nano_robotics(self):
        assert "微纳机器人" in read_text(README_CN)

    def test_readme_en_mentions_micro_nano_robotics(self):
        assert "micro/nano robotics" in read_text(README_EN)

    def test_skill_load_resources_names_the_module(self):
        assert "`references/micro-nano-robotics.md`" in read_text(SKILL_MD)


class TestNoDanglingReferences:
    def test_backticked_reference_paths_resolve(self):
        paths = SKILL_REFERENCE_PATH.findall(read_text(SKILL_MD))
        assert paths, "SKILL.md should name its references through backticked paths"
        for relative in paths:
            assert not relative.startswith(("/", "\\")), relative
            assert ".." not in Path(relative).parts, relative
            assert (SKILL_DIR / relative).is_file(), f"dangling reference: {relative}"

    def test_skill_named_reference_files_exist_for_routing_targets(self):
        for stem in routing_module_stems():
            assert (REFERENCES_DIR / f"{stem}.md").is_file(), stem
