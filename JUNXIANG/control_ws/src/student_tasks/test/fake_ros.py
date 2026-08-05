"""Deterministic non-network ROS facade and message fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class FakeVector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class FakeTwist:
    linear: FakeVector3 = field(default_factory=FakeVector3)
    angular: FakeVector3 = field(default_factory=FakeVector3)


@dataclass(frozen=True)
class FakeStamp:
    seconds: float

    def to_sec(self) -> float:
        return self.seconds


@dataclass(frozen=True)
class FakeHeader:
    stamp: FakeStamp
    frame_id: str = ""


@dataclass(frozen=True)
class FakeLaserScan:
    header: FakeHeader
    angle_min: float
    angle_increment: float
    range_min: float
    range_max: float
    ranges: tuple[object, ...]


@dataclass(frozen=True)
class FakeString:
    data: str


@dataclass(frozen=True)
class FakeBool:
    data: bool


class FakePublisher:
    def __init__(self, facade: "FakeRosFacade", topic: str) -> None:
        self.facade = facade
        self.topic = topic
        self.messages: list[object] = []

    def publish(self, message: object) -> None:
        self.facade.publish_attempts += 1
        if self.facade.fail_publish_at == self.facade.publish_attempts:
            raise RuntimeError("fake publish failure")
        self.messages.append(message)


@dataclass(frozen=True)
class FakeSubscription:
    topic: str
    callback: Callable[[object], None]


class FakeRosFacade:
    """All state is explicit; no socket, ROS package, or wall-clock access."""

    def __init__(
        self,
        *,
        master_up: bool = True,
        node_name: str = "/jx_control_test",
        wall_time: float = 1_000.0,
    ) -> None:
        self.master_up = master_up
        self.node_name = node_name
        self.wall_seconds = wall_time
        self.monotonic_seconds = 0.0
        self.initialized_names: list[str] = []
        self.publisher_nodes: dict[str, list[str]] = {}
        self.subscriber_nodes: dict[str, list[str]] = {}
        self.created_publishers: list[FakePublisher] = []
        self.subscriptions: list[FakeSubscription] = []
        self.logs: list[tuple[str, str]] = []
        self.shutdown = False
        self.fail_graph = False
        self.fail_publisher_creation = False
        self.fail_publish_at: int | None = None
        self.publish_attempts = 0

    def initialize(self, node_name: str) -> None:
        self.initialized_names.append(node_name)

    def master_available(self) -> bool:
        return self.master_up

    def current_node_name(self) -> str:
        return self.node_name

    def publishers(self, topic: str) -> tuple[str, ...]:
        if self.fail_graph:
            raise RuntimeError("fake graph failure")
        return tuple(self.publisher_nodes.get(topic, ()))

    def subscribers(self, topic: str) -> tuple[str, ...]:
        if self.fail_graph:
            raise RuntimeError("fake graph failure")
        return tuple(self.subscriber_nodes.get(topic, ()))

    def create_publisher(self, topic: str) -> FakePublisher:
        if self.fail_publisher_creation:
            raise RuntimeError("fake publisher creation failure")
        publisher = FakePublisher(self, topic)
        self.created_publishers.append(publisher)
        self.publisher_nodes.setdefault(topic, []).append(self.node_name)
        return publisher

    def subscribe(
        self,
        topic: str,
        callback: Callable[[object], None],
        message_kind: str = "string",
    ) -> FakeSubscription:
        if message_kind not in {"laser_scan", "string", "bool"}:
            raise ValueError("unsupported fake message kind")
        subscription = FakeSubscription(topic, callback)
        self.subscriptions.append(subscription)
        return subscription

    def emit(self, topic: str, message: object) -> None:
        for subscription in tuple(self.subscriptions):
            if subscription.topic == topic:
                subscription.callback(message)

    def make_twist(self, linear_x: float, linear_y: float, angular_z: float) -> FakeTwist:
        message = FakeTwist()
        message.linear.x = linear_x
        message.linear.y = linear_y
        message.angular.z = angular_z
        return message

    def monotonic(self) -> float:
        return self.monotonic_seconds

    def source_time(self) -> float:
        return self.wall_seconds

    def sleep(self, duration_s: float) -> None:
        self.monotonic_seconds += float(duration_s)
        self.wall_seconds += float(duration_s)

    def is_shutdown(self) -> bool:
        return self.shutdown

    def log(self, level: str, message: str) -> None:
        message.encode("ascii")
        self.logs.append((level, message))
