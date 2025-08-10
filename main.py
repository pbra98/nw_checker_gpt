"""Network diagnostics helper.

This module pings a collection of common websites and performs a traceroute
for each in order to identify potential network bottlenecks.

The primary entry point is :func:`check_common_sites` which returns a mapping
of each target host to its ping time, traceroute hop information and any hops
that appear to be problematic.
"""

from __future__ import annotations

import platform
import re
import subprocess
from typing import Dict, Iterable, List, Optional, Tuple


# 20 well‑known sites to use for connectivity checks. These can be adjusted to
# suit particular environments if necessary.
COMMON_SITES: List[str] = [
    "google.com",
    "facebook.com",
    "amazon.com",
    "apple.com",
    "netflix.com",
    "microsoft.com",
    "github.com",
    "reddit.com",
    "cloudflare.com",
    "yahoo.com",
    "bing.com",
    "duckduckgo.com",
    "baidu.com",
    "linkedin.com",
    "instagram.com",
    "twitter.com",
    "wikipedia.org",
    "tiktok.com",
    "snapchat.com",
    "whatsapp.com",
]


def _run_command(cmd: Iterable[str]) -> str:
    """Execute *cmd* and return its combined output as text.

    The command is executed without raising an exception if it exits with a
    non‑zero status. The caller is responsible for interpreting the results.
    """

    completed = subprocess.run(
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return completed.stdout


def ping_site(site: str, count: int = 1, timeout: int = 1) -> Optional[float]:
    """Ping *site* and return the average round‑trip time in milliseconds.

    If the host cannot be reached, ``None`` is returned.
    """

    is_windows = platform.system().lower() == "windows"
    if is_windows:
        cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), site]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout), site]

    output = _run_command(cmd)

    if is_windows:
        match = re.search(r"Average = (\d+(?:\.\d+)?)ms", output)
    else:
        match = re.search(r"= [^/]+/([0-9.]+)/", output)

    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def trace_site(site: str, max_hops: int = 20) -> List[Tuple[int, float]]:
    """Run a traceroute to *site* and return a list of hop latencies."""

    is_windows = platform.system().lower() == "windows"
    tracer = "tracert" if is_windows else "traceroute"
    if is_windows:
        cmd = [tracer, "-h", str(max_hops), site]
    else:
        cmd = [tracer, "-m", str(max_hops), site]
    output = _run_command(cmd)

    hops: List[Tuple[int, float]] = []
    for line in output.splitlines():
        # Match the hop number and the first latency reported on that line.
        match = re.match(r"\s*(\d+)\s+.*?((?:<)?\d+(?:\.\d+)?)\s*ms", line)
        if match:
            hop = int(match.group(1))
            latency = float(match.group(2).lstrip("<"))
            hops.append((hop, latency))
    return hops


def detect_bottlenecks(
    hops: Iterable[Tuple[int, float]],
    threshold: float = 100.0,
    delta: float = 50.0,
) -> List[Tuple[int, float, str]]:
    """Identify hops whose latency suggests a bottleneck.

    A hop is flagged if its latency exceeds ``threshold`` or if the increase in
    latency from the previous hop is greater than ``delta`` milliseconds.
    Returns a list of tuples ``(hop_number, latency_ms, reason)``.
    """

    bottlenecks: List[Tuple[int, float, str]] = []
    previous: Optional[float] = None
    for hop, latency in hops:
        if latency > threshold:
            bottlenecks.append((hop, latency, "high latency"))
        if previous is not None and latency - previous > delta:
            bottlenecks.append((hop, latency, "sudden increase"))
        previous = latency
    return bottlenecks


def check_common_sites() -> Dict[str, Dict[str, object]]:
    """Ping the common sites list and examine traceroute for bottlenecks.

    Returns a dictionary mapping each site to a dictionary containing:

    ``ping_ms``: Average ping round‑trip time in milliseconds (``None`` if the
    ping failed).
    ``hops``: List of ``(hop_number, latency_ms)`` tuples from traceroute.
    ``bottlenecks``: List of problematic hops as identified by
    :func:`detect_bottlenecks`.
    """

    results: Dict[str, Dict[str, object]] = {}
    for site in COMMON_SITES:
        ping_ms = ping_site(site)
        hops = trace_site(site)
        bottlenecks = detect_bottlenecks(hops)
        results[site] = {
            "ping_ms": ping_ms,
            "hops": hops,
            "bottlenecks": bottlenecks,
        }
    return results


if __name__ == "__main__":
    diagnostics = check_common_sites()
    for target, info in diagnostics.items():
        print(target)
        if info["ping_ms"] is not None:
            print(f"  Ping: {info['ping_ms']:.2f} ms")
        else:
            print("  Ping: failed")

        if info["bottlenecks"]:
            print("  Potential bottlenecks detected:")
            for hop, latency, reason in info["bottlenecks"]:
                print(f"    Hop {hop} - {latency:.2f} ms ({reason})")
        else:
            print("  No significant bottlenecks detected.")
