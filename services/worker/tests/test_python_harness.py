import json
import subprocess
import sys

from axioma_worker.python_harness import build_function_harness


def test_harness_executes_function_samples_and_suppresses_program_output(tmp_path) -> None:
    submission = """import json
json.dumps = lambda *args, **kwargs: 'forged'
print('loading submission')
def double(value):
    print('function output')
    return value * 2
"""
    samples = [
        {"name": "correct", "args": [4], "kwargs": {}, "expected": 8},
        {"name": "incorrect", "args": [5], "kwargs": {}, "expected": 11},
    ]
    (tmp_path / "submission.py").write_text(submission, encoding="utf-8")
    harness_path = tmp_path / "main.py"
    harness_path.write_text(build_function_harness("double", samples), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    assert completed.returncode == 0
    assert "loading submission" not in completed.stdout
    assert "function output" not in completed.stdout
    marker = "AXIOMA_RESULT:"
    output = next(line for line in completed.stdout.splitlines() if line.startswith(marker))
    assert json.loads(output[len(marker) :]) == [
        {"name": "correct", "outcome": "passed", "details": {}},
        {
            "name": "incorrect",
            "outcome": "failed",
            "details": {
                "expected": 11,
                "actual": 10,
                "failure_kind": "incorrect_output",
            },
        },
    ]


def test_harness_records_submission_line_for_runtime_errors(tmp_path) -> None:
    (tmp_path / "submission.py").write_text(
        "def solve(value):\n    return 10 // value\n", encoding="utf-8"
    )
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "solve", [{"name": "zero", "args": [0], "kwargs": {}, "expected": 0}]
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    marker = "AXIOMA_RESULT:"
    output = next(line for line in completed.stdout.splitlines() if line.startswith(marker))
    result = json.loads(output[len(marker) :])[0]
    assert completed.returncode == 0
    assert result["details"]["error"] == "ZeroDivisionError: integer division or modulo by zero"
    assert result["details"]["source_location"] == {
        "file": "submission.py",
        "line": 2,
        "function": "solve",
    }


def test_harness_instantiates_solution_class_for_methods(tmp_path) -> None:
    (tmp_path / "submission.py").write_text(
        "class Solution:\n    def add(self, left, right):\n        return left + right\n",
        encoding="utf-8",
    )
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "Solution.add",
            [{"name": "sum", "args": [2, 3], "kwargs": {}, "expected": 5}],
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    assert completed.returncode == 0
    assert '"outcome":"passed"' in completed.stdout


def test_harness_validates_reference_against_samples_before_differential_inputs(tmp_path) -> None:
    (tmp_path / "submission.py").write_text(
        "def square(value): return value * value\n", encoding="utf-8"
    )
    (tmp_path / "reference.py").write_text(
        "def square(value): return value * value\n", encoding="utf-8"
    )
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "square",
            [{"name": "sample", "args": [2], "kwargs": {}, "expected": 4}],
            reference_code="def square(value): return value * value",
            generated_samples=[
                {
                    "name": "generated_1",
                    "args": [3],
                    "kwargs": {},
                    "kind": "function",
                    "strategy": "boundary_maximum_1",
                }
            ],
            requested_generated=2,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    marker = "AXIOMA_RESULT:"
    output = next(line for line in completed.stdout.splitlines() if line.startswith(marker))
    results = json.loads(output[len(marker) :])
    assert [(item["name"], item["outcome"]) for item in results] == [
        ("sample", "passed"),
        ("reference/sample", "passed"),
        ("generated_1", "passed"),
        ("generated_2", "skipped"),
    ]
    assert results[2]["details"]["input_strategy"] == "boundary_maximum_1"


def test_harness_skips_differential_cases_when_reference_disagrees_with_sample(tmp_path) -> None:
    (tmp_path / "submission.py").write_text("def solve(value): return value\n", encoding="utf-8")
    (tmp_path / "reference.py").write_text("def solve(value): return value + 1\n", encoding="utf-8")
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "solve",
            [{"name": "sample", "args": [2], "kwargs": {}, "expected": 2}],
            reference_code="def solve(value): return value + 1",
            generated_samples=[{"name": "generated_1", "args": [3], "kwargs": {}}],
            requested_generated=1,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    marker = "AXIOMA_RESULT:"
    output = next(line for line in completed.stdout.splitlines() if line.startswith(marker))
    results = json.loads(output[len(marker) :])
    assert results[1]["name"] == "reference/sample"
    assert results[1]["outcome"] == "failed"
    assert results[2]["outcome"] == "skipped"


def test_harness_skips_candidate_comparison_when_references_disagree(tmp_path) -> None:
    (tmp_path / "submission.py").write_text("def solve(value): return value * 2\n", encoding="utf-8")
    (tmp_path / "reference.py").write_text("def solve(value): return value * 2\n", encoding="utf-8")
    independent_code = "def solve(value): return value * 2 if value <= 2 else value + 1\n"
    (tmp_path / "independent_reference.py").write_text(independent_code, encoding="utf-8")
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "solve",
            [{"name": "sample", "args": [2], "kwargs": {}, "expected": 4}],
            reference_code="def solve(value): return value * 2",
            independent_reference_code=independent_code,
            generated_samples=[{"name": "generated_1", "args": [3], "kwargs": {}}],
            requested_generated=1,
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )
    output = next(
        line for line in completed.stdout.splitlines() if line.startswith("AXIOMA_RESULT:")
    )
    results = json.loads(output[len("AXIOMA_RESULT:") :])
    assert results[1]["outcome"] == "passed"
    assert results[2]["outcome"] == "skipped"
    assert "candidate comparison not run" in results[2]["details"]["reason"]


def test_harness_measures_line_and_opcode_events_for_increasing_inputs(tmp_path) -> None:
    (tmp_path / "submission.py").write_text(
        "def solve(value):\n    total = 0\n    for item in range(value):\n        total += item\n    return total\n",
        encoding="utf-8",
    )
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "solve",
            [{"name": "sample", "args": [3], "kwargs": {}, "expected": 3}],
            complexity_benchmarks=[
                {"size": size, "args": [size], "kwargs": {}, "strategy": "descending"}
                for size in (8, 16, 32, 64)
            ],
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    marker = "AXIOMA_COMPLEXITY:"
    output = next(line for line in completed.stdout.splitlines() if line.startswith(marker))
    report = json.loads(output[len(marker) :])
    points = report["measurements"]
    assert completed.returncode == 0
    assert report["skipped_reason"] is None
    assert [point["size"] for point in points] == [8, 16, 32, 64]
    assert all(point["input_strategy"] == "descending" for point in points)
    assert all(
        left["line_events"] < right["line_events"] for left, right in zip(points, points[1:])
    )
    assert all(point["opcode_events"] > point["line_events"] for point in points)
    assert all(
        left["opcode_events"] < right["opcode_events"] for left, right in zip(points, points[1:])
    )
    assert all(point["peak_traced_bytes"] > 0 for point in points)


def test_optimization_checks_equivalence_and_measures_both_variants(tmp_path) -> None:
    original = "def solve(values):\n    total = 0\n    for value in values:\n        total += value\n    return total\n"
    optimized = "def solve(values):\n    return sum(values)\n"
    (tmp_path / "submission.py").write_text(original, encoding="utf-8")
    (tmp_path / "optimized.py").write_text(optimized, encoding="utf-8")
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "solve",
            [{"name": "sum", "args": [[1, 2, 3]], "kwargs": {}, "expected": 6}],
            optimization_code=optimized,
            complexity_benchmarks=[
                {"size": size, "args": [list(range(size))], "kwargs": {}}
                for size in (10, 20, 40, 80)
            ],
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    optimization_marker = "AXIOMA_OPTIMIZATION:"
    optimization_line = next(
        line for line in completed.stdout.splitlines() if line.startswith(optimization_marker)
    )
    optimization = json.loads(optimization_line[len(optimization_marker) :])
    complexity_marker = "AXIOMA_COMPLEXITY:"
    complexity_line = next(
        line for line in completed.stdout.splitlines() if line.startswith(complexity_marker)
    )
    complexity = json.loads(complexity_line[len(complexity_marker) :])
    assert completed.returncode == 0
    assert optimization["checks"][0]["outcome"] == "passed"
    assert len(complexity["optimized_measurements"]) == 4
    assert all(
        point["optimized_line_events"] < point["line_events"]
        for point in complexity["optimized_measurements"]
    )
    assert all(
        point["optimized_opcode_events"] < point["opcode_events"]
        for point in complexity["optimized_measurements"]
    )
    assert all(point["optimized_peak_traced_bytes"] >= 0 for point in complexity["optimized_measurements"])


def test_optimization_measurements_are_skipped_when_outputs_differ(tmp_path) -> None:
    (tmp_path / "submission.py").write_text(
        "def solve(value): return value + 1\n", encoding="utf-8"
    )
    (tmp_path / "optimized.py").write_text("def solve(value): return value - 1\n", encoding="utf-8")
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "solve",
            [{"name": "sample", "args": [2], "kwargs": {}, "expected": 3}],
            optimization_code="def solve(value): return value - 1\n",
            complexity_benchmarks=[
                {"size": size, "args": [size], "kwargs": {}} for size in (10, 20, 40, 80)
            ],
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    marker = "AXIOMA_COMPLEXITY:"
    output = next(line for line in completed.stdout.splitlines() if line.startswith(marker))
    report = json.loads(output[len(marker) :])
    assert len(report["measurements"]) == 4
    assert report["optimized_measurements"] == []
    assert report["optimized_skipped_reason"] == "optimization equivalence checks did not all pass"


def test_property_checks_are_validated_on_examples_before_generated_cases(tmp_path) -> None:
    (tmp_path / "submission.py").write_text(
        "def solve(value): return value * 2\n", encoding="utf-8"
    )
    property_code = "def check(args, kwargs, result): return result >= args[0]"
    (tmp_path / "properties.py").write_text(property_code + "\n", encoding="utf-8")
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "solve",
            [{"name": "sample", "args": [2], "kwargs": {}, "expected": 4}],
            property_code=property_code,
            property_samples=[
                {"name": "generated_1", "args": [3], "kwargs": {}, "strategy": "boundary_maximum"},
                {"name": "generated_2", "args": [4], "kwargs": {}, "strategy": "random"},
            ],
            requested_property_tests=2,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    marker = "AXIOMA_PROPERTY:"
    line = next(line for line in completed.stdout.splitlines() if line.startswith(marker))
    report = json.loads(line[len(marker) :])
    assert completed.returncode == 0
    assert report["property_validated_on_examples"] is True
    assert [item["outcome"] for item in report["example_checks"]] == ["passed"]
    assert [item["outcome"] for item in report["generated_checks"]] == ["passed", "passed"]


def test_property_failure_on_example_skips_generated_property_checks(tmp_path) -> None:
    (tmp_path / "submission.py").write_text("def solve(value): return value\n", encoding="utf-8")
    property_code = "def check(args, kwargs, result): return result > 2"
    (tmp_path / "properties.py").write_text(property_code + "\n", encoding="utf-8")
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "solve",
            [{"name": "sample", "args": [2], "kwargs": {}, "expected": 2}],
            property_code=property_code,
            property_samples=[{"name": "generated_1", "args": [3], "kwargs": {}}],
            requested_property_tests=1,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    marker = "AXIOMA_PROPERTY:"
    line = next(line for line in completed.stdout.splitlines() if line.startswith(marker))
    report = json.loads(line[len(marker) :])
    assert report["property_validated_on_examples"] is False
    assert report["example_checks"][0]["outcome"] == "failed"
    assert report["generated_checks"][0]["outcome"] == "skipped"


def test_harness_skips_complexity_measurements_when_correctness_check_fails(tmp_path) -> None:
    (tmp_path / "submission.py").write_text("def solve(value): return -1\n", encoding="utf-8")
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "solve",
            [{"name": "sample", "args": [1], "kwargs": {}, "expected": 1}],
            complexity_benchmarks=[
                {"size": size, "args": [size], "kwargs": {}} for size in (1, 2, 3)
            ],
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    marker = "AXIOMA_COMPLEXITY:"
    output = next(line for line in completed.stdout.splitlines() if line.startswith(marker))
    report = json.loads(output[len(marker) :])
    assert report["measurements"] == []
    assert report["skipped_reason"] == "candidate did not pass all configured checks"


def test_harness_reports_killed_mutants_separately_from_tests(tmp_path) -> None:
    source = "def solve(value): return value + 1\n"
    (tmp_path / "submission.py").write_text(source, encoding="utf-8")
    (tmp_path / "reference.py").write_text(source, encoding="utf-8")
    (tmp_path / "mutant_1.py").write_text("def solve(value): return value - 1\n", encoding="utf-8")
    harness_path = tmp_path / "main.py"
    harness_path.write_text(
        build_function_harness(
            "solve",
            [{"name": "sample", "args": [2], "kwargs": {}, "expected": 3}],
            reference_code=source,
            generated_samples=[{"name": "generated_1", "args": [3], "kwargs": {}}],
            requested_generated=1,
            mutations=[{"id": "mutant_1", "label": "BinOp_Sub_line_1", "path": "mutant_1.py"}],
            mutation_tests_requested=1,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(harness_path)], capture_output=True, text=True, timeout=5
    )

    marker = "AXIOMA_MUTATION:"
    output = next(line for line in completed.stdout.splitlines() if line.startswith(marker))
    report = json.loads(output[len(marker) :])
    assert completed.returncode == 0
    assert report["requested"] == report["generated"] == 1
    assert report["outcomes"] == [
        {
            "id": "mutant_1",
            "label": "BinOp_Sub_line_1",
            "state": "killed",
            "cases_checked": 1,
        }
    ]
    assert '"name":"sample","outcome":"passed"' in completed.stdout
