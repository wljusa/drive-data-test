from pathlib import Path

import yaml

from bagcheck.reader import read_messages
from bagcheck.report import Finding
from bagcheck.rules import check_topics
from bagcheck.sample import TYPESTORE, write_bag

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "expectations" / "drive.yaml"
STATUS_FIX = TYPESTORE.types["sensor_msgs/msg/NavSatStatus"].STATUS_FIX


def load_rules(path: Path = RULES_PATH) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "topics" not in data:
        raise ValueError(f"规则格式错误: {path}")
    return data


def load_scenario(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"场景格式错误: {path}")
    return data


def write_scenario(path: Path, scenario: dict) -> None:
    fault = scenario.get("fault") or {}
    write_bag(
        path,
        duration_s=float(scenario.get("duration_s", 3.0)),
        ego_speed_mps=float(scenario.get("ego_speed_mps", 16.0)),
        lead_range_m=float(scenario.get("lead_range_m", 40.0)),
        drop_scan=bool(fault.get("drop_scan", False)),
        rewind_imu=bool(fault.get("rewind_imu", False)),
        include_gnss=not bool(fault.get("no_gnss", False)),
        gnss_delay_s=float(fault.get("gnss_delay_s", 0.0)),
        gnss_lose_after_s=fault.get("gnss_lose_after_s"),
        include_twist=True,
    )


def odd_findings(messages: dict, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    speeds = [msg.twist.linear.x for _, msg in messages.get("/vehicle/twist", [])]
    low = float(rules["speed_min_mps"])
    high = float(rules["speed_max_mps"])
    if speeds and (min(speeds) < low or max(speeds) > high):
        findings.append(
            Finding("/vehicle/twist", "speed", f"车速 {min(speeds):.1f}–{max(speeds):.1f} m/s，允许 {low:.1f}–{high:.1f}")
        )

    beams = [int(index) for index in rules["forward_beams"]]
    ranges = [
        min(float(msg.ranges[index]) for index in beams)
        for _, msg in messages.get("/lidar/scan", [])
        if len(msg.ranges) > max(beams)
    ]
    limit = float(rules["min_lead_range_m"])
    if ranges and min(ranges) < limit:
        findings.append(
            Finding("/lidar/scan", "gap_range", f"前向最近距离 {min(ranges):.1f}m，阈值 {limit:.1f}m")
        )

    if rules.get("require_gnss_fix", True):
        fixes = messages.get("/gnss/fix", [])
        if fixes and any(int(msg.status.status) != int(STATUS_FIX) for _, msg in fixes):
            findings.append(Finding("/gnss/fix", "gnss", "存在失锁帧"))
    return findings


def evaluate(messages: dict, rules: dict) -> list[Finding]:
    stamps = {topic: [stamp for stamp, _msg in items] for topic, items in messages.items()}
    return [*check_topics(stamps, rules).findings, *odd_findings(messages, rules)]


def expectation_failures(scenario: dict, findings: list[Finding]) -> list[str]:
    expect = scenario.get("expect", {})
    codes = {(item.code, item.topic) for item in findings}
    failures: list[str] = []
    accept = bool(expect.get("accept", False))
    if accept and findings:
        failures.append("期望片段通过，但有失败项：" + "；".join(str(item) for item in findings))
    if not accept and not findings:
        failures.append("期望拒绝该片段，但检查通过")
    for code, topic in expect.get("codes", []):
        if (code, topic) not in codes:
            failures.append(f"缺少失败项 {code} {topic}")
    return failures


def run_scenario(scenario: dict, bag_path: Path, rules: dict | None = None) -> tuple[list[Finding], list[str]]:
    rules = load_rules() if rules is None else rules
    write_scenario(bag_path, scenario)
    findings = evaluate(read_messages(bag_path), rules)
    return findings, expectation_failures(scenario, findings)
