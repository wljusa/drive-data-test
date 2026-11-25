from pathlib import Path

import yaml

from bagcheck.report import Finding, Report

NS_PER_MS = 1_000_000
NS_PER_SEC = 1_000_000_000


def load_expect(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "topics" not in data:
        raise ValueError(f"期望文件格式错误: {path}")
    return data


def check_stamps(topic: str, stamps: list[int], spec: dict) -> list[Finding]:
    findings: list[Finding] = []
    if len(stamps) < 2:
        findings.append(Finding(topic, "count", f"有效消息 {len(stamps)} 条，无法计算频率"))
        return findings

    previous = stamps[0]
    max_gap_ms = 0.0
    monotonic = True
    for stamp in stamps[1:]:
        delta_ms = (stamp - previous) / NS_PER_MS
        if stamp <= previous:
            monotonic = False
        elif delta_ms > max_gap_ms:
            max_gap_ms = delta_ms
        if stamp > previous:
            previous = stamp
    if not monotonic:
        findings.append(Finding(topic, "monotonic", "header.stamp 相对接收顺序出现回退"))

    limit = float(spec["max_gap_ms"])
    if max_gap_ms > limit:
        findings.append(Finding(topic, "gap", f"最大帧间隔 {max_gap_ms:.1f}ms，阈值 {limit:.1f}ms"))

    duration = (stamps[-1] - stamps[0]) / NS_PER_SEC
    if duration <= 0:
        findings.append(Finding(topic, "hz", "时间跨度为 0"))
        return findings
    measured = (len(stamps) - 1) / duration
    expected = float(spec["hz"])
    tolerance = float(spec["hz_tolerance"])
    if abs(measured - expected) / expected > tolerance:
        findings.append(
            Finding(
                topic,
                "hz",
                f"实测 {measured:.2f}Hz，期望 {expected:.2f}Hz，容差 {tolerance:.0%}",
            )
        )
    return findings


def check_topics(stamps_by_topic: dict[str, list[int]], expect: dict) -> Report:
    findings: list[Finding] = []
    specs: dict = expect["topics"]
    present: dict[str, list[int]] = {}
    for topic, spec in specs.items():
        stamps = stamps_by_topic.get(topic)
        if not stamps:
            findings.append(Finding(topic, "missing", "话题不存在或没有消息"))
            continue
        present[topic] = stamps
        findings.extend(check_stamps(topic, stamps, spec))

    if len(present) >= 2:
        starts = {topic: stamps[0] for topic, stamps in present.items()}
        skew_ms = (max(starts.values()) - min(starts.values())) / NS_PER_MS
        limit = float(expect.get("sync_max_start_skew_ms", 50))
        if skew_ms > limit:
            findings.append(Finding("*", "skew", f"话题首帧相差 {skew_ms:.1f}ms，阈值 {limit:.1f}ms"))
    return Report(findings)
