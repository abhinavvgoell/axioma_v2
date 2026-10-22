from __future__ import annotations

import io
import os
import shutil
import subprocess
import tarfile
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath

from axioma_worker.adapters import LanguageAdapter


class SandboxError(RuntimeError):
    """Base error for sandbox setup and execution failures."""


class SandboxUnavailable(SandboxError):
    """Docker or a required prebuilt language image is unavailable."""


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    cancelled: bool = False
    output_limited: bool = False


class DockerSandbox:
    def __init__(
        self,
        timeout_seconds: float = 10,
        source_limit_bytes: int = 64 * 1024,
        output_limit_bytes: int = 1024 * 1024,
        docker_binary: str = "docker",
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.source_limit_bytes = source_limit_bytes
        self.output_limit_bytes = output_limit_bytes
        self.docker_binary = self._resolve_docker_binary(docker_binary)

    @staticmethod
    def _resolve_docker_binary(docker_binary: str) -> str:
        """Find Docker Desktop on Windows even when its CLI directory is not on PATH."""
        resolved = shutil.which(docker_binary)
        if resolved:
            return resolved
        if docker_binary != "docker" or os.name != "nt":
            return docker_binary

        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        desktop_cli = Path(program_files) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe"
        if desktop_cli.is_file():
            return str(desktop_cli)
        return docker_binary

    def run(
        self,
        adapter: LanguageAdapter,
        source: str,
        cancellation_requested: Callable[[], bool] | None = None,
        *,
        source_filename: str | None = None,
        extra_files: dict[str, bytes] | None = None,
        execute_script: str | None = None,
    ) -> SandboxResult:
        source_bytes = source.encode("utf-8")
        files = {source_filename or adapter.filename: source_bytes, **(extra_files or {})}
        if sum(len(contents) for contents in files.values()) > self.source_limit_bytes:
            raise ValueError(f"Source exceeds {self.source_limit_bytes} byte limit")
        for filename, contents in files.items():
            if (
                not isinstance(filename, str)
                or PurePosixPath(filename).name != filename
                or filename in {"", ".", ".."}
            ):
                raise ValueError("Sandbox file names must be simple file names")
            if b"\0" in contents:
                raise ValueError("Source files cannot contain NUL bytes")

        container_name = f"axioma-{uuid.uuid4().hex[:20]}"
        container_id: str | None = None
        try:
            self._docker(["image", "inspect", adapter.image], timeout=5)
            created = self._docker(self._create_args(container_name, adapter.image), timeout=10)
            container_id = created.stdout.decode("ascii", errors="replace").strip()
            if not container_id:
                raise SandboxUnavailable("Docker did not return a container ID")

            # Start the empty container so /work is mounted, then extract directly into its tmpfs.
            self._docker(["start", container_id], timeout=10)
            self._docker(
                [self.docker_binary, "exec", "-i", container_id, "tar", "-x", "-C", "/work"],
                timeout=10,
                input=self._source_archive_files(files),
            )
            try:
                execution = self._run_user_code(
                    container_id,
                    execute_script or adapter.execute_script,
                    cancellation_requested,
                )
            except subprocess.TimeoutExpired:
                self._try_docker(["kill", container_id])
                return SandboxResult(
                    None, "", "Execution exceeded the wall-clock limit", timed_out=True
                )

            if isinstance(execution, SandboxResult) and execution.cancelled:
                self._try_docker(["kill", container_id])
                return SandboxResult(None, "", "Execution cancelled", cancelled=True)

            exit_code_result = self._docker(
                ["exec", container_id, "sh", "-c", "cat /tmp/exit-code"], timeout=5
            )
            try:
                exit_code = int(exit_code_result.stdout.strip())
            except ValueError as exc:
                raise SandboxError("Sandbox did not return a valid process exit code") from exc

            stdout, stdout_limited = self._read_output(container_id, "/tmp/stdout")
            stderr, stderr_limited = self._read_output(container_id, "/tmp/stderr")
            return SandboxResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                output_limited=stdout_limited or stderr_limited,
            )
        except FileNotFoundError as exc:
            raise SandboxUnavailable("Docker CLI is not installed or is not on PATH") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode("utf-8", errors="replace")[:1000] if exc.stderr else ""
            raise SandboxUnavailable(f"Docker operation failed: {detail or exc.cmd}") from exc
        finally:
            if container_id:
                self._try_docker(["rm", "-f", container_id])

    def _create_args(self, name: str, image: str) -> list[str]:
        return [
            self.docker_binary,
            "create",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--pids-limit=64",
            "--memory=256m",
            "--memory-swap=256m",
            "--cpus=1",
            "--user=65534:65534",
            "--tmpfs",
            "/work:rw,exec,nosuid,nodev,size=64m,uid=65534,gid=65534,mode=0700",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=32m,uid=65534,gid=65534,mode=0700",
            "--log-driver=none",
            image,
            "sleep",
            "infinity",
        ]

    def _source_archive(self, filename: str, source: bytes) -> bytes:
        return self._source_archive_files({filename: source})

    def _source_archive_files(self, files: dict[str, bytes]) -> bytes:
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as tar:
            for filename, source in files.items():
                info = tarfile.TarInfo(name=filename)
                info.size = len(source)
                info.mode = 0o444
                tar.addfile(info, io.BytesIO(source))
        return archive.getvalue()

    def _docker(
        self,
        args: list[str],
        timeout: float,
        input: bytes | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        command = args if args[0] == self.docker_binary else [self.docker_binary, *args]
        return subprocess.run(
            command,
            input=input,
            capture_output=True,
            check=True,
            timeout=timeout,
        )

    def _try_docker(self, args: list[str]) -> None:
        try:
            self._docker(args, timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass

    def _run_user_code(
        self,
        container_id: str,
        script: str,
        cancellation_requested: Callable[[], bool] | None,
    ) -> subprocess.CompletedProcess[bytes] | SandboxResult:
        command = [self.docker_binary, "exec", container_id, "sh", "-c", script]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic() + self.timeout_seconds
        while process.poll() is None:
            if cancellation_requested and cancellation_requested():
                process.kill()
                process.communicate(timeout=1)
                return SandboxResult(None, "", "Execution cancelled", cancelled=True)
            if time.monotonic() >= deadline:
                process.kill()
                process.communicate(timeout=1)
                raise subprocess.TimeoutExpired(command, self.timeout_seconds)
            time.sleep(0.05)
        stdout, stderr = process.communicate(timeout=1)
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)

    def _read_output(self, container_id: str, path: str) -> tuple[str, bool]:
        size = self._docker(["exec", container_id, "sh", "-c", f"wc -c < {path}"], timeout=5)
        byte_count = int(size.stdout.strip() or b"0")
        read_limit = min(byte_count, self.output_limit_bytes)
        output = self._docker(
            ["exec", container_id, "head", "-c", str(read_limit), path], timeout=5
        )
        return output.stdout.decode("utf-8", errors="replace"), byte_count > self.output_limit_bytes
