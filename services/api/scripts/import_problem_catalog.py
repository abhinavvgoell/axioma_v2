from __future__ import annotations

import argparse
import ast
import gzip
import json
import re
import urllib.request
import warnings
from pathlib import Path
from typing import Any

from axioma_api.catalog_selection import select_catalog_packs
from axioma_api.problem_constraints import constraints_match_samples, parse_problem_constraints


REPOSITORY = "https://github.com/newfacade/LeetCodeDataset"
REVISION = "182cd19fd53161efd70a1ef074fe1056b659bfa3"
DATASET_VERSION = "v0.3.1"
USER_AGENT = "Axioma-problem-catalog-importer/1.0"
MAX_CASES_PER_PROBLEM = 20
MAX_CASE_BYTES = 16_384
MIN_CASES_PER_PROBLEM = 4
UNSUPPORTED_TYPES = re.compile(
    r"\b(?:ListNode|TreeNode|NestedInteger|MountainArray|GuessGame|Robot|Node)\b"
)


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _json_value(value: Any) -> bool:
    if value is None or type(value) in (bool, int, float, str):
        return True
    if isinstance(value, list):
        return all(_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _json_value(item) for key, item in value.items())
    return False


def _parse_arguments(source: str) -> dict[str, Any] | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            expression = ast.parse(f"_axioma_call({source})", mode="eval").body
        if not isinstance(expression, ast.Call) or expression.args:
            return None
        if any(keyword.arg is None for keyword in expression.keywords):
            return None
        values = {
            keyword.arg: ast.literal_eval(keyword.value)
            for keyword in expression.keywords
            if keyword.arg is not None
        }
    except (SyntaxError, ValueError, TypeError, MemoryError, RecursionError, OverflowError):
        return None
    return values if _json_value(values) else None


def _parse_output(source: str) -> Any | None:
    text = source.strip()
    if not text or "execution timed out" in text.casefold():
        return None
    try:
        value = ast.literal_eval(text)
    except (SyntaxError, ValueError, TypeError, MemoryError, RecursionError, OverflowError):
        try:
            value = json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError, OverflowError):
            # A few dataset rows store a string result without quotes.
            if re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", text):
                return None
            value = text
    return value if _json_value(value) else None


def _entrypoint(row: dict[str, Any]) -> str | None:
    source = str(row.get("entry_point", ""))
    match = re.search(r"\bSolution\(\)\.([A-Za-z_]\w*)\b", source)
    if match:
        return f"Solution.{match.group(1)}"
    match = re.search(r"\bSolution\.([A-Za-z_]\w*)\b", source)
    if match:
        return f"Solution.{match.group(1)}"
    return None


def _argument_order(row: dict[str, Any], entrypoint: str) -> list[str] | None:
    starter_code = str(row.get("starter_code", "")).rstrip()
    last_line = starter_code.splitlines()[-1] if starter_code else ""
    if last_line.rstrip().endswith(":"):
        indent = len(last_line) - len(last_line.lstrip()) + 4
        starter_code += "\n" + " " * indent + "pass"
    try:
        module = ast.parse(starter_code)
    except (SyntaxError, ValueError, TypeError):
        return None
    method_name = entrypoint.split(".", maxsplit=1)[1]
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            positional = [*node.args.posonlyargs, *node.args.args]
            return [argument.arg for argument in positional if argument.arg != "self"]
    return None


def _samples(row: dict[str, Any], argument_order: list[str]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for case_index, case in enumerate(row.get("input_output", []), start=1):
        if not isinstance(case, dict):
            continue
        kwargs = _parse_arguments(str(case.get("input", "")))
        expected = _parse_output(str(case.get("output", "")))
        if kwargs is None or expected is None:
            continue
        if any(key not in argument_order for key in kwargs):
            continue
        provided_positions = [argument_order.index(key) for key in kwargs]
        if provided_positions != sorted(provided_positions):
            continue
        args = [kwargs[key] for key in argument_order if key in kwargs]
        if len(args) != len(kwargs):
            continue
        sample = {
            "name": f"dataset_case_{case_index}",
            "args": args,
            "kwargs": {},
            "expected": expected,
        }
        serialized = json.dumps(sample, ensure_ascii=False, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > MAX_CASE_BYTES:
            continue
        samples.append(sample)
        if len(samples) == MAX_CASES_PER_PROBLEM:
            break
    return samples


def _to_pack(row: dict[str, Any]) -> dict[str, Any] | None:
    slug = row.get("task_id")
    entrypoint = _entrypoint(row)
    starter_code = str(row.get("starter_code", ""))
    if not isinstance(slug, str) or not entrypoint:
        return None
    if UNSUPPORTED_TYPES.search(starter_code):
        return None
    argument_order = _argument_order(row, entrypoint)
    if argument_order is None:
        return None
    samples = _samples(row, argument_order)
    if len(samples) < MIN_CASES_PER_PROBLEM:
        return None
    description = str(row.get("problem_description", ""))
    constraints = constraints_match_samples(
        parse_problem_constraints(description, argument_order), samples
    )
    title = re.sub(r"\s+", " ", slug.replace("-", " ").title()).strip()
    return {
        "slug": slug,
        "question_id": row.get("question_id"),
        "title": title,
        "description": description,
        "difficulty": row.get("difficulty"),
        "topics": row.get("tags", []),
        "entrypoint": entrypoint,
        "constraints": [constraint.model_dump(mode="json") for constraint in constraints],
        "samples": samples,
        "test_source": (
            "Imported from newfacade/LeetCodeDataset v0.3.1 at "
            f"{REVISION[:12]}; {len(samples)} dataset cases. "
            "These are not LeetCode hidden judge tests; Axioma has not independently "
            "verified this pack."
        ),
    }


def _read_rows(archive: bytes):
    import io

    with gzip.GzipFile(fileobj=io.BytesIO(archive), mode="rb") as compressed:
        for raw_line in compressed:
            if raw_line.strip():
                yield json.loads(raw_line)


def import_catalog(limit: int, output_dir: Path) -> dict[str, Any]:
    data_url = (
        f"https://raw.githubusercontent.com/newfacade/LeetCodeDataset/{REVISION}/"
        f"data/LeetCodeDataset-{DATASET_VERSION}-train.jsonl.gz"
    )
    rows = _read_rows(_download(data_url))
    eligible: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        pack = _to_pack(row)
        if pack:
            eligible.setdefault(pack["slug"], pack)
    selected = select_catalog_packs(list(eligible.values()), limit)
    if len(selected) < limit:
        raise RuntimeError(
            f"The pinned dataset contains only {len(selected)} compatible packs; "
            f"{limit} were requested."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = output_dir / "problem_catalog.json"
    metadata = {
        "schema_version": 1,
        "source_repository": REPOSITORY,
        "source_revision": REVISION,
        "dataset_version": DATASET_VERSION,
        "problems_imported": len(selected),
        "selection": (
            "round-robin across core DSA topics and Easy/Medium/Hard difficulty, then question ID; "
            "at least four JSON-compatible cases"
        ),
        "warning": (
            "Dataset repository license is MIT. Review rights for embedded third-party "
            "problem text and test data before redistribution."
        ),
        "problems": selected,
    }
    catalog_path.write_text(
        json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    license_url = f"https://raw.githubusercontent.com/newfacade/LeetCodeDataset/{REVISION}/LICENSE"
    (output_dir / "LICENSE-LeetCodeDataset.txt").write_bytes(_download(license_url))
    (output_dir / "SOURCE.txt").write_text(
        f"Source: {REPOSITORY}\n"
        f"Dataset version: {DATASET_VERSION}\n"
        f"Pinned revision: {REVISION}\n"
        "The importer uses input_output literal cases only; it does not execute dataset code.\n"
        "The dataset repository is MIT licensed. Embedded third-party content may have separate rights.\n",
        encoding="utf-8",
    )
    return {"path": str(catalog_path), "imported": len(selected), "eligible": len(eligible)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a local Axioma problem catalog.")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    arguments = parser.parse_args()
    if arguments.limit < 1:
        parser.error("--limit must be positive")
    result = import_catalog(arguments.limit, arguments.output_dir)
    print(
        f"Imported {result['imported']} problem packs ({result['eligible']} eligible) "
        f"to {result['path']}"
    )


if __name__ == "__main__":
    main()
