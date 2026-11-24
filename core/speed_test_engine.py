"""Production speed test engine with multi-threaded parallel streaming and ultra-low latency probing.

Measures:
1. Low-latency idle ping, jitter, and packet loss (using ICMP/TCP edge probes matching line latency).
2. Multi-threaded download throughput (saturating line bandwidth up to multi-hundred Mbps).
3. Download bufferbloat (loaded download latency via background non-blocking probes).
4. Multi-threaded persistent upload throughput (saturating upstream bandwidth).
5. Upload bufferbloat (loaded upload latency).
6. Connection quality ratings for Streaming, Gaming, and Video Calls.
"""

from __future__ import annotations

import collections
import datetime
import http.client
import logging
import re
import socket
import ssl
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger("FreeNetMeter.SpeedTest")

# Edge targets for accurate ping and jitter measurement
PRIMARY_PING_HOSTS = ["speedtest.net", "1.1.1.1", "8.8.8.8"]

# High-capacity speed test endpoints (Cloudflare edge CDN)
SPEED_TEST_HOST = "speed.cloudflare.com"
SPEED_TEST_DOWN_PATH = "/__down?bytes=50000000"  # 50 MB payload tier
SPEED_TEST_DOWN_FALLBACK_PATH = "/__down?bytes=25000000"
SPEED_TEST_UP_PATH = "/__up"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 FreeNetMeter/1.0"
)


@dataclass(frozen=True)
class SpeedTestSamplePoint:
    """Point in time sample for live graphing."""

    elapsed_s: float
    speed_mbps: float
    latency_ms: float
    stage: str


@dataclass(frozen=True)
class SpeedTestResult:
    """Comprehensive test outcome metrics."""

    timestamp_iso: str
    download_mbps: float
    upload_mbps: float
    idle_ping_ms: float
    jitter_ms: float
    loaded_down_ping_ms: float
    loaded_up_ping_ms: float
    packet_loss_pct: float
    bufferbloat_grade: str
    streaming_rating: str
    gaming_rating: str
    video_calls_rating: str

    def to_dict(self) -> dict[str, str | float]:
        return {
            "timestamp": self.timestamp_iso,
            "download_mbps": self.download_mbps,
            "upload_mbps": self.upload_mbps,
            "idle_ping_ms": self.idle_ping_ms,
            "jitter_ms": self.jitter_ms,
            "loaded_down_ping_ms": self.loaded_down_ping_ms,
            "loaded_up_ping_ms": self.loaded_up_ping_ms,
            "packet_loss_pct": self.packet_loss_pct,
            "bufferbloat_grade": self.bufferbloat_grade,
            "streaming_rating": self.streaming_rating,
            "gaming_rating": self.gaming_rating,
            "video_calls_rating": self.video_calls_rating,
        }


def calculate_bufferbloat_grade(idle_ms: float, loaded_down_ms: float) -> str:
    """Grade network responsiveness under load according to bufferbloat delta."""
    delta = max(0.0, loaded_down_ms - idle_ms)
    if delta < 5.0:
        return "A+"
    elif delta < 15.0:
        return "A"
    elif delta < 35.0:
        return "B"
    elif delta < 75.0:
        return "C"
    else:
        return "D"


def rate_streaming(down_mbps: float, ping_ms: float) -> str:
    """Rate streaming quality capabilities."""
    if down_mbps >= 25.0 and ping_ms <= 60.0:
        return "4K Ultra HD (Excellent)"
    elif down_mbps >= 10.0:
        return "1080p Full HD (Good)"
    elif down_mbps >= 4.0:
        return "720p HD (Fair)"
    else:
        return "SD (Basic)"


def rate_gaming(ping_ms: float, jitter_ms: float, loss_pct: float) -> str:
    """Rate interactive online gaming experience."""
    if loss_pct > 2.0:
        return "Poor (Packet Loss)"
    if ping_ms <= 25.0 and jitter_ms <= 8.0:
        return "Elite (<25ms)"
    elif ping_ms <= 50.0 and jitter_ms <= 12.0:
        return "Great (<50ms)"
    elif ping_ms <= 85.0:
        return "Acceptable (<85ms)"
    else:
        return "High Latency (Laggy)"


def rate_video_calls(down_mbps: float, up_mbps: float, ping_ms: float) -> str:
    """Rate video conferencing reliability."""
    if down_mbps >= 6.0 and up_mbps >= 3.0 and ping_ms <= 70.0:
        return "Smooth HD (Crystal Clear)"
    elif down_mbps >= 2.5 and up_mbps >= 1.0 and ping_ms <= 120.0:
        return "Good (Standard HD)"
    else:
        return "Choppy / Audio Only"


def probe_single_ping(host: str = "speedtest.net") -> Optional[float]:
    """Measure true round-trip ping time in ms using ICMP ping with TCP connect fallback."""
    # 1. Native ICMP Ping (reflects exact line ping as reported by Ookla and Windows ping)
    try:
        proc = subprocess.run(
            ["ping", "-n", "1", "-w", "700", host],
            capture_output=True,
            text=True,
            timeout=1.0,
        )
        match = re.search(r"time[=<](\d+)ms", proc.stdout)
        if match:
            return float(match.group(1))
    except Exception:
        pass

    # 2. Fast TCP connect fallback (SYN/ACK RTT without TLS / HTTP application overhead)
    for port in (80, 443):
        try:
            t0 = time.perf_counter()
            s = socket.create_connection((host, port), timeout=0.8)
            rtt = (time.perf_counter() - t0) * 1000.0
            s.close()
            return rtt
        except Exception:
            continue

    return None


class SpeedTestWorker(QThread):
    """Background worker executing ping, multi-stream download, multi-stream upload, and stability tests."""

    progress_updated = pyqtSignal(str, float, float, float)  # stage, pct, speed_mbps, ping_ms
    sample_recorded = pyqtSignal(object)  # SpeedTestSamplePoint
    test_finished = pyqtSignal(object)  # SpeedTestResult
    test_failed = pyqtSignal(str)
    test_cancelled = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._is_cancelled: bool = False
        self._stop_event = threading.Event()

    def cancel(self) -> None:
        """Signal worker to abort execution immediately."""
        self._is_cancelled = True
        self._stop_event.set()

    def run(self) -> None:
        """Execute complete multi-stage test suite."""
        self._is_cancelled = False
        self._stop_event.clear()
        start_time = time.time()

        try:
            # 1. PING & JITTER STAGE
            self.progress_updated.emit("Measuring Latency...", 5.0, 0.0, 0.0)
            ping_samples: List[float] = []
            loss_count = 0
            total_probes = 8

            for i in range(total_probes):
                if self._is_cancelled:
                    self.test_cancelled.emit()
                    return

                # Probe primary host, fallback to secondary if needed
                rtt = None
                for host in PRIMARY_PING_HOSTS:
                    rtt = probe_single_ping(host)
                    if rtt is not None:
                        break

                if rtt is not None:
                    ping_samples.append(rtt)
                    self.sample_recorded.emit(
                        SpeedTestSamplePoint(
                            elapsed_s=time.time() - start_time,
                            speed_mbps=0.0,
                            latency_ms=rtt,
                            stage="ping",
                        )
                    )
                else:
                    loss_count += 1

                pct = 5.0 + (i + 1) / total_probes * 15.0
                curr_ping = ping_samples[-1] if ping_samples else 0.0
                self.progress_updated.emit("Measuring Latency...", pct, 0.0, curr_ping)
                time.sleep(0.06)

            if not ping_samples:
                self.test_failed.emit("Failed to reach speed test servers. Check your connection.")
                return

            idle_ping = statistics.median(ping_samples)
            if len(ping_samples) > 1:
                jitter = statistics.mean(
                    abs(ping_samples[i] - ping_samples[i - 1]) for i in range(1, len(ping_samples))
                )
            else:
                jitter = 1.0

            packet_loss_pct = (loss_count / total_probes) * 100.0

            # 2. MULTI-STREAM DOWNLOAD STAGE
            self.progress_updated.emit("Testing Download...", 20.0, 0.0, idle_ping)
            down_mbps, loaded_down_ping = self._run_download_stage(start_time, idle_ping)
            if self._is_cancelled:
                self.test_cancelled.emit()
                return

            # 3. MULTI-STREAM UPLOAD STAGE
            self.progress_updated.emit("Testing Upload...", 60.0, down_mbps, idle_ping)
            up_mbps, loaded_up_ping = self._run_upload_stage(start_time, idle_ping)
            if self._is_cancelled:
                self.test_cancelled.emit()
                return

            # 4. RATINGS & RESULT
            bufferbloat_grade = calculate_bufferbloat_grade(idle_ping, loaded_down_ping)
            streaming_rating = rate_streaming(down_mbps, idle_ping)
            gaming_rating = rate_gaming(idle_ping, jitter, packet_loss_pct)
            video_rating = rate_video_calls(down_mbps, up_mbps, idle_ping)

            result = SpeedTestResult(
                timestamp_iso=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                download_mbps=round(down_mbps, 2),
                upload_mbps=round(up_mbps, 2),
                idle_ping_ms=round(idle_ping, 1),
                jitter_ms=round(jitter, 1),
                loaded_down_ping_ms=round(loaded_down_ping, 1),
                loaded_up_ping_ms=round(loaded_up_ping, 1),
                packet_loss_pct=round(packet_loss_pct, 1),
                bufferbloat_grade=bufferbloat_grade,
                streaming_rating=streaming_rating,
                gaming_rating=gaming_rating,
                video_calls_rating=video_rating,
            )

            self.progress_updated.emit("Finished", 100.0, down_mbps, idle_ping)
            self.test_finished.emit(result)

        except Exception as exc:
            logger.error("Speed test encountered unexpected error: %s", exc)
            self.test_failed.emit(f"Test interrupted: {exc}")

    def _run_download_stage(self, test_start_time: float, idle_ping: float) -> Tuple[float, float]:
        """Download using multiple parallel connections to fully saturate line bandwidth."""
        num_workers = 4
        chunk_read_size = 131072  # 128 KB
        total_downloaded_bytes = 0
        loaded_pings: List[float] = []
        dl_stop = threading.Event()

        # Dedicated non-blocking background probe for bufferbloat
        def ping_probe_loop():
            while not dl_stop.is_set() and not self._is_cancelled:
                p = probe_single_ping(PRIMARY_PING_HOSTS[0])
                if p is not None:
                    loaded_pings.append(p)
                time.sleep(0.6)

        ping_thread = threading.Thread(target=ping_probe_loop, daemon=True)
        ping_thread.start()

        # Multi-connection download workers
        def download_worker():
            nonlocal total_downloaded_bytes
            target_urls = [
                f"https://{SPEED_TEST_HOST}{SPEED_TEST_DOWN_PATH}",
                f"https://{SPEED_TEST_HOST}{SPEED_TEST_DOWN_FALLBACK_PATH}",
            ]
            for url in target_urls:
                if dl_stop.is_set() or self._is_cancelled:
                    break
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(req, timeout=10.0) as resp:
                        while not dl_stop.is_set() and not self._is_cancelled:
                            data = resp.read(chunk_read_size)
                            if not data:
                                break
                            total_downloaded_bytes += len(data)
                except Exception as exc:
                    logger.debug("Download stream worker retry: %s", exc)
                    continue

        workers = [
            threading.Thread(target=download_worker, daemon=True)
            for _ in range(num_workers)
        ]
        t_stage_start = time.perf_counter()
        for w in workers:
            w.start()

        # Main QThread sampling loop (5.5 seconds active duration)
        stage_duration = 5.5
        history: Deque[Tuple[float, int]] = collections.deque()
        speed_samples: List[float] = []

        while not self._is_cancelled:
            now = time.perf_counter()
            elapsed_stage = now - t_stage_start
            if elapsed_stage >= stage_duration:
                break

            cur_bytes = total_downloaded_bytes
            history.append((now, cur_bytes))

            # Maintain a 450ms sliding window for smooth needle gauge display
            while history and (now - history[0][0]) > 0.45:
                history.popleft()

            if len(history) >= 2:
                dt = history[-1][0] - history[0][0]
                db = history[-1][1] - history[0][1]
                instant_mbps = (db * 8.0) / (dt * 1_000_000.0) if dt > 0 else 0.0
            else:
                instant_mbps = (cur_bytes * 8.0) / (max(0.001, elapsed_stage) * 1_000_000.0)

            speed_samples.append(instant_mbps)

            curr_loaded_ping = loaded_pings[-1] if loaded_pings else idle_ping
            elapsed_total = time.time() - test_start_time
            self.sample_recorded.emit(
                SpeedTestSamplePoint(
                    elapsed_s=elapsed_total,
                    speed_mbps=instant_mbps,
                    latency_ms=curr_loaded_ping,
                    stage="download",
                )
            )

            pct = 20.0 + min(40.0, (elapsed_stage / stage_duration) * 40.0)
            self.progress_updated.emit("Testing Download...", pct, instant_mbps, idle_ping)
            time.sleep(0.08)

        dl_stop.set()
        for w in workers:
            w.join(timeout=0.3)

        total_stage_time = max(0.001, time.perf_counter() - t_stage_start)
        raw_avg_down = (total_downloaded_bytes * 8.0) / (total_stage_time * 1_000_000.0)

        # Standard speedtest algorithm (Ookla / NDT7): exclude initial 20% TCP slow-start ramp
        if len(speed_samples) > 10:
            sustained_samples = speed_samples[int(len(speed_samples) * 0.20):]
            sustained_down = statistics.mean(
                sorted(sustained_samples)[int(len(sustained_samples) * 0.15):]
            )
        else:
            sustained_down = raw_avg_down

        final_down_mbps = max(sustained_down, raw_avg_down)
        avg_loaded_ping = (
            statistics.mean(loaded_pings) if loaded_pings else (idle_ping * 1.15)
        )
        return final_down_mbps, avg_loaded_ping

    def _run_upload_stage(self, test_start_time: float, idle_ping: float) -> Tuple[float, float]:
        """Upload using multiple concurrent persistent HTTPS connections to saturate upstream bandwidth."""
        num_workers = 6
        payload_size = 262144  # 256 KB chunks for high-frequency continuous transfer
        payload = b"0" * payload_size
        total_uploaded_bytes = 0
        loaded_pings: List[float] = []
        up_stop = threading.Event()
        ssl_ctx = ssl.create_default_context()

        # Dedicated non-blocking background probe for bufferbloat
        def ping_probe_loop():
            while not up_stop.is_set() and not self._is_cancelled:
                p = probe_single_ping(PRIMARY_PING_HOSTS[0])
                if p is not None:
                    loaded_pings.append(p)
                time.sleep(0.6)

        ping_thread = threading.Thread(target=ping_probe_loop, daemon=True)
        ping_thread.start()

        # Multi-connection persistent upload workers
        def upload_worker():
            nonlocal total_uploaded_bytes
            while not up_stop.is_set() and not self._is_cancelled:
                try:
                    conn = http.client.HTTPSConnection(
                        SPEED_TEST_HOST, timeout=8.0, context=ssl_ctx
                    )
                    while not up_stop.is_set() and not self._is_cancelled:
                        conn.request(
                            "POST",
                            SPEED_TEST_UP_PATH,
                            body=payload,
                            headers={
                                "Content-Type": "application/octet-stream",
                                "User-Agent": USER_AGENT,
                            },
                        )
                        resp = conn.getresponse()
                        resp.read(32)
                        total_uploaded_bytes += payload_size
                except Exception as exc:
                    logger.debug("Upload stream worker retry: %s", exc)
                    time.sleep(0.05)

        workers = [
            threading.Thread(target=upload_worker, daemon=True)
            for _ in range(num_workers)
        ]
        t_stage_start = time.perf_counter()
        for w in workers:
            w.start()

        # Main QThread sampling loop (5.5 seconds active duration)
        stage_duration = 5.5
        history: Deque[Tuple[float, int]] = collections.deque()
        speed_samples: List[float] = []

        while not self._is_cancelled:
            now = time.perf_counter()
            elapsed_stage = now - t_stage_start
            if elapsed_stage >= stage_duration:
                break

            cur_bytes = total_uploaded_bytes
            history.append((now, cur_bytes))

            # Maintain a 450ms sliding window for smooth needle gauge display
            while history and (now - history[0][0]) > 0.45:
                history.popleft()

            if len(history) >= 2:
                dt = history[-1][0] - history[0][0]
                db = history[-1][1] - history[0][1]
                instant_mbps = (db * 8.0) / (dt * 1_000_000.0) if dt > 0 else 0.0
            else:
                instant_mbps = (cur_bytes * 8.0) / (max(0.001, elapsed_stage) * 1_000_000.0)

            speed_samples.append(instant_mbps)

            curr_loaded_ping = loaded_pings[-1] if loaded_pings else idle_ping
            elapsed_total = time.time() - test_start_time
            self.sample_recorded.emit(
                SpeedTestSamplePoint(
                    elapsed_s=elapsed_total,
                    speed_mbps=instant_mbps,
                    latency_ms=curr_loaded_ping,
                    stage="upload",
                )
            )

            pct = 60.0 + min(38.0, (elapsed_stage / stage_duration) * 38.0)
            self.progress_updated.emit("Testing Upload...", pct, instant_mbps, idle_ping)
            time.sleep(0.08)

        up_stop.set()
        for w in workers:
            w.join(timeout=0.3)

        total_stage_time = max(0.001, time.perf_counter() - t_stage_start)
        raw_avg_up = (total_uploaded_bytes * 8.0) / (total_stage_time * 1_000_000.0)

        # Standard speedtest algorithm: exclude ramp-up, compute sustained throughput
        if len(speed_samples) > 10:
            sustained_samples = speed_samples[int(len(speed_samples) * 0.20):]
            sustained_up = statistics.mean(
                sorted(sustained_samples)[int(len(sustained_samples) * 0.15):]
            )
        else:
            sustained_up = raw_avg_up

        final_up_mbps = max(sustained_up, raw_avg_up)
        avg_loaded_up_ping = (
            statistics.mean(loaded_pings) if loaded_pings else (idle_ping * 1.15)
        )
        return final_up_mbps, avg_loaded_up_ping
