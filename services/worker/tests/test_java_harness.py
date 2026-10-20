from axioma_worker.java_harness import build_java_function_harness


def test_java_harness_generates_reflective_array_and_nested_value_checks() -> None:
    source = build_java_function_harness(
        "Solution.twoSum",
        [
            {
                "name": 'unicode "case"',
                "args": [[2, 7], 9],
                "expected": [0, 1],
            }
        ],
    )

    assert 'invokeQuietly("Solution", "twoSum"' in source
    assert "findMethod(type, methodName, args)" in source
    assert "target.isArray() && value instanceof List" in source
    assert (
        'new ArrayList<>(Arrays.asList(new Object[]{Long.valueOf("2"), Long.valueOf("7")}))'
        in source
    )
    assert 'new Case("unicode \\"case\\""' in source
    assert "AXIOMA_RESULT:[" in source


def test_java_complexity_harness_reports_heap_pool_peak_increases() -> None:
    source = build_java_function_harness(
        "Solution.solve",
        [{"name": "sample", "args": [2], "expected": 2}],
        complexity_benchmarks=[
            {"size": size, "args": [size], "strategy": "descending"}
            for size in (10, 20, 40, 80)
        ],
        optimization_enabled=True,
    )

    assert "ManagementFactory.getMemoryPoolMXBeans()" in source
    assert 'new Benchmark(10, "descending", new Object[]{Long.valueOf("10")})' in source
    assert '\\"input_strategy\\"' in source
    assert "pool.resetPeakUsage()" in source
    assert '\\"heap_pool_peak_increase_bytes\\"' in source
    assert '\\"optimized_heap_pool_peak_increase_bytes\\"' in source
    assert "boolean allPropertyChecksPassed = true || propertyValid;" in source


def test_java_harness_checks_reference_before_generated_differential_cases() -> None:
    sample = {"name": "example", "args": [2], "expected": 4}
    source = build_java_function_harness(
        "Solution.solve",
        [sample],
        reference_samples=[sample],
        generated_samples=[
            {
                "name": "generated_1",
                "args": [3],
                "strategy": "exhaustive_integer_domain",
            }
        ],
        requested_generated=2,
    )

    assert 'invokeQuietly("Reference", "solve"' in source
    assert "test.strategy()" in source
    assert "input_strategy" in source


def test_java_harness_can_require_independent_reference_consensus() -> None:
    sample = {"name": "example", "args": [2], "expected": 4}
    source = build_java_function_harness(
        "Solution.solve",
        [sample],
        reference_samples=[sample],
        generated_samples=[{"name": "generated_1", "args": [3]}],
        requested_generated=1,
        independent_reference_enabled=True,
    )

    assert 'invokeQuietly("ReferenceIndependent", "solve"' in source
    assert "independent references disagree" in source
    assert "candidate comparison not run" in source


def test_java_harness_checks_user_property_on_examples_then_generated_cases() -> None:
    sample = {"name": "example", "args": [2], "expected": 4}
    source = build_java_function_harness(
        "Solution.solve",
        [sample],
        property_samples=[{"name": "generated_1", "args": [3]}],
        requested_property_tests=2,
    )

    assert 'Class.forName("AxiomaProperties")' in source
    assert 'getDeclaredMethod("check", Object[].class, Object.class)' in source
    assert 'result("property/" + test.name(), outcome, reason)' in source
    assert '\\"requested\\":2' in source
    assert "propertyCases.size()" in source
    assert "property did not pass its example checks" in source
    assert 'result("reference/" + test.name(), outcome, reason)' in source
    assert 'result("generated_" + (index + 1), "skipped"' in source
    assert "candidate differs from user-supplied reference" in source
    assert 'invokeQuietly("Solution", "solve", test.args())' in source
    assert 'invokeQuietly("Reference", "solve", test.args())' in source
