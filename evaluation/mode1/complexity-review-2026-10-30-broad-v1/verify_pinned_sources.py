from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_manifest(path: Path) -> int:
    manifest_path = path.resolve()
    if ROOT not in manifest_path.parents or not manifest_path.is_file():
        raise ValueError(f"manifest must be inside {ROOT}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_path = (ROOT / manifest["candidate_file"]).resolve()
    if ROOT not in packet_path.parents or not packet_path.is_file():
        raise ValueError("candidate packet must be inside the evaluation directory")
    packet = packet_path.read_bytes()
    if sha256(packet) != manifest["candidate_file_sha256"]:
        raise ValueError(f"candidate packet hash mismatch: {packet_path.name}")

    cases = [json.loads(line) for line in packet.decode("utf-8").splitlines() if line.strip()]
    if len(cases) != manifest["case_count_current_batch"]:
        raise ValueError(f"case count mismatch: {manifest_path.name}")

    for case in cases:
        repo = case["repo"]
        repository = manifest["upstream_repositories"][repo]
        commit = repository["commit"]
        if case["commit"] != commit or commit not in case["source_url"]:
            raise ValueError(f"source commit is not pinned by manifest: {case['id']}")

        relative_path = case["repo_path"].lstrip("/")
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{relative_path}"
        request = Request(url, headers={"User-Agent": "Axioma-source-provenance-audit"})
        with urlopen(request, timeout=20) as response:
            upstream = response.read()

        snapshot_path = (ROOT / case["local_path"]).resolve()
        if ROOT not in snapshot_path.parents or not snapshot_path.is_file():
            raise ValueError(f"source snapshot path is invalid: {case['id']}")
        snapshot = snapshot_path.read_bytes()
        embedded = case["source"].encode("utf-8")
        expected_hash = case["source_sha256"]
        if sha256(upstream) != expected_hash:
            raise ValueError(f"upstream source hash mismatch: {case['id']}")
        if snapshot != upstream or embedded != upstream:
            raise ValueError(f"upstream, local, and embedded source differ: {case['id']}")
        print(f"MATCH {case['id']} {expected_hash}")

    print(f"PASS {len(cases)} pinned source files match byte-for-byte ({manifest_path.name})")
    return len(cases)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare candidate sources with pinned upstream commits.")
    parser.add_argument("--manifest", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    total = sum(verify_manifest(path) for path in args.manifest)
    print(f"PASS {total} source records checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
