from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "manifest-v1.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_PATH,
        help="candidate manifest to validate (defaults to manifest-v1.json)",
    )
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    if ROOT not in manifest_path.parents or not manifest_path.is_file():
        raise ValueError("manifest must be an existing file in this evaluation directory")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidate_path = ROOT / manifest["candidate_file"]
    candidate_bytes = candidate_path.read_bytes()
    if sha256(candidate_bytes) != manifest["candidate_file_sha256"]:
        raise ValueError("candidate packet SHA-256 does not match manifest")

    rows = [
        json.loads(line)
        for line in candidate_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    ids = [row["id"] for row in rows]
    if len(ids) != manifest["case_count_current_batch"] or len(set(ids)) != len(ids):
        raise ValueError("candidate case count or ID uniqueness check failed")
    if ids != manifest["case_ids"]:
        raise ValueError("candidate IDs do not match manifest")
    if manifest["gold_labels_frozen"] or manifest["analyzer_run"]:
        raise ValueError("candidate batch must remain unfrozen and unanalyzed")

    for row in rows:
        required = (
            "expected_time",
            "expected_time_exact",
            "expected_auxiliary_space",
            "expected_auxiliary_space_exact",
            "assumptions",
            "time_rationale",
            "space_rationale",
            "source_sha256",
            "source_url",
        )
        if any(not row.get(field) for field in required):
            raise ValueError(f"required review field is missing for {row['id']}")
        if row.get("decision_status") != "proposed_pending_owner_confirmation":
            raise ValueError(f"owner review status is not pending for {row['id']}")
        if row.get("owner_decision") is not None or row.get("reviewer") is not None:
            raise ValueError(f"owner decision was populated without review for {row['id']}")
        if "predicted" in row:
            raise ValueError(f"candidate case contains analyzer output for {row['id']}")

        source_bytes = row["source"].encode("utf-8")
        if sha256(source_bytes) != row["source_sha256"]:
            raise ValueError(f"embedded source SHA-256 mismatch for {row['id']}")
        local_path = (ROOT / row["local_path"]).resolve()
        if ROOT not in local_path.parents or not local_path.is_file():
            raise ValueError(f"source snapshot path is invalid for {row['id']}")
        if local_path.read_bytes() != source_bytes:
            raise ValueError(f"source snapshot differs from packet for {row['id']}")
        if manifest["source_sha256"].get(row["id"]) != row["source_sha256"]:
            raise ValueError(f"source hash does not match manifest for {row['id']}")
        repo = row["repo"]
        if row["commit"] != manifest["upstream_repositories"][repo]["commit"]:
            raise ValueError(f"source commit does not match manifest for {row['id']}")
        if row["commit"] not in row["source_url"]:
            raise ValueError(f"source URL is not commit-pinned for {row['id']}")

    if not (ROOT / "LICENSE-TheAlgorithms-Python.md").is_file():
        raise ValueError("Python upstream license notice is missing")
    if not (ROOT / "LICENSE-TheAlgorithms-Java.md").is_file():
        raise ValueError("Java upstream license notice is missing")
    for output_name in (
        "analysis-output-v1.json",
        "predictions-v1.jsonl",
        "run-manifest-v1.json",
    ):
        if (ROOT / output_name).exists():
            raise ValueError(f"candidate packet must not contain analyzer output: {output_name}")

    print(
        json.dumps(
            {
                "candidate_count": len(rows),
                "unique_ids": len(set(ids)),
                "source_hashes_match": True,
                "labels_frozen": False,
                "analyzer_run": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
