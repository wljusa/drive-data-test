import argparse
import shutil
from pathlib import Path

import numpy as np
from rosbags.rosbag2 import Writer
from rosbags.typesys import Stores, get_typestore

TYPESTORE = get_typestore(Stores.ROS2_HUMBLE)
Header = TYPESTORE.types["std_msgs/msg/Header"]
Time = TYPESTORE.types["builtin_interfaces/msg/Time"]
Imu = TYPESTORE.types["sensor_msgs/msg/Imu"]
Quaternion = TYPESTORE.types["geometry_msgs/msg/Quaternion"]
Vector3 = TYPESTORE.types["geometry_msgs/msg/Vector3"]
LaserScan = TYPESTORE.types["sensor_msgs/msg/LaserScan"]
NavSatFix = TYPESTORE.types["sensor_msgs/msg/NavSatFix"]
NavSatStatus = TYPESTORE.types["sensor_msgs/msg/NavSatStatus"]

ZERO9 = np.zeros(9, dtype=np.float64)
RANGES = np.full(8, 5.0, dtype=np.float32)
INTENSITIES = np.zeros(8, dtype=np.float32)


def _ns(seconds: float) -> int:
    return int(round(seconds * 1_000_000_000))


def _header(stamp_ns: int, frame_id: str):
    sec, nanosec = divmod(stamp_ns, 1_000_000_000)
    return Header(stamp=Time(sec=int(sec), nanosec=int(nanosec)), frame_id=frame_id)


def _imu(stamp_ns: int):
    return Imu(
        header=_header(stamp_ns, "imu"),
        orientation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0),
        orientation_covariance=ZERO9,
        angular_velocity=Vector3(x=0.0, y=0.0, z=0.01),
        angular_velocity_covariance=ZERO9,
        linear_acceleration=Vector3(x=0.0, y=0.0, z=9.81),
        linear_acceleration_covariance=ZERO9,
    )


def _scan(stamp_ns: int):
    return LaserScan(
        header=_header(stamp_ns, "lidar"),
        angle_min=-0.8,
        angle_max=0.8,
        angle_increment=1.6 / 7,
        time_increment=0.0,
        scan_time=0.1,
        range_min=0.1,
        range_max=30.0,
        ranges=RANGES,
        intensities=INTENSITIES,
    )


def _fix(stamp_ns: int):
    return NavSatFix(
        header=_header(stamp_ns, "gnss"),
        status=NavSatStatus(status=NavSatStatus.STATUS_FIX, service=NavSatStatus.SERVICE_GPS),
        latitude=22.54,
        longitude=113.95,
        altitude=20.0,
        position_covariance=ZERO9,
        position_covariance_type=NavSatFix.COVARIANCE_TYPE_UNKNOWN,
    )


def _times(hz: float, duration_s: float, delay_s: float = 0.0) -> list[int]:
    period = 1.0 / hz
    stamps = []
    t = delay_s
    while t <= duration_s + 1e-9:
        stamps.append(_ns(t))
        t += period
    return stamps


def write_bag(
    path: Path,
    *,
    duration_s: float = 2.0,
    drop_scan: bool = False,
    rewind_imu: bool = False,
    include_gnss: bool = True,
    gnss_delay_s: float = 0.0,
) -> None:
    if path.exists():
        shutil.rmtree(path)

    imu_times = _times(100, duration_s)
    scan_times = _times(10, duration_s)
    gnss_times = _times(5, duration_s, gnss_delay_s) if include_gnss else []
    if drop_scan:
        scan_times = [stamp for stamp in scan_times if not _ns(0.50) <= stamp < _ns(0.90)]
    if rewind_imu and len(imu_times) > 50:
        imu_times[50] = imu_times[48]

    messages: list[tuple[int, str, str, object]] = []
    for index, stamp in enumerate(imu_times):
        bag_time = _ns(index / 100)
        messages.append((bag_time, "/imu/data", "sensor_msgs/msg/Imu", _imu(stamp)))
    for index, stamp in enumerate(scan_times):
        bag_time = _ns(index / 10)
        messages.append((bag_time, "/lidar/scan", "sensor_msgs/msg/LaserScan", _scan(stamp)))
    for index, stamp in enumerate(gnss_times):
        bag_time = _ns(gnss_delay_s + index / 5)
        messages.append((bag_time, "/gnss/fix", "sensor_msgs/msg/NavSatFix", _fix(stamp)))
    messages.sort(key=lambda item: item[0])

    with Writer(path, version=9) as writer:
        connections = {}
        for _bag_time, topic, msgtype, _msg in messages:
            if topic not in connections:
                connections[topic] = writer.add_connection(topic, msgtype, typestore=TYPESTORE)
        for bag_time, topic, msgtype, msg in messages:
            raw = TYPESTORE.serialize_cdr(msg, msgtype)
            writer.write(connections[topic], bag_time, raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成一份用于检查器演示的 rosbag2")
    parser.add_argument("bag", type=Path)
    parser.add_argument("--drop-scan", action="store_true", help="激光在 0.5s 到 0.9s 之间丢帧")
    parser.add_argument("--rewind-imu", action="store_true", help="IMU header.stamp 回退一帧")
    parser.add_argument("--no-gnss", action="store_true", help="不写 GNSS 话题")
    parser.add_argument("--gnss-delay", type=float, default=0.0, help="GNSS 首帧延后的秒数")
    args = parser.parse_args(argv)
    write_bag(
        args.bag,
        drop_scan=args.drop_scan,
        rewind_imu=args.rewind_imu,
        include_gnss=not args.no_gnss,
        gnss_delay_s=args.gnss_delay,
    )
    print(args.bag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
