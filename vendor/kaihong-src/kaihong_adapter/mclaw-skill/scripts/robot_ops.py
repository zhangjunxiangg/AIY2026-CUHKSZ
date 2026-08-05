#!/usr/bin/env python3
"""JSON command surface for bounded Kaihong robot operations."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shlex
import socket
import subprocess
import sys
import time
import xmlrpc.client
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCRIPT_ROOT = Path(__file__).resolve().parent
CHASSIS_CLIENT = Path(
    os.environ.get(
        "MCLAW_CHASSIS_CLIENT",
        str(SCRIPT_ROOT / "ros_cmd_vel.py"),
    )
)
ROBOT_ROOT = Path(os.environ.get("ROBOT_HOST_ROOT", "/data/robot-host"))
OUTPUT_ROOT = Path(
    os.environ.get(
        "ROBOT_OPERATIONS_OUTPUT",
        "/data/local/tmp/.mclaw/output/robot",
    )
)
COLOR_SORTING_DEMO = ROBOT_ROOT / "student/demo/color_sorting/run-color-sorting-demo.sh"
COLOR_SORTING_RESULT = (
    ROBOT_ROOT / "student/output/color-sorting/latest-color-sorting.json"
)
AUX_RELAY = ROBOT_ROOT / "student/interfaces/aux-target-relay.sh"
AUX_RGBD_RECEIVER = ROBOT_ROOT / "student/tools/receive-aux-rgbd-once.sh"
AUX_COLOR_TOPIC = "/aux_camera/color/image_raw/compressed"
AUX_DEPTH_TOPIC = "/aux_camera/depth/image_raw"
AUX_OUTPUT_DIR = ROBOT_ROOT / "student/output"
PHOTO_SERVER = SCRIPT_ROOT / "latest_photo_server.py"
PHOTO_SERVER_PORT = int(os.environ.get("ROBOT_PHOTO_VIEW_PORT", "18080"))
PHOTO_SERVER_PID = OUTPUT_ROOT / "latest-photo-server.pid"
PHOTO_SERVER_LOG = OUTPUT_ROOT / "latest-photo-server.log"


class TimeoutTransport(xmlrpc.client.Transport):
    def __init__(self, timeout: float) -> None:
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host: Any) -> Any:
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection


def emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("ok") else int(payload.get("returncode", 1) or 1)


def run(
    command: list[str],
    timeout: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )


def parse_last_json(completed: subprocess.CompletedProcess[str], command: str) -> dict[str, Any]:
    for line in reversed(completed.stdout.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payload.setdefault("command", command)
            payload.setdefault("returncode", completed.returncode)
            payload.setdefault("ok", completed.returncode == 0)
            if completed.stderr.strip():
                payload.setdefault("stderr", completed.stderr[-2000:])
            return payload
    return {
        "ok": completed.returncode == 0,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-6000:],
        "stderr": completed.stderr[-3000:],
    }


def container_running(name: str) -> bool:
    completed = run(["docker", "inspect", "-f", "{{.State.Running}}", name], 5)
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def container_python(
    container: str,
    local_script: Path,
    arguments: list[str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    remote_script = f"/tmp/mclaw-{local_script.name}"
    copied = run(["docker", "cp", str(local_script), f"{container}:{remote_script}"], 10)
    if copied.returncode != 0:
        return copied
    quoted_args = " ".join(shlex.quote(value) for value in arguments)
    command = (
        "source /opt/ros/noetic/setup.bash; "
        "source /chassis_ws/devel/setup.bash 2>/dev/null || true; "
        "source /vision_ws/devel/setup.bash 2>/dev/null || true; "
        "source /arm_ws/devel/setup.bash 2>/dev/null || true; "
        f"python3 {shlex.quote(remote_script)} {quoted_args}"
    )
    try:
        return run(["docker", "exec", container, "bash", "-lc", command], timeout)
    finally:
        run(["docker", "exec", container, "rm", "-f", remote_script], 5)


def chassis(args: argparse.Namespace) -> int:
    if not CHASSIS_CLIENT.exists():
        return emit({"ok": False, "error": f"missing chassis client: {CHASSIS_CLIENT}"})
    # robot_ops.py itself is launched through /bin/run.  Starting another
    # nested /bin/run here changed the working chassis path after the skills
    # were consolidated.  Reuse the current interpreter and inherited ROS
    # environment so chassis publishing has the same single wrapper layer as
    # the former dedicated skill.
    command = [sys.executable, str(CHASSIS_CLIENT)]
    if args.command == "chassis-status":
        command.append("status")
    elif args.command == "chassis-stop":
        command.append("stop")
    else:
        command.extend(
            [
                "publish",
                "--linear-x",
                str(args.linear_x),
                "--linear-y",
                str(args.linear_y),
                "--angular-z",
                str(args.angular_z),
                "--duration",
                str(args.duration),
            ]
        )
    try:
        completed = run(command, 25)
    except subprocess.TimeoutExpired:
        return emit({"ok": False, "command": args.command, "error": "chassis command timeout"})
    return emit(parse_last_json(completed, args.command))


def arm(args: argparse.Namespace) -> int:
    script = SCRIPT_ROOT / ("arm_state.py" if args.command == "arm-read" else "arm_set_one.py")
    arguments: list[str] = []
    if args.command == "arm-set-one":
        arguments = ["--servo-id", str(args.servo_id), "--position", str(args.position)]
        if args.allow_large_delta:
            arguments.append("--allow-large-delta")

    # The final 4.1 delivery runs the arm on the host only.
    host_status = run([str(ROBOT_ROOT / "status-host-arm-4.1.sh")], 5)
    if host_status.returncode == 0:
        env = os.environ.copy()
        env["ROBOT_HOST_ROOT"] = str(ROBOT_ROOT)
        env["PYROOT"] = env.get("PYROOT", "/data/local/release/usr")
        arm_root = ROBOT_ROOT / "host_arm"
        env["ARM_HOST_ROOT"] = str(arm_root)
        env["PYTHONPATH"] = ":".join(
            [
                str(arm_root / "kinematics/src"),
                str(arm_root / "servo_driver/src"),
                str(arm_root / "servo_controllers/src"),
                str(arm_root / "python"),
                env.get("PYTHONPATH", ""),
            ]
        ).strip(":")
        env["ROS_PACKAGE_PATH"] = ":".join(
            [str(arm_root), env.get("ROS_PACKAGE_PATH", "")]
        ).strip(":")
        command = ["/bin/run", "python3", str(script), *arguments]
        try:
            completed = run(command, 30, env=env)
        except subprocess.TimeoutExpired:
            return emit({"ok": False, "command": args.command, "error": "arm command timeout"})
        return emit(parse_last_json(completed, args.command))

    return emit(
        {
            "ok": False,
            "command": args.command,
            "error": "host arm is not running",
        }
    )


def gripper(args: argparse.Namespace) -> int:
    command_name = "gripper-set"
    script = ROBOT_ROOT / "run-set-gripper-4.1.sh"
    if not script.exists():
        return emit(
            {"ok": False, "command": command_name, "error": f"missing script: {script}"}
        )
    try:
        completed = run([str(script), str(args.position)], 20)
    except subprocess.TimeoutExpired:
        return emit({"ok": False, "command": command_name, "error": "gripper command timeout"})
    payload = parse_last_json(completed, command_name)
    if not any(line.startswith("{") for line in completed.stdout.splitlines()):
        payload.update(
            {
                "ok": completed.returncode == 0,
                "command": command_name,
                "position": args.position,
                "returncode": completed.returncode,
                "result": completed.stdout.strip(),
            }
        )
    return emit(payload)


def camera_capture() -> int:
    command_name = "camera-capture"
    if not container_running("rk3588s-vision"):
        return emit({"ok": False, "command": command_name, "error": "rk3588s-vision is not running"})
    script = SCRIPT_ROOT / "camera_snapshot.py"
    remote_prefix = "/tmp/mclaw-camera-latest"
    try:
        completed = container_python(
            "rk3588s-vision",
            script,
            ["--output-prefix", remote_prefix],
            25,
        )
    except subprocess.TimeoutExpired:
        return emit({"ok": False, "command": command_name, "error": "camera capture timeout"})
    payload = parse_last_json(completed, command_name)
    if completed.returncode != 0 or not payload.get("ok"):
        return emit(payload)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "rgb_path": OUTPUT_ROOT / "camera-latest-rgb.jpg",
        "depth_path": OUTPUT_ROOT / "camera-latest-depth.png",
        "depth_preview_path": OUTPUT_ROOT / "camera-latest-depth-preview.jpg",
        "metadata_path": OUTPUT_ROOT / "camera-latest.json",
    }
    remote_files = {
        "rgb_path": f"{remote_prefix}-rgb.jpg",
        "depth_path": f"{remote_prefix}-depth.png",
        "depth_preview_path": f"{remote_prefix}-depth-preview.jpg",
        "metadata_path": f"{remote_prefix}.json",
    }
    try:
        for key, host_path in outputs.items():
            copied = run(
                ["docker", "cp", f"rk3588s-vision:{remote_files[key]}", str(host_path)],
                10,
            )
            if copied.returncode != 0:
                return emit(
                    {
                        "ok": False,
                        "command": command_name,
                        "error": f"failed to copy {key}",
                        "stderr": copied.stderr[-2000:],
                    }
                )
    finally:
        run(
            [
                "docker",
                "exec",
                "rk3588s-vision",
                "rm",
                "-f",
                *remote_files.values(),
            ],
            5,
        )
    payload.update({key: str(path) for key, path in outputs.items()})
    return emit(payload)


def lidar(command_name: str) -> int:
    script_name = (
        "status-lidar-4.1.sh" if command_name == "lidar-status" else "healthcheck-lidar-4.1.sh"
    )
    script = ROBOT_ROOT / script_name
    if not script.exists():
        return emit({"ok": False, "command": command_name, "error": f"missing script: {script}"})
    try:
        completed = run(["sh", str(script)], 20)
    except subprocess.TimeoutExpired:
        return emit({"ok": False, "command": command_name, "error": "lidar read timeout"})
    return emit(parse_last_json(completed, command_name))


def board_interface(command_name: str) -> int:
    if command_name == "health":
        command = [str(ROBOT_ROOT / "healthcheck-all-4.1.sh")]
    elif command_name == "status":
        command = [str(ROBOT_ROOT / "status-all-4.1.sh")]
    elif command_name == "interfaces":
        script = (
            ". /data/robot-host/robot-env.sh; "
            "rostopic list | grep -E "
            "'^/(cmd_vel|odom|scan|astra_camera/|servo_controllers/|competition/aux_target)' "
            "| sort"
        )
        command = ["/bin/sh", "-lc", script]
    else:
        command = [str(AUX_RELAY), command_name.removeprefix("aux-")]
    if command[0].startswith("/") and not Path(command[0]).exists():
        return emit(
            {"ok": False, "command": command_name, "error": f"missing command: {command[0]}"}
        )
    try:
        completed = run(command, 30)
    except subprocess.TimeoutExpired:
        return emit(
            {"ok": False, "command": command_name, "error": "board command timeout"}
        )
    return emit(parse_last_json(completed, command_name))


def resolve_ipv4(host: str) -> set[str]:
    try:
        address = ipaddress.ip_address(host)
        return {str(address)} if address.version == 4 else set()
    except ValueError:
        pass
    try:
        return {
            result[4][0]
            for result in socket.getaddrinfo(host, None, socket.AF_INET)
        }
    except socket.gaierror:
        return set()


def normalize_ipv4(value: str, label: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise RuntimeError(f"invalid {label} IPv4: {value}") from exc
    if address.version != 4:
        raise RuntimeError(f"{label} address must be IPv4")
    return str(address)


def local_wlan_ipv4() -> str:
    completed = run(["ip", "-4", "-o", "addr", "show", "wlan0"], 5)
    for line in completed.stdout.splitlines():
        fields = line.split()
        if "inet" in fields:
            return normalize_ipv4(
                fields[fields.index("inet") + 1].split("/", 1)[0],
                "local wlan0",
            )
    raise RuntimeError("cannot determine car wlan0 IPv4")


def photo_server_running() -> bool:
    try:
        pid = int(PHOTO_SERVER_PID.read_text(encoding="ascii").strip())
        os.kill(pid, 0)
        command_line = Path(f"/proc/{pid}/cmdline").read_bytes()
        return b"latest_photo_server.py" in command_line
    except (OSError, ValueError):
        return False


def aux_camera_view(args: argparse.Namespace) -> int:
    command_name = "aux-camera-view"
    color_path = AUX_OUTPUT_DIR / "aux-camera-latest-color.jpg"
    if not color_path.is_file():
        return emit(
            {
                "ok": False,
                "command": command_name,
                "error": f"latest photo does not exist: {color_path}",
                "hint": "Capture or connect the auxiliary camera first.",
            }
        )
    if not PHOTO_SERVER.is_file():
        return emit(
            {
                "ok": False,
                "command": command_name,
                "error": f"missing photo server: {PHOTO_SERVER}",
            }
        )
    if not 60 <= args.ttl <= 3600:
        return emit(
            {
                "ok": False,
                "command": command_name,
                "error": "ttl must be within 60..3600 seconds",
            }
        )
    try:
        car_ip = local_wlan_ipv4()
    except RuntimeError as exc:
        return emit({"ok": False, "command": command_name, "error": str(exc)})

    if not photo_server_running():
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        with PHOTO_SERVER_LOG.open("a", encoding="utf-8") as log_stream:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(PHOTO_SERVER),
                    "--directory",
                    str(AUX_OUTPUT_DIR),
                    "--bind",
                    car_ip,
                    "--port",
                    str(PHOTO_SERVER_PORT),
                    "--ttl",
                    str(args.ttl),
                ],
                stdin=subprocess.DEVNULL,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        PHOTO_SERVER_PID.write_text(str(process.pid), encoding="ascii")
        time.sleep(0.5)
        if process.poll() is not None:
            return emit(
                {
                    "ok": False,
                    "command": command_name,
                    "error": "temporary photo viewer failed to start",
                    "log_path": str(PHOTO_SERVER_LOG),
                }
            )

    base_url = f"http://{car_ip}:{PHOTO_SERVER_PORT}"
    return emit(
        {
            "ok": True,
            "command": command_name,
            "expires_in_s": args.ttl,
            "color_url": f"{base_url}/aux-camera-latest-color.jpg",
            "depth_url": f"{base_url}/aux-camera-latest-depth.png",
            "depth_preview_url": (
                f"{base_url}/aux-camera-latest-depth-preview.pgm"
            ),
            "metadata_url": f"{base_url}/aux-camera-latest.json",
        }
    )


def aux_camera_publishers(aux_ip: str) -> dict[str, Any]:
    aux_ip = normalize_ipv4(aux_ip, "auxiliary-board")

    master_uri = os.environ.get("ROS_MASTER_URI", "http://127.0.0.1:11311")
    master = xmlrpc.client.ServerProxy(
        master_uri,
        transport=TimeoutTransport(5.0),
        allow_none=True,
    )
    code, message, state = master.getSystemState("/mclaw_aux_camera")
    if code != 1:
        raise RuntimeError(f"ROS Master getSystemState failed: {message}")
    publishers = dict(state[0])
    details: dict[str, list[dict[str, Any]]] = {}
    errors: list[str] = []
    for topic in (AUX_COLOR_TOPIC, AUX_DEPTH_TOPIC):
        nodes = publishers.get(topic, [])
        topic_details: list[dict[str, Any]] = []
        for node in nodes:
            lookup_code, lookup_message, node_uri = master.lookupNode(
                "/mclaw_aux_camera", node
            )
            host = urlparse(node_uri).hostname if lookup_code == 1 else None
            resolved = sorted(resolve_ipv4(host or ""))
            topic_details.append(
                {
                    "node": node,
                    "node_uri": node_uri if lookup_code == 1 else None,
                    "host": host,
                    "resolved_ipv4": resolved,
                    "matches_aux_ip": aux_ip in resolved,
                    "lookup_error": None if lookup_code == 1 else lookup_message,
                }
            )
        details[topic] = topic_details
        if not topic_details:
            errors.append(f"no publisher for {topic}")
        elif not any(item["matches_aux_ip"] for item in topic_details):
            errors.append(f"publisher for {topic} does not come from {aux_ip}")

    return {
        "ok": not errors,
        "aux_ip": aux_ip,
        "ros_master_uri": master_uri,
        "publishers": details,
        "errors": errors,
    }


def aux_camera(args: argparse.Namespace) -> int:
    command_name = args.command
    try:
        aux_ip = normalize_ipv4(args.aux_ip, "auxiliary-board")
        source = aux_camera_publishers(aux_ip)
    except (OSError, RuntimeError, xmlrpc.client.Error) as exc:
        return emit(
            {
                "ok": False,
                "command": command_name,
                "aux_ip": args.aux_ip,
                "error": str(exc),
            }
        )
    if not source["ok"]:
        return emit(
            {
                **source,
                "command": command_name,
                "returncode": 1,
                "hint": (
                    "Configure the auxiliary board to this car's ROS Master in the "
                    "auxiliary-board terminal, then start Gemini 335."
                ),
            }
        )
    if command_name == "aux-camera-status":
        return emit({**source, "command": command_name})

    if not AUX_RGBD_RECEIVER.is_file():
        return emit(
            {
                "ok": False,
                "command": command_name,
                "error": f"missing receiver: {AUX_RGBD_RECEIVER}",
            }
        )
    try:
        completed = run([str(AUX_RGBD_RECEIVER)], 50)
    except subprocess.TimeoutExpired:
        return emit(
            {
                **source,
                "ok": False,
                "command": command_name,
                "error": "timed out waiting for auxiliary RGB-D frames",
            }
        )
    frame = parse_last_json(completed, command_name)
    return emit(
        {
            **source,
            "ok": bool(source["ok"] and frame.get("ok")),
            "command": command_name,
            "frame": frame,
        }
    )


def color_sorting() -> int:
    command_name = "color-sorting"
    if not COLOR_SORTING_DEMO.is_file():
        return emit(
            {
                "ok": False,
                "command": command_name,
                "error": f"missing demo: {COLOR_SORTING_DEMO}",
            }
        )
    try:
        completed = run([str(COLOR_SORTING_DEMO)], 45)
    except subprocess.TimeoutExpired:
        return emit(
            {"ok": False, "command": command_name, "error": "demo timeout after 45s"}
        )
    if completed.returncode != 0:
        return emit(parse_last_json(completed, command_name))
    try:
        result = json.loads(COLOR_SORTING_RESULT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return emit(
            {"ok": False, "command": command_name, "error": f"cannot read result: {exc}"}
        )
    return emit(
        {
            "ok": bool(result.get("ok")),
            "command": command_name,
            "mode": result.get("mode"),
            "input_fresh": result.get("input_fresh"),
            "frame_skew_s": result.get("frame_skew_s"),
            "detection_count": result.get("detection_count"),
            "recommendation_count": result.get("recommendation_count"),
            "depth_quality_count": result.get("depth_quality_count"),
            "rgbd_complete": result.get("rgbd_complete"),
            "decisions": result.get("decisions", []),
            "annotated_image": result.get("annotated_image"),
            "depth_preview": result.get("depth_preview"),
            "result_json": result.get("result_json"),
            "safety": result.get("safety"),
            "warning": result.get("warning"),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("chassis-status")
    move = subparsers.add_parser("chassis-move")
    move.add_argument("--linear-x", type=float, default=0.0)
    move.add_argument("--linear-y", type=float, default=0.0)
    move.add_argument("--angular-z", type=float, default=0.0)
    move.add_argument("--duration", type=float, required=True)
    subparsers.add_parser("chassis-stop")
    subparsers.add_parser("arm-read")
    arm_set = subparsers.add_parser("arm-set-one")
    arm_set.add_argument("--servo-id", type=int, required=True)
    arm_set.add_argument("--position", type=int, required=True)
    arm_set.add_argument("--allow-large-delta", action="store_true")
    gripper_set = subparsers.add_parser("gripper-set")
    gripper_set.add_argument("--position", type=int, required=True)
    subparsers.add_parser("camera-capture")
    subparsers.add_parser("lidar-status")
    subparsers.add_parser("lidar-scan")
    subparsers.add_parser("health")
    subparsers.add_parser("status")
    subparsers.add_parser("interfaces")
    subparsers.add_parser("aux-start")
    subparsers.add_parser("aux-status")
    subparsers.add_parser("aux-stop")
    for command in (
        "aux-camera-connect",
        "aux-camera-status",
        "aux-camera-capture",
    ):
        aux_camera_parser = subparsers.add_parser(command)
        aux_camera_parser.add_argument("--aux-ip", required=True)
    photo_view = subparsers.add_parser("aux-camera-view")
    photo_view.add_argument("--ttl", type=int, default=600)
    subparsers.add_parser("color-sorting")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command.startswith("chassis-"):
        return chassis(args)
    if args.command.startswith("arm-"):
        return arm(args)
    if args.command == "gripper-set":
        return gripper(args)
    if args.command == "camera-capture":
        return camera_capture()
    if args.command == "aux-camera-view":
        return aux_camera_view(args)
    if args.command.startswith("aux-camera-"):
        return aux_camera(args)
    if args.command.startswith("lidar-"):
        return lidar(args.command)
    if args.command == "color-sorting":
        return color_sorting()
    return board_interface(args.command)


if __name__ == "__main__":
    sys.exit(main())
