"""Run existing static analyzers on a BFS v2 packet without exposing labels to them."""

from __future__ import annotations

import argparse
import ast
from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "axioma.bfs-v2.prediction.v1"
JAVA_TOKEN_RE = re.compile(
    r"//[^\n]*|/\*[\s\S]*?\*/|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|"
    r"[A-Za-z_$][\w$]*|\d+|[{}();,\[\].<>]"
)
NON_METHOD_NAMES = {"if", "for", "while", "switch", "catch", "synchronized", "new"}


class PredictionInputError(ValueError):
    """Raised when packet identity or source integrity is invalid."""


@dataclass(frozen=True)
class PacketInput:
    case_id: str
    language: str
    pattern: str
    source: str
    source_sha256: str


Analyzer = Callable[[str, str], Any]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _java_tokens(source: str) -> list[str]:
    return [
        match.group()
        for match in JAVA_TOKEN_RE.finditer(source)
        if not match.group().startswith(("//", "/*", '"', "'"))
    ]


def _java_entrypoint(source: str) -> str:
    tokens = _java_tokens(source)
    class_index = next(
        (i for i, token in enumerate(tokens[:-1]) if token == "class"), None
    )
    if class_index is None:
        raise PredictionInputError("Java source has no class declaration")
    class_name = tokens[class_index + 1]
    try:
        open_brace = tokens.index("{", class_index + 2)
    except ValueError as exc:
        raise PredictionInputError("Java class body is missing") from exc
    depth = 1
    i = open_brace + 1
    while i < len(tokens) and depth:
        token = tokens[i]
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
        elif depth == 1 and token == "(":
            name_index = i - 1
            if name_index < 0:
                i += 1
                continue
            method_name = tokens[name_index]
            if method_name in NON_METHOD_NAMES or method_name == class_name:
                i += 1
                continue
            paren_depth = 1
            close = i + 1
            while close < len(tokens) and paren_depth:
                if tokens[close] == "(":
                    paren_depth += 1
                elif tokens[close] == ")":
                    paren_depth -= 1
                close += 1
            if paren_depth == 0 and close < len(tokens) and tokens[close] == "{":
                return f"{class_name}.{method_name}"
        i += 1
    raise PredictionInputError("Java source has no top-level method entrypoint")


def resolve_entrypoint(source: str, language: str) -> str:
    """Resolve the analyzer context from code only; packet labels are not consulted."""
    if language == "java":
        return _java_entrypoint(source)
    if language == "python":
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise PredictionInputError(
                f"Python source syntax error: {exc.msg}"
            ) from exc
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        raise PredictionInputError(
            "Python source has no module-level function entrypoint"
        )
    raise PredictionInputError(f"unsupported language {language!r}")


def read_packet(
    path: Path, expected_packet_sha256: str | None = None
) -> list[PacketInput]:
    """Load minimal analyzer inputs, verifying the packet and every exact source string."""
    data = path.read_bytes()
    actual_packet_hash = _sha256(data)
    if expected_packet_sha256 and actual_packet_hash != expected_packet_sha256:
        raise PredictionInputError(
            f"packet SHA-256 mismatch: expected {expected_packet_sha256}, got {actual_packet_hash}"
        )
    cases: list[PacketInput] = []
    seen: set[str] = set()
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PredictionInputError(f"line {line_number}: invalid JSON") from exc
        if not isinstance(record, dict):
            raise PredictionInputError(f"line {line_number}: expected an object")
        # Select only inference inputs. Gold labels and review fields are intentionally dropped.
        required = ("case_id", "language", "pattern", "source", "source_sha256")
        if any(
            not isinstance(record.get(key), str) or not record[key] for key in required
        ):
            raise PredictionInputError(
                f"line {line_number}: missing or invalid inference input"
            )
        case_id = record["case_id"]
        if case_id in seen:
            raise PredictionInputError(
                f"line {line_number}: duplicate case ID {case_id!r}"
            )
        seen.add(case_id)
        actual_source_hash = hashlib.sha256(
            record["source"].encode("utf-8")
        ).hexdigest()
        if actual_source_hash != record["source_sha256"]:
            raise PredictionInputError(
                f"line {line_number}: source hash mismatch for {case_id}"
            )
        if record["language"] not in {"java", "python"}:
            raise PredictionInputError(
                f"line {line_number}: unsupported language for {case_id}"
            )
        cases.append(PacketInput(*(record[key] for key in required)))
    if not cases:
        raise PredictionInputError("packet contains no cases")
    return cases


def _raw_analyzer_output(result: Any) -> dict[str, Any]:
    if is_dataclass(result) and not isinstance(result, type):
        raw = asdict(result)
    elif isinstance(result, Mapping):
        raw = dict(result)
    else:
        names = (
            "method",
            "estimate",
            "confidence",
            "methods_disagree",
            "explanation",
            "details",
        )
        raw = {name: getattr(result, name) for name in names if hasattr(result, name)}
    if not isinstance(raw.get("estimate"), str) or not raw["estimate"].strip():
        raise TypeError("analyzer result must contain a non-empty string estimate")
    return raw


def run_cases(
    cases: Sequence[PacketInput], analyzers: Mapping[str, Analyzer]
) -> list[dict[str, Any]]:
    """Invoke injected analyzers using only source and extracted entrypoint context."""
    ids = [case.case_id for case in cases]
    if len(set(ids)) != len(ids):
        raise PredictionInputError("duplicate case IDs supplied to runner")
    for case in cases:
        if (
            hashlib.sha256(case.source.encode("utf-8")).hexdigest()
            != case.source_sha256
        ):
            raise PredictionInputError(f"source hash mismatch for {case.case_id}")

    predictions: list[dict[str, Any]] = []
    for case in cases:
        record: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "case_id": case.case_id,
            "language": case.language,
            "pattern": case.pattern,
            "source_sha256": case.source_sha256,
            "entrypoint": None,
            "execution_status": "error",
            "actual_response": "error",
            "analyzer_output": None,
            "error": None,
        }
        try:
            entrypoint = resolve_entrypoint(case.source, case.language)
            record["entrypoint"] = entrypoint
        except Exception as exc:
            record["error"] = {
                "stage": "context_resolution",
                "type": type(exc).__name__,
                "message": str(exc),
            }
            predictions.append(record)
            continue
        analyzer = analyzers.get(case.language)
        if analyzer is None:
            record["error"] = {
                "stage": "dispatch",
                "type": "MissingAnalyzer",
                "message": f"no analyzer configured for {case.language}",
            }
            predictions.append(record)
            continue
        try:
            # Do not pass the packet row, label, pattern, or review metadata to analyzers.
            output = _raw_analyzer_output(analyzer(case.source, entrypoint))
            record["analyzer_output"] = output
            raw_estimate = output["estimate"].strip()
            record["actual_response"] = (
                "unknown" if raw_estimate.lower().startswith("unknown") else "estimate"
            )
            record["execution_status"] = "completed"
        except Exception as exc:
            record["error"] = {
                "stage": "analyzer_execution",
                "type": type(exc).__name__,
                "message": str(exc),
            }
        predictions.append(record)
    return predictions


def load_default_analyzers() -> dict[str, Analyzer]:
    """Import the existing analyzer implementations only for an explicit runner call."""
    sys.path.insert(0, str(ROOT / "services" / "worker" / "src"))
    sys.path.insert(0, str(ROOT / "services" / "api" / "src"))
    from axioma_worker.java_complexity import analyze_java_complexity
    from axioma_worker.python_complexity import analyze_python_complexity

    return {"java": analyze_java_complexity, "python": analyze_python_complexity}


def write_predictions(path: Path, predictions: Sequence[Mapping[str, Any]]) -> None:
    """Write newline-delimited raw predictions without overwriting existing evidence."""
    with path.open("x", encoding="utf-8", newline="\n") as output:
        for prediction in predictions:
            output.write(
                json.dumps(prediction, ensure_ascii=False, separators=(",", ":"))
            )
            output.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path, help="source JSONL packet")
    parser.add_argument(
        "--packet-sha256", required=True, help="expected whole-packet SHA-256"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="new predictions JSONL path"
    )
    args = parser.parse_args()
    try:
        if args.output.exists():
            parser.error(f"refusing to overwrite existing output: {args.output}")
        if not args.output.parent.is_dir():
            parser.error(f"output directory does not exist: {args.output.parent}")
        cases = read_packet(args.packet, args.packet_sha256)
        predictions = run_cases(cases, load_default_analyzers())
        write_predictions(args.output, predictions)
    except (OSError, PredictionInputError) as exc:
        parser.error(str(exc))
    completed = sum(item["execution_status"] == "completed" for item in predictions)
    errors = len(predictions) - completed
    print(
        f"Wrote {len(predictions)} prediction records ({completed} completed, {errors} errors)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
