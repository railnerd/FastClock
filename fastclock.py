#!/usr/bin/env python3
"""JMRI-compatible Fast Clock MQTT Publisher.

Simulates a fast clock and publishes updates to an MQTT broker.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
import threading
import time

import paho.mqtt.client as mqtt

SECONDS_PER_DAY = 86_400

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fastclock")


@dataclass(frozen=True)
class ClockSnapshot:
    """Immutable snapshot of the clock state at a specific moment."""

    time_str: str
    is_running: bool
    rate: float
    minute_index: int


class FastClock:
    """Thread-safe simulation of a fast clock with configurable speed and time wrapping."""

    def __init__(self, start_time: str = "08:00", rate: float = 4.0) -> None:
        self._lock = threading.RLock()
        self._rate = rate
        self._running = True
        self._sim_seconds = self._parse_time(start_time)
        self._last_mono = time.monotonic()

    @staticmethod
    def _parse_time(time_str: str) -> float:
        """Parses 'H:MM', 'HH:MM', or 'HH:MM:SS' into seconds from midnight."""
        try:
            parts = [int(p) for p in time_str.strip().split(":")]
            if len(parts) == 2:
                h, m = parts
                s = 0
            elif len(parts) == 3:
                h, m, s = parts
            else:
                raise ValueError("Expected H:MM or HH:MM:SS")
            if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60):
                raise ValueError("Hours (0-23), minutes (0-59), or seconds (0-59) out of range")
            return float(h * 3600 + m * 60 + s)
        except Exception as err:
            raise ValueError(f"Invalid time format '{time_str}': {err}") from err

    def _sync(self) -> None:
        """Advances simulation seconds based on monotonic time elapsed."""
        now = time.monotonic()
        if self._running:
            elapsed = now - self._last_mono
            self._sim_seconds = (self._sim_seconds + elapsed * self._rate) % SECONDS_PER_DAY
        self._last_mono = now

    def start(self) -> None:
        with self._lock:
            self._sync()
            self._running = True

    def stop(self) -> None:
        with self._lock:
            self._sync()
            self._running = False

    def set_rate(self, rate: float) -> None:
        if rate < 0:
            raise ValueError("Clock rate cannot be negative")
        with self._lock:
            self._sync()
            self._rate = rate

    def set_time(self, time_str: str) -> None:
        new_seconds = self._parse_time(time_str)
        with self._lock:
            self._sync()
            self._sim_seconds = new_seconds

    def snapshot(self) -> ClockSnapshot:
        """Returns an atomic snapshot of current time, running state, and rate."""
        with self._lock:
            self._sync()
            total_minutes = int(self._sim_seconds // 60)
            hours, minutes = divmod(total_minutes, 60)
            return ClockSnapshot(
                time_str=f"{hours % 24:02d}:{minutes:02d}",
                is_running=self._running,
                rate=self._rate,
                minute_index=total_minutes,
            )


class FastClockMQTTService:
    """Manages MQTT communication and command dispatching for FastClock."""

    def __init__(
        self,
        clock: FastClock,
        broker: str = "localhost",
        port: int = 1883,
        prefix: str = "layout/clock",
    ) -> None:
        self.clock = clock
        self.broker = broker
        self.port = port
        self.prefix = prefix.rstrip("/")
        self._last_published_minute: int | None = None

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="PiFastClock",
            userdata=self,
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        logger.info("Connected to MQTT broker (reason code: %s)", reason_code)
        client.subscribe(f"{self.prefix}/cmd")
        self.publish_state(force=True)

    def _on_message(self, client, userdata, msg) -> None:
        payload = msg.payload.decode("utf-8", errors="replace").strip()
        parts = payload.split(maxsplit=1)
        if not parts:
            return

        cmd = parts[0].upper()
        arg = parts[1] if len(parts) > 1 else ""

        handlers = {
            "START": lambda _: self.clock.start(),
            "STOP": lambda _: self.clock.stop(),
            "RATE": lambda a: self.clock.set_rate(float(a)),
            "SET": lambda a: self.clock.set_time(a),
        }

        handler = handlers.get(cmd)
        if not handler:
            logger.warning("Unrecognized command: %s", cmd)
            return

        try:
            handler(arg)
        except ValueError as err:
            logger.warning("Failed to execute '%s': %s", payload, err)
            return

        self.publish_state(force=True)

    def publish_state(self, force: bool = False) -> None:
        snapshot = self.clock.snapshot()
        if not (force or snapshot.minute_index != self._last_published_minute):
            return

        self._last_published_minute = snapshot.minute_index
        topics = (
            ("time", snapshot.time_str),
            ("state", "ACTIVE" if snapshot.is_running else "INACTIVE"),
            ("rate", f"{snapshot.rate:.2f}"),
        )
        for subtopic, value in topics:
            self.client.publish(f"{self.prefix}/{subtopic}", value, retain=True)

    def run(self, poll_interval: float = 0.2) -> None:
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()
        logger.info("FastClock started (Broker: %s:%d, Prefix: %s)", self.broker, self.port, self.prefix)
        try:
            while True:
                self.publish_state()
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            logger.info("Stopping FastClock service...")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("FastClock service stopped.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JMRI-compatible Fast Clock MQTT Publisher")
    parser.add_argument("--broker", default="localhost", help="MQTT broker address (default: localhost)")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port (default: 1883)")
    parser.add_argument("--prefix", default="layout/clock", help="MQTT topic prefix (default: layout/clock)")
    parser.add_argument("--start", default="08:00", help="Initial clock time in HH:MM (default: 08:00)")
    parser.add_argument("--rate", type=float, default=4.0, help="Clock speed multiplier (default: 4.0)")
    parser.add_argument("--poll-interval", type=float, default=0.2, help="Polling interval in seconds (default: 0.2)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    clock = FastClock(start_time=args.start, rate=args.rate)
    service = FastClockMQTTService(clock=clock, broker=args.broker, port=args.port, prefix=args.prefix)
    service.run(poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
