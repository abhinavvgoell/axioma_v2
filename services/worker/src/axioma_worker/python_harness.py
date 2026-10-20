from __future__ import annotations

import json
from typing import Any


def build_function_harness(
    entrypoint: str,
    samples: list[dict[str, Any]],
    reference_code: str | None = None,
    optimization_code: str | None = None,
    property_code: str | None = None,
    property_samples: list[dict[str, Any]] | None = None,
    requested_property_tests: int = 0,
    generated_samples: list[dict[str, Any]] | None = None,
    requested_generated: int = 0,
    complexity_benchmarks: list[dict[str, Any]] | None = None,
    mutations: list[dict[str, str]] | None = None,
    mutation_tests_requested: int = 0,
    independent_reference_code: str | None = None,
) -> str:
    """Build a runner for examples and optional differential tests."""
    payload = json.dumps(
        {
            "entrypoint": entrypoint,
            "samples": samples,
            "reference_code": reference_code,
            "independent_reference_code": independent_reference_code,
            "optimization_code": optimization_code,
            "property_code": property_code,
            "property_samples": property_samples or [],
            "requested_property_tests": requested_property_tests,
            "generated_samples": generated_samples or [],
            "requested_generated": requested_generated,
            "complexity_benchmarks": complexity_benchmarks or [],
            "mutations": mutations or [],
            "mutation_tests_requested": mutation_tests_requested,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return f"""import contextlib
import copy
import gc
import json
import os
import statistics
import sys
import tracemalloc

spec = json.loads({payload!r})
json_dumps = json.dumps
redirect_stdout = contextlib.redirect_stdout
redirect_stderr = contextlib.redirect_stderr
open_file = open
compile_code = compile
execute_code = exec
set_trace = sys.settrace
median = statistics.median
deepcopy = copy.deepcopy
collect_garbage = gc.collect
trace_start = tracemalloc.start
trace_stop = tracemalloc.stop
trace_get_memory = tracemalloc.get_traced_memory
trace_reset_peak = tracemalloc.reset_peak
trace_is_active = tracemalloc.is_tracing

def load_source(path, module_name):
    namespace = {{"__name__": module_name}}
    try:
        with open_file(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
            with open_file(os.path.join(os.path.dirname(__file__), path), encoding="utf-8") as source_file:
                code = source_file.read()
            execute_code(compile_code(code, path, "exec"), namespace)
        return namespace, None
    except BaseException as exc:
        return namespace, type(exc).__name__ + ": " + str(exc)[:300]

def call(namespace, sample, copy_inputs=True):
    target = namespace
    parts = spec["entrypoint"].split(".")
    for part in parts[:-1]:
        target = target[part] if isinstance(target, dict) else getattr(target, part)
        if isinstance(target, type):
            target = target()
    function = target[parts[-1]] if isinstance(target, dict) else getattr(target, parts[-1])
    with open_file(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
        args = deepcopy(sample.get("args", [])) if copy_inputs else sample.get("args", [])
        kwargs = deepcopy(sample.get("kwargs", {{}})) if copy_inputs else sample.get("kwargs", {{}})
        return function(*args, **kwargs)

def check_property(namespace, sample, result):
    checker = namespace.get("check")
    if not callable(checker):
        raise TypeError("property source must define callable check(args, kwargs, result)")
    with open_file(os.devnull, "w") as sink, redirect_stdout(sink), redirect_stderr(sink):
        value = checker(
            deepcopy(sample.get("args", [])),
            deepcopy(sample.get("kwargs", {{}})),
            deepcopy(result),
        )
    if type(value) is not bool:
        raise TypeError("property check must return bool")
    return value

def count_target_work(namespace, sample):
    target = namespace
    parts = spec["entrypoint"].split(".")
    for part in parts[:-1]:
        target = target[part] if isinstance(target, dict) else getattr(target, part)
        if isinstance(target, type):
            target = target()
    target = target[parts[-1]] if isinstance(target, dict) else getattr(target, parts[-1])
    function = getattr(target, "__func__", target)
    code = function.__code__
    counts = {{"line_events": 0, "opcode_events": 0}}
    def trace(frame, event, arg):
        if frame.f_code is code:
            if event == "call":
                frame.f_trace_opcodes = True
            elif event == "line":
                counts["line_events"] += 1
            elif event == "opcode":
                counts["opcode_events"] += 1
        return trace
    set_trace(trace)
    try:
        call(namespace, sample)
    finally:
        set_trace(None)
    return counts

def measure_peak_traced_bytes(namespace, sample):
    # Prepare fresh inputs outside tracing so input copying does not dominate the measurement.
    prepared = {{"args": deepcopy(sample.get("args", [])), "kwargs": deepcopy(sample.get("kwargs", {{}}))}}
    collect_garbage()
    trace_start()
    try:
        baseline, _ = trace_get_memory()
        trace_reset_peak()
        result = call(namespace, prepared, copy_inputs=False)
        if not trace_is_active():
            return None
        _, peak = trace_get_memory()
        return max(0, int(peak - baseline))
    finally:
        if trace_is_active():
            trace_stop()

def equal(left, right):
    return json_dumps(left, sort_keys=True, separators=(",", ":"), allow_nan=False) == json_dumps(
        right, sort_keys=True, separators=(",", ":"), allow_nan=False
    )

candidate, candidate_error = load_source("submission.py", "axioma_submission")
reference = None
reference_error = None
if spec["reference_code"] is not None:
    reference, reference_error = load_source("reference.py", "axioma_reference")
independent_reference = None
independent_reference_error = None
if spec["independent_reference_code"] is not None:
    independent_reference, independent_reference_error = load_source(
        "independent_reference.py", "axioma_independent_reference"
    )
optimized = None
optimized_error = None
if spec["optimization_code"] is not None:
    optimized, optimized_error = load_source("optimized.py", "axioma_optimized")
property_checker = None
property_error = None
if spec["property_code"] is not None:
    property_checker, property_error = load_source("properties.py", "axioma_properties")

results = []
reference_results = []
optimization_checks = []
reference_valid = reference is not None and reference_error is None
if independent_reference is not None:
    reference_valid = reference_valid and independent_reference_error is None
mutation_samples = []
for sample in spec["samples"]:
    result = {{"name": sample["name"], "outcome": "failed", "details": {{}}}}
    if candidate_error:
        result["details"]["error"] = candidate_error
    else:
        try:
            actual = call(candidate, sample)
            expected = sample["expected"]
            result["outcome"] = "passed" if equal(actual, expected) else "failed"
            if result["outcome"] == "failed":
                result["details"] = {{"expected": expected, "actual": actual}}
        except BaseException as exc:
            result["details"] = {{"error": type(exc).__name__ + ": " + str(exc)[:300]}}
    results.append(result)

    if optimized is not None:
        check = {{"name": "optimization/" + sample["name"], "outcome": "failed", "details": {{}}}}
        if candidate_error or optimized_error:
            check["details"]["error"] = candidate_error or optimized_error
        else:
            try:
                original_output = call(candidate, sample)
                optimized_output = call(optimized, sample)
                equivalent = equal(original_output, optimized_output)
                both_match_expected = equal(original_output, sample["expected"]) and equal(
                    optimized_output, sample["expected"]
                )
                check["outcome"] = "passed" if equivalent and both_match_expected else "failed"
                if check["outcome"] == "failed":
                    check["details"] = {{
                        "original_matches_expected": equal(original_output, sample["expected"]),
                        "optimized_matches_expected": equal(optimized_output, sample["expected"]),
                        "outputs_match": equivalent,
                    }}
            except BaseException as exc:
                check["details"]["error"] = type(exc).__name__ + ": " + str(exc)[:300]
        optimization_checks.append(check)

    if reference is not None:
        check = {{"name": "reference/" + sample["name"], "outcome": "failed", "details": {{}}}}
        if reference_error:
            check["details"]["error"] = reference_error
            reference_valid = False
        else:
            try:
                reference_output = call(reference, sample)
                independent_output = None
                if independent_reference is not None and independent_reference_error is None:
                    independent_output = call(independent_reference, sample)
                reference_matches = equal(reference_output, sample["expected"])
                independent_matches = independent_reference is None or (
                    independent_reference_error is None
                    and equal(independent_output, sample["expected"])
                )
                references_agree = independent_reference is None or (
                    independent_reference_error is None
                    and equal(reference_output, independent_output)
                )
                if reference_matches and independent_matches and references_agree:
                    check["outcome"] = "passed"
                else:
                    check["details"]["reason"] = (
                        "independent references disagree"
                        if not references_agree
                        else "reference output differs from provided sample"
                    )
                    check["details"]["references_agree"] = references_agree
                    reference_valid = False
                if independent_reference is not None:
                    check["details"]["independent_reference_outcome"] = (
                        "passed" if independent_matches and references_agree else "failed"
                    )
            except BaseException as exc:
                check["details"]["error"] = type(exc).__name__ + ": " + str(exc)[:300]
                reference_valid = False
        reference_results.append(check)

if reference_valid:
    mutation_samples.extend(spec["samples"])

results.extend(reference_results)
if reference is not None:
    for sample in spec["generated_samples"]:
        result = {{
            "name": sample["name"],
            "outcome": "skipped",
            "details": {{"reason": "reference did not pass all provided samples"}},
        }}
        if reference_valid:
            references_agree = True
            try:
                reference_output = call(reference, sample)
                independent_output = (
                    call(independent_reference, sample)
                    if independent_reference is not None
                    else reference_output
                )
                if not equal(reference_output, independent_output):
                    references_agree = False
                    result["details"] = {{
                        "reason": "independent references disagree; candidate comparison not run",
                        "references_agree": False,
                        "input_strategy": sample.get("strategy", "unspecified"),
                    }}
                else:
                    actual = call(candidate, sample)
                    result["outcome"] = "passed" if equal(actual, reference_output) else "failed"
                    result["details"] = {{
                        "comparison": "candidate against corroborated user-supplied references"
                        if independent_reference is not None
                        else "candidate against user-supplied reference",
                        "references_agree": True,
                        "input_strategy": sample.get("strategy", "unspecified"),
                    }}
            except BaseException as exc:
                result["outcome"] = "failed"
                result["details"] = {{"error": type(exc).__name__ + ": " + str(exc)[:300]}}
            else:
                if references_agree and result["outcome"] == "passed":
                    mutation_samples.append(sample)
        results.append(result)
        if optimized is not None:
            check = {{"name": "optimization/" + sample["name"], "outcome": "skipped", "details": {{}}}}
            if not reference_valid:
                check["details"]["reason"] = "reference did not pass all provided samples"
            elif optimized_error or candidate_error:
                check["outcome"] = "failed"
                check["details"]["error"] = candidate_error or optimized_error
            else:
                try:
                    original_output = call(candidate, sample)
                    optimized_output = call(optimized, sample)
                    reference_output = call(reference, sample)
                    independent_output = (
                        call(independent_reference, sample)
                        if independent_reference is not None
                        else reference_output
                    )
                    if not equal(reference_output, independent_output):
                        check["details"]["reason"] = "independent references disagree"
                        optimization_checks.append(check)
                        continue
                    equivalent = equal(original_output, optimized_output)
                    both_match_reference = equal(original_output, reference_output) and equal(
                        optimized_output, reference_output
                    )
                    check["outcome"] = "passed" if equivalent and both_match_reference else "failed"
                    if check["outcome"] == "failed":
                        check["details"] = {{
                            "original_matches_reference": equal(original_output, reference_output),
                            "optimized_matches_reference": equal(optimized_output, reference_output),
                            "outputs_match": equivalent,
                        }}
                except BaseException as exc:
                    check["outcome"] = "failed"
                    check["details"]["error"] = type(exc).__name__ + ": " + str(exc)[:300]
            optimization_checks.append(check)
    for index in range(len(spec["generated_samples"]), spec["requested_generated"]):
        results.append({{
            "name": "generated_" + str(index + 1),
            "outcome": "skipped",
            "details": {{"reason": "no distinct valid input could be generated"}},
        }})
        if optimized is not None:
            optimization_checks.append({{
                "name": "optimization/generated_" + str(index + 1),
                "outcome": "skipped",
                "details": {{"reason": "no distinct valid input could be generated"}},
            }})

if optimized is not None:
    print("AXIOMA_OPTIMIZATION:" + json_dumps({{
        "checks": optimization_checks,
        "requested": len(spec["samples"]) + spec["requested_generated"],
        "checked": len(optimization_checks),
    }}, sort_keys=True, separators=(",", ":")))

if property_checker is not None:
    example_checks = []
    property_valid = property_error is None
    for index, sample in enumerate(spec["samples"]):
        check = {{"name": "property/" + sample["name"], "outcome": "skipped", "details": {{}}}}
        if property_error:
            check["details"]["error"] = property_error
            property_valid = False
        elif results[index]["outcome"] != "passed":
            check["details"]["reason"] = "candidate did not pass the provided example"
            property_valid = False
        else:
            try:
                output = call(candidate, sample)
                valid = check_property(property_checker, sample, output)
                check["outcome"] = "passed" if valid else "failed"
                if not valid:
                    check["details"]["reason"] = "property returned false for a provided example"
                    property_valid = False
            except BaseException as exc:
                check["outcome"] = "failed"
                check["details"]["error"] = type(exc).__name__ + ": " + str(exc)[:300]
                property_valid = False
        example_checks.append(check)

    generated_checks = []
    for sample in spec["property_samples"]:
        check = {{"name": sample["name"], "outcome": "skipped", "details": {{}}}}
        if not property_valid:
            check["details"]["reason"] = "property did not pass its example checks"
        else:
            try:
                output = call(candidate, sample)
                valid = check_property(property_checker, sample, output)
                check["outcome"] = "passed" if valid else "failed"
                if not valid:
                    check["details"]["reason"] = "property returned false"
            except BaseException as exc:
                check["outcome"] = "failed"
                check["details"]["error"] = type(exc).__name__ + ": " + str(exc)[:300]
        generated_checks.append(check)
    for index in range(len(generated_checks), spec["requested_property_tests"]):
        generated_checks.append({{
            "name": "property/generated_" + str(index + 1),
            "outcome": "skipped",
            "details": {{"reason": "no distinct valid input could be generated"}},
        }})
    print("AXIOMA_PROPERTY:" + json_dumps({{
        "example_checks": example_checks,
        "generated_checks": generated_checks,
        "requested": spec["requested_property_tests"],
        "generated": len(spec["property_samples"]),
        "property_validated_on_examples": property_valid,
        "property_code": spec["property_code"],
        "limit": "Matching examples does not prove a user-supplied property is universally valid.",
    }}, sort_keys=True, separators=(",", ":")))

print("AXIOMA_RESULT:" + json_dumps(results, sort_keys=True, separators=(",", ":")))

benchmark_report = {{"measurements": [], "optimized_measurements": [], "skipped_reason": None}}
if spec["complexity_benchmarks"]:
    if candidate_error:
        benchmark_report["skipped_reason"] = "candidate could not be loaded"
    elif not results or any(item["outcome"] != "passed" for item in results):
        benchmark_report["skipped_reason"] = "candidate did not pass all configured checks"
    else:
        try:
            for benchmark in spec["complexity_benchmarks"]:
                sample = {{"args": benchmark["args"], "kwargs": benchmark["kwargs"]}}
                counts = [count_target_work(candidate, sample) for _ in range(3)]
                memory_samples = []
                for _ in range(3):
                    peak_bytes = measure_peak_traced_bytes(candidate, sample)
                    if peak_bytes is None:
                        benchmark_report["memory_skipped_reason"] = (
                            "submission disabled tracemalloc during the target call"
                        )
                        memory_samples = []
                        break
                    memory_samples.append(peak_bytes)
                measurement = {{
                    "size": benchmark["size"],
                    "input_strategy": benchmark.get("strategy") or "user_supplied",
                    "line_events": int(median([item["line_events"] for item in counts])),
                    "opcode_events": int(median([item["opcode_events"] for item in counts])),
                }}
                if memory_samples:
                    measurement["peak_traced_bytes"] = int(median(memory_samples))
                benchmark_report["measurements"].append(measurement)
                if (
                    optimized is not None
                    and not optimized_error
                    and optimization_checks
                    and all(item["outcome"] == "passed" for item in optimization_checks)
                ):
                    optimized_counts = [count_target_work(optimized, sample) for _ in range(3)]
                    optimized_memory_samples = []
                    for _ in range(3):
                        peak_bytes = measure_peak_traced_bytes(optimized, sample)
                        if peak_bytes is None:
                            benchmark_report["memory_skipped_reason"] = (
                                "optimization candidate disabled tracemalloc during the target call"
                            )
                            optimized_memory_samples = []
                            break
                        optimized_memory_samples.append(peak_bytes)
                    optimized_measurement = {{
                        **measurement,
                        "optimized_line_events": int(median([item["line_events"] for item in optimized_counts])),
                        "optimized_opcode_events": int(median([item["opcode_events"] for item in optimized_counts])),
                    }}
                    if optimized_memory_samples:
                        optimized_measurement["optimized_peak_traced_bytes"] = int(
                            median(optimized_memory_samples)
                        )
                    benchmark_report["optimized_measurements"].append(optimized_measurement)
            if optimized is not None and not benchmark_report["optimized_measurements"]:
                benchmark_report["optimized_skipped_reason"] = (
                    optimized_error or "optimization equivalence checks did not all pass"
                )
        except BaseException as exc:
            benchmark_report["measurements"] = []
            benchmark_report["skipped_reason"] = type(exc).__name__ + ": " + str(exc)[:300]
print("AXIOMA_COMPLEXITY:" + json_dumps(benchmark_report, sort_keys=True, separators=(",", ":")))

mutation_report = {{
    "requested": spec["mutation_tests_requested"],
    "generated": len(spec["mutations"]),
    "outcomes": [],
}}
for mutant in spec["mutations"]:
    outcome = {{"id": mutant["id"], "label": mutant["label"], "state": "not_run", "cases_checked": 0}}
    if not reference_valid or not mutation_samples:
        outcome["reason"] = "reference did not pass its configured sample checks"
    else:
        mutant_namespace, mutant_error = load_source(mutant["path"], "axioma_" + mutant["id"])
        if mutant_error:
            outcome["state"] = "invalid"
            outcome["reason"] = mutant_error
        else:
            outcome["state"] = "survived"
            for sample in mutation_samples:
                outcome["cases_checked"] += 1
                try:
                    original_value = call(reference, sample)
                    mutated_value = call(mutant_namespace, sample)
                    if not equal(original_value, mutated_value):
                        outcome["state"] = "killed"
                        break
                except BaseException as exc:
                    outcome["state"] = "killed"
                    outcome["reason"] = type(exc).__name__ + ": " + str(exc)[:300]
                    break
    mutation_report["outcomes"].append(outcome)
print("AXIOMA_MUTATION:" + json_dumps(mutation_report, sort_keys=True, separators=(",", ":")))
"""
