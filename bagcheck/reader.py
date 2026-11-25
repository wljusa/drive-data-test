from pathlib import Path

from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

from bagcheck.rules import check_topics
from bagcheck.report import Report

TYPESTORE = get_typestore(Stores.ROS2_HUMBLE)


def header_stamp_ns(msg: object) -> int:
    stamp = msg.header.stamp
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def read_header_stamps(bag_path: Path) -> dict[str, list[int]]:
    stamps: dict[str, list[int]] = {}
    with Reader(bag_path) as reader:
        for connection, _timestamp, raw in reader.messages():
            msg = TYPESTORE.deserialize_cdr(raw, connection.msgtype)
            stamps.setdefault(connection.topic, []).append(header_stamp_ns(msg))
    return stamps


def check_bag(bag_path: Path, expect: dict) -> Report:
    return check_topics(read_header_stamps(bag_path), expect)
