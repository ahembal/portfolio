"""
locustfile.py — PCam inference load test
=========================================
Generates a steady stream of /predict requests using a synthetic 96×96 PNG
patch. The goal is to push average CPU utilisation above the HPA target (60%
of 250m = 150m millicores) so we can observe the autoscaler adding replicas.

Usage (from repo root):
    locust -f p1-pcam-deployment/load-test/locustfile.py \
           --host http://localhost:18080 \
           --headless -u 10 -r 2 --run-time 3m
"""

import io
import struct
import zlib

from locust import HttpUser, task, between


def _make_patch_png(width: int = 96, height: int = 96) -> bytes:
    """Build a minimal valid 96×96 RGB PNG using only stdlib — no Pillow needed."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = b""
    for y in range(height):
        raw += b"\x00"  # filter type: None
        for x in range(width):
            raw += bytes([(x * 2) % 256, (y * 2) % 256, 128])

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr_data)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return png


# Pre-build the patch once; reuse for every request to avoid CPU overhead
# inside the load generator skewing the measurement.
_PATCH_PNG = _make_patch_png()


class PcamUser(HttpUser):
    """
    Simulates a user sending pathology patch images for inference.
    wait_time is intentionally short (0.1–0.5 s) so each virtual user
    sends ~2–10 requests/s, creating meaningful CPU load.
    """

    wait_time = between(0.1, 0.5)

    @task
    def predict(self) -> None:
        self.client.post(
            "/predict",
            files={"file": ("patch.png", io.BytesIO(_PATCH_PNG), "image/png")},
            name="/predict",
        )

    @task(1)
    def health(self) -> None:
        """Occasional health checks — low weight so /predict dominates."""
        self.client.get("/health", name="/health")
