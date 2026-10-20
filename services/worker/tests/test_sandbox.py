import io
import subprocess
import tarfile

import pytest

from axioma_worker.adapters import get_adapter
from axioma_worker.sandbox import DockerSandbox, SandboxResult, SandboxUnavailable


def test_worker_adapters_are_limited_to_supported_languages() -> None:
    assert get_adapter("python").filename == "main.py"
    assert get_adapter("java").filename == "Main.java"
    with pytest.raises(ValueError, match="Unsupported language"):
        get_adapter("javascript")


def test_container_profile_has_isolation_and_resource_limits() -> None:
    args = DockerSandbox()._create_args("job-container", "python:3.13-slim")
    joined = " ".join(args)
    assert "--network none" in joined
    assert "--read-only" in joined
    assert "--cap-drop=ALL" in joined
    assert "--pids-limit=64" in joined
    assert "--memory=256m" in joined
    assert "--security-opt=no-new-privileges:true" in joined
    assert "python:3.13-slim" in args
    assert "-v" not in args and "--volume" not in args


def test_source_archive_uses_fixed_safe_filename() -> None:
    archive_bytes = DockerSandbox()._source_archive("main.py", b"print('ok')")
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
        members = archive.getmembers()
        assert [member.name for member in members] == ["main.py"]
        assert archive.extractfile(members[0]).read() == b"print('ok')"


def test_source_size_is_checked_before_docker_is_called(monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = DockerSandbox(source_limit_bytes=4)
    monkeypatch.setattr(
        sandbox, "_docker", lambda *args, **kwargs: pytest.fail("Docker was called")
    )
    with pytest.raises(ValueError, match="Source exceeds"):
        sandbox.run(get_adapter("python"), "12345")


def test_run_lifecycle_uses_prebuilt_image_and_cleans_up(monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = DockerSandbox()
    docker_calls: list[tuple[list[str], bytes | None]] = []

    def fake_docker(args: list[str], timeout: float, input: bytes | None = None):
        docker_calls.append((args, input))
        if "create" in args:
            return subprocess.CompletedProcess(args, 0, b"container-1", b"")
        if any("cat" in arg for arg in args):
            return subprocess.CompletedProcess(args, 0, b"0", b"")
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(sandbox, "_docker", fake_docker)
    monkeypatch.setattr(
        sandbox,
        "_run_user_code",
        lambda *args: subprocess.CompletedProcess(args[0], 0, b"", b""),
    )
    monkeypatch.setattr(
        sandbox,
        "_read_output",
        lambda _container_id, path: ("done\n" if path.endswith("stdout") else "", False),
    )

    result = sandbox.run(get_adapter("python"), "print('done')")

    assert result == SandboxResult(exit_code=0, stdout="done\n", stderr="")
    assert any("image" in args and "inspect" in args for args, _ in docker_calls)
    assert any(args[1:3] == ["cp", "-"] and archive for args, archive in docker_calls)
    assert any(args[0:2] == ["rm", "-f"] for args, _ in docker_calls)
    start_index = next(i for i, (args, _) in enumerate(docker_calls) if args[:2] == ["start", "container-1"])
    copy_index = next(i for i, (args, _) in enumerate(docker_calls) if args[1:3] == ["cp", "-"])
    assert start_index < copy_index
    assert all(not any("print('done')" in arg for arg in command) for command, _ in docker_calls)


def test_missing_docker_is_reported_without_attempting_a_pull(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sandbox = DockerSandbox()
    calls = []

    def missing_docker(args, timeout, input=None):
        calls.append(args)
        raise FileNotFoundError("docker")

    monkeypatch.setattr(sandbox, "_docker", missing_docker)
    with pytest.raises(SandboxUnavailable, match="Docker CLI is not installed"):
        sandbox.run(get_adapter("python"), "print(1)")
    assert len(calls) == 1
    assert calls[0] == ["image", "inspect", "python:3.13-slim"]


def test_timeout_kills_and_removes_the_container(monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = DockerSandbox()
    docker_calls: list[list[str]] = []

    def fake_docker(args: list[str], timeout: float, input: bytes | None = None):
        docker_calls.append(args)
        if "create" in args:
            return subprocess.CompletedProcess(args, 0, b"container-1", b"")
        return subprocess.CompletedProcess(args, 0, b"", b"")

    def timeout(*_args):
        raise subprocess.TimeoutExpired("docker exec", 10)

    monkeypatch.setattr(sandbox, "_docker", fake_docker)
    monkeypatch.setattr(sandbox, "_run_user_code", timeout)
    result = sandbox.run(get_adapter("python"), "while True: pass")
    assert result.timed_out is True
    assert any(args[0:2] == ["kill", "container-1"] for args in docker_calls)
    assert any(args[0:2] == ["rm", "-f"] for args in docker_calls)
