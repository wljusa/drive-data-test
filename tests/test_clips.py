from pathlib import Path

import pytest

from bagcheck.clip import load_scenario, run_scenario

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = sorted((ROOT / "scenarios").glob("*.yaml"))


@pytest.mark.parametrize("path", SCENARIOS, ids=lambda item: item.stem)
def test_clip(path: Path, tmp_path: Path):
    scenario = load_scenario(path)
    _findings, failures = run_scenario(scenario, tmp_path / path.stem)
    assert failures == []
