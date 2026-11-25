import argparse
import sys
from pathlib import Path

from bagcheck.reader import check_bag
from bagcheck.rules import load_expect


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查 rosbag2 里传感器话题的频率、丢帧和时间戳")
    parser.add_argument("bag", type=Path)
    parser.add_argument("--expect", type=Path, required=True)
    args = parser.parse_args(argv)
    report = check_bag(args.bag, load_expect(args.expect))
    if report.ok:
        print("PASS")
        return 0
    for finding in report.findings:
        print(finding)
    print("FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
