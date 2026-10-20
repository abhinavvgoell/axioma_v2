"""Docker-backed abuse checks; skipped until Docker and the prebuilt image are ready."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from axioma_worker.adapters import get_adapter
from axioma_worker.sandbox import DockerSandbox


def _docker_runtime_ready() -> tuple[bool, str]:
    docker = shutil.which("docker")
    if docker is None:
        return False, "Docker CLI is not installed"
    try:
        daemon = subprocess.run(
            [docker, "info"], capture_output=True, timeout=5, check=False
        )
        if daemon.returncode != 0:
            return False, "Docker daemon is unavailable"
        image = subprocess.run(
            [docker, "image", "inspect", "python:3.13-slim"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if image.returncode != 0:
            return False, "Prebuilt python:3.13-slim image is not available"
    except (OSError, subprocess.SubprocessError):
        return False, "Docker runtime could not be inspected"
    return True, ""


_DOCKER_READY, _DOCKER_REASON = _docker_runtime_ready()
pytestmark = pytest.mark.skipif(not _DOCKER_READY, reason=_DOCKER_REASON)


def _run(source: str, *, timeout_seconds: float = 10, output_limit_bytes: int = 1024 * 1024):
    return DockerSandbox(
        timeout_seconds=timeout_seconds, output_limit_bytes=output_limit_bytes
    ).run(get_adapter("python"), source)


def test_python_runs_without_network_and_cannot_write_to_root_filesystem():
    result = _run(
        """import socket
try:
    socket.create_connection(("1.1.1.1", 80), timeout=1)
    print("network-available")
except OSError:
    print("network-blocked")
try:
    open("/axioma-readonly-probe", "w").write("unexpected")
    print("root-writable")
except OSError:
    print("root-read-only")
"""
    )

    assert result.exit_code == 0
    assert "network-blocked" in result.stdout
    assert "root-read-only" in result.stdout


def test_infinite_loop_hits_wall_clock_timeout():
    result = _run("while True: pass\n", timeout_seconds=1)

    assert result.timed_out


def test_large_output_is_truncated_to_the_configured_limit():
    result = _run("print('x' * 2_000_000)\n", output_limit_bytes=4096)

    assert result.exit_code == 0
    assert result.output_limited
    assert len(result.stdout.encode("utf-8")) == 4096


def test_container_observes_memory_and_process_limits():
    result = _run(
        """from pathlib import Path
print(Path("/sys/fs/cgroup/memory.max").read_text().strip())
print(Path("/sys/fs/cgroup/pids.max").read_text().strip())
"""
    )

    assert result.exit_code == 0
    limits = result.stdout.splitlines()
    assert limits == ["268435456", "64"]
