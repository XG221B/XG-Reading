import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skill" / "xg-reading" / "scripts"
SKILL_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def pytest_configure(config):
    """Register platform/integration markers used by the CI job split (E01).

    Windows CI runs everything. The Ubuntu job runs the pure-Python suite and
    excludes tests marked ``office_integration`` (needs a real Word/LibreOffice
    conversion) or ``windows_only`` (asserts Windows-specific behavior). No test
    currently carries these markers; they exist so future integration tests do
    not silently run on a runner without Office.
    """
    config.addinivalue_line(
        "markers",
        "windows_only: requires Windows-specific behavior (skipped by the Linux CI job)",
    )
    config.addinivalue_line(
        "markers",
        "office_integration: requires a real Word/LibreOffice renderer "
        "(excluded by the Linux CI job)",
    )

