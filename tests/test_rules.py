from pathlib import Path

import pytest

from bagcheck.__main__ import main
from bagcheck.reader import check_bag
from bagcheck.rules import load_expect
from bagcheck.sample import write_bag

ROOT = Path(__file__).resolve().parents[1]
EXPECT = load_expect(ROOT / "expectations" / "sensors.yaml")


def codes(bag: Path) -> set[tuple[str, str]]:
    report = check_bag(bag, EXPECT)
    return {(item.code, item.topic) for item in report.findings}


def test_good_bag_passes(tmp_path: Path):
    bag = tmp_path / "good"
    write_bag(bag)
    assert codes(bag) == set()


def test_scan_drop_is_a_gap(tmp_path: Path):
    bag = tmp_path / "drop"
    write_bag(bag, drop_scan=True)
    assert ("gap", "/lidar/scan") in codes(bag)


def test_imu_rewind_is_monotonic(tmp_path: Path):
    bag = tmp_path / "rewind"
    write_bag(bag, rewind_imu=True)
    found = codes(bag)
    assert ("monotonic", "/imu/data") in found
    assert ("gap", "/imu/data") not in found


def test_missing_gnss(tmp_path: Path):
    bag = tmp_path / "nognss"
    write_bag(bag, include_gnss=False)
    assert ("missing", "/gnss/fix") in codes(bag)


def test_gnss_start_skew(tmp_path: Path):
    bag = tmp_path / "skew"
    write_bag(bag, gnss_delay_s=0.2)
    assert ("skew", "*") in codes(bag)


def test_cli_fail(tmp_path: Path):
    bag = tmp_path / "drop"
    write_bag(bag, drop_scan=True)
    assert main([str(bag), "--expect", str(ROOT / "expectations" / "sensors.yaml")]) == 1


def test_cli_pass(tmp_path: Path):
    bag = tmp_path / "good"
    write_bag(bag)
    assert main([str(bag), "--expect", str(ROOT / "expectations" / "sensors.yaml")]) == 0
