from __future__ import annotations

from typing import Any


def _java_string(value: str) -> str:
    escaped: list[str] = []
    for char in value:
        codepoint = ord(char)
        if char == '"':
            escaped.append('\\"')
        elif char == "\\":
            escaped.append("\\\\")
        elif char == "\n":
            escaped.append("\\n")
        elif char == "\r":
            escaped.append("\\r")
        elif char == "\t":
            escaped.append("\\t")
        elif char == "\b":
            escaped.append("\\b")
        elif char == "\f":
            escaped.append("\\f")
        elif codepoint < 32 or codepoint == 127:
            escaped.append(f"\\{codepoint:03o}")
        elif codepoint <= 126:
            escaped.append(char)
        elif codepoint <= 0xFFFF:
            escaped.append(f"\\u{codepoint:04x}")
        else:
            codepoint -= 0x10000
            escaped.append(f"\\u{0xD800 + (codepoint >> 10):04x}")
            escaped.append(f"\\u{0xDC00 + (codepoint & 0x3FF):04x}")
    return '"' + "".join(escaped) + '"'


def _java_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return f"Boolean.valueOf({str(value).lower()})"
    if isinstance(value, int):
        return f"Long.valueOf({_java_string(str(value))})"
    if isinstance(value, float):
        return f"Double.valueOf({_java_string(repr(value))})"
    if isinstance(value, str):
        return _java_string(value)
    if isinstance(value, list):
        values = ", ".join(_java_value(item) for item in value)
        return f"new ArrayList<>(Arrays.asList(new Object[]{{{values}}}))"
    if isinstance(value, dict):
        values = ", ".join(
            f"{_java_string(str(key))}, {_java_value(item)}" for key, item in value.items()
        )
        return f"map({values})"
    raise ValueError(f"Unsupported value in Java function sample: {type(value).__name__}")


def _case_source(sample: dict[str, Any], *, include_expected: bool) -> str:
    args = ", ".join(_java_value(value) for value in sample.get("args", []))
    expected = _java_value(sample["expected"]) if include_expected else "null"
    strategy = _java_string(sample.get("strategy", "provided_example"))
    return f"new Case({_java_string(sample['name'])}, new Object[]{{{args}}}, {expected}, {strategy})"


def build_java_function_harness(
    entrypoint: str,
    samples: list[dict[str, Any]],
    reference_samples: list[dict[str, Any]] | None = None,
    generated_samples: list[dict[str, Any]] | None = None,
    requested_generated: int = 0,
    property_samples: list[dict[str, Any]] | None = None,
    requested_property_tests: int = 0,
    optimization_enabled: bool = False,
    complexity_benchmarks: list[dict[str, Any]] | None = None,
    independent_reference_enabled: bool = False,
    mutations: list[dict[str, str]] | None = None,
    mutation_tests_requested: int = 0,
) -> str:
    class_name, method_name = entrypoint.split(".", maxsplit=1)
    cases_source = ",\n            ".join(
        _case_source(sample, include_expected=True) for sample in samples
    )
    reference_cases_source = ",\n            ".join(
        _case_source(sample, include_expected=True) for sample in (reference_samples or [])
    )
    generated_cases = generated_samples or []
    generated_cases_source = ",\n            ".join(
        _case_source(sample, include_expected=False) for sample in generated_cases
    )
    property_cases = property_samples or []
    property_cases_source = ",\n            ".join(
        _case_source(sample, include_expected=False) for sample in property_cases
    )
    benchmark_cases = complexity_benchmarks or []
    benchmark_cases_source = ",\n            ".join(
        "new Benchmark(" + str(sample["size"]) + ", new Object[]{"
        + ", ".join(_java_value(value) for value in sample.get("args", []))
        + "})"
        for sample in benchmark_cases
    )
    mutation_cases_source = ",\n            ".join(
        "new Mutation(" + ", ".join(
            _java_string(mutant[key]) for key in ("id", "label", "class_name")
        ) + ")"
        for mutant in (mutations or [])
    )
    return f"""import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.lang.reflect.Array;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryPoolMXBean;
import java.lang.management.MemoryType;
import java.lang.management.MemoryUsage;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

public class Harness {{
    record Case(String name, Object[] args, Object expected, String strategy) {{}}
    record Benchmark(int size, Object[] args) {{}}
    record Mutation(String id, String label, String className) {{}}
    record MutationResult(String state, int casesChecked) {{}}

    static Map<String, Object> map(Object... values) {{
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < values.length; i += 2) {{
            result.put((String) values[i], values[i + 1]);
        }}
        return result;
    }}

    static Object convert(Object value, Class<?> target) {{
        if (value == null) {{
            if (target.isPrimitive()) throw new IllegalArgumentException("null for primitive parameter");
            return null;
        }}
        if (target.isInstance(value) || target == Object.class) return value;
        if (target.isArray() && value instanceof List<?> values) {{
            Object array = Array.newInstance(target.getComponentType(), values.size());
            for (int i = 0; i < values.size(); i++) Array.set(array, i, convert(values.get(i), target.getComponentType()));
            return array;
        }}
        if ((target == int.class || target == Integer.class) && value instanceof Number n) return n.intValue();
        if ((target == long.class || target == Long.class) && value instanceof Number n) return n.longValue();
        if ((target == short.class || target == Short.class) && value instanceof Number n) return n.shortValue();
        if ((target == byte.class || target == Byte.class) && value instanceof Number n) return n.byteValue();
        if ((target == double.class || target == Double.class) && value instanceof Number n) return n.doubleValue();
        if ((target == float.class || target == Float.class) && value instanceof Number n) return n.floatValue();
        if ((target == boolean.class || target == Boolean.class) && value instanceof Boolean) return value;
        if ((target == char.class || target == Character.class) && value instanceof String text && text.length() == 1) return text.charAt(0);
        if (target == String.class && value instanceof String) return value;
        if (Map.class.isAssignableFrom(target) && value instanceof Map<?, ?> values) {{
            if (target.isInstance(value)) return value;
            if (target.isInterface()) return new LinkedHashMap<>(values);
            try {{
                Map<Object, Object> converted = (Map<Object, Object>) target.getDeclaredConstructor().newInstance();
                converted.putAll(values);
                return converted;
            }} catch (ReflectiveOperationException error) {{ throw new IllegalArgumentException("Cannot construct map parameter", error); }}
        }}
        if (List.class.isAssignableFrom(target) && value instanceof List<?> values) {{
            if (target.isInstance(value)) return value;
            if (target.isInterface()) return new ArrayList<>(values);
            try {{
                List<Object> converted = (List<Object>) target.getDeclaredConstructor().newInstance();
                converted.addAll(values);
                return converted;
            }} catch (ReflectiveOperationException error) {{ throw new IllegalArgumentException("Cannot construct list parameter", error); }}
        }}
        throw new IllegalArgumentException("Cannot convert sample argument to " + target.getTypeName());
    }}

    static List<?> values(Object value) {{
        if (value instanceof List<?> list) return list;
        if (value != null && value.getClass().isArray()) {{
            List<Object> list = new ArrayList<>();
            for (int i = 0; i < Array.getLength(value); i++) list.add(Array.get(value, i));
            return list;
        }}
        return null;
    }}

    static boolean equal(Object left, Object right) {{
        if (left instanceof Number && right instanceof Number) {{
            return new BigDecimal(left.toString()).compareTo(new BigDecimal(right.toString())) == 0;
        }}
        List<?> leftValues = values(left), rightValues = values(right);
        if (leftValues != null || rightValues != null) {{
            if (leftValues == null || rightValues == null || leftValues.size() != rightValues.size()) return false;
            for (int i = 0; i < leftValues.size(); i++) if (!equal(leftValues.get(i), rightValues.get(i))) return false;
            return true;
        }}
        if (left instanceof Map<?, ?> leftMap && right instanceof Map<?, ?> rightMap) {{
            if (!leftMap.keySet().equals(rightMap.keySet())) return false;
            for (Object key : leftMap.keySet()) if (!equal(leftMap.get(key), rightMap.get(key))) return false;
            return true;
        }}
        return java.util.Objects.equals(left, right);
    }}

    static String quote(String value) {{
        StringBuilder out = new StringBuilder("\\\"");
        for (char c : value.toCharArray()) {{
            switch (c) {{
                case '\\\\' -> out.append("\\\\\\\\");
                case '\\"' -> out.append("\\\\\\\"");
                case '\\n' -> out.append("\\\\n");
                case '\\r' -> out.append("\\\\r");
                case '\\t' -> out.append("\\\\t");
                default -> {{ if (c < 32) out.append(String.format("\\\\u%04x", (int)c)); else out.append(c); }}
            }}
        }}
        return out.append('\\"').toString();
    }}

    static Method findMethod(Class<?> type, String name, Object[] args) throws Exception {{
        Method[] methods = type.getDeclaredMethods();
        Arrays.sort(methods, Comparator.comparing(Method::toGenericString));
        for (Method method : methods) {{
            if (!method.getName().equals(name) || method.getParameterCount() != args.length) continue;
            try {{
                Class<?>[] types = method.getParameterTypes();
                for (int i = 0; i < types.length; i++) convert(args[i], types[i]);
                return method;
            }} catch (RuntimeException ignored) {{}}
        }}
        throw new NoSuchMethodException(name + " with " + args.length + " compatible parameters");
    }}

    static Object invoke(String className, String methodName, Object[] args) throws Exception {{
        return invoke(Class.forName(className), methodName, args);
    }}

    static Object invoke(Class<?> type, String methodName, Object[] args) throws Exception {{
        Method method = findMethod(type, methodName, args);
        method.setAccessible(true);
        Object receiver = null;
        if (!Modifier.isStatic(method.getModifiers())) {{
            var constructor = type.getDeclaredConstructor();
            constructor.setAccessible(true);
            receiver = constructor.newInstance();
        }}
        Object[] converted = new Object[args.length];
        Class<?>[] parameterTypes = method.getParameterTypes();
        for (int i = 0; i < converted.length; i++) converted[i] = convert(args[i], parameterTypes[i]);
        return method.invoke(receiver, converted);
    }}

    static Object invokeQuietly(String className, String methodName, Object[] args) throws Exception {{
        PrintStream out = System.out, err = System.err;
        try {{
            System.setOut(new PrintStream(new ByteArrayOutputStream()));
            System.setErr(new PrintStream(new ByteArrayOutputStream()));
            return invoke(className, methodName, copyArgs(args));
        }} finally {{ System.setOut(out); System.setErr(err); }}
    }}

    static Object invokeQuietly(Class<?> type, String methodName, Object[] args) throws Exception {{
        PrintStream out = System.out, err = System.err;
        try {{
            System.setOut(new PrintStream(new ByteArrayOutputStream()));
            System.setErr(new PrintStream(new ByteArrayOutputStream()));
            return invoke(type, methodName, copyArgs(args));
        }} finally {{ System.setOut(out); System.setErr(err); }}
    }}

    static MutationResult runMutation(Mutation mutant, List<Case> referenceCases, List<Case> generatedCases,
            boolean referenceValid, String methodName) {{
        if (!referenceValid || referenceCases.isEmpty()) return new MutationResult("not_run", 0);
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) return new MutationResult("not_run", 0);
        Path work = Path.of("/work");
        Path output = work.resolve("mutants").resolve(mutant.id());
        try {{
            Files.createDirectories(output);
            DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
            try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, null, null)) {{
                Iterable<? extends JavaFileObject> units = manager.getJavaFileObjects(work.resolve(mutant.className() + ".java").toFile());
                Boolean compiled = compiler.getTask(null, manager, diagnostics,
                    Arrays.asList("-proc:none", "-classpath", work.toString(), "-d", output.toString()),
                    null, units).call();
                if (!Boolean.TRUE.equals(compiled)) return new MutationResult("invalid", 0);
            }}
            try (URLClassLoader loader = new URLClassLoader(new URL[]{{output.toUri().toURL()}}, Harness.class.getClassLoader())) {{
                Class<?> mutantType = Class.forName(mutant.className(), true, loader);
                List<Case> checks = new ArrayList<>(referenceCases);
                checks.addAll(generatedCases);
                boolean killed = false;
                int checked = 0;
                for (Case test : checks) {{
                    Object expected = invokeQuietly("Reference", methodName, test.args());
                    try {{
                        Object actual = invokeQuietly(mutantType, methodName, test.args());
                        if (!equal(expected, actual)) killed = true;
                    }} catch (Throwable mutantError) {{ killed = true; }}
                    checked++;
                }}
                return new MutationResult(killed ? "killed" : "survived", checked);
            }}
        }} catch (Throwable error) {{
            return new MutationResult("invalid", 0);
        }}
    }}

    static Object copyValue(Object value) {{
        if (value instanceof List<?> items) {{
            List<Object> copy = new ArrayList<>();
            for (Object item : items) copy.add(copyValue(item));
            return copy;
        }}
        if (value instanceof Map<?, ?> items) {{
            Map<Object, Object> copy = new LinkedHashMap<>();
            for (Map.Entry<?, ?> item : items.entrySet()) copy.put(item.getKey(), copyValue(item.getValue()));
            return copy;
        }}
        if (value != null && value.getClass().isArray()) {{
            int length = Array.getLength(value);
            Object copy = Array.newInstance(value.getClass().getComponentType(), length);
            for (int index = 0; index < length; index++) Array.set(copy, index, copyValue(Array.get(value, index)));
            return copy;
        }}
        return value;
    }}

    static Object[] copyArgs(Object[] args) {{
        Object[] copy = new Object[args.length];
        for (int index = 0; index < args.length; index++) copy[index] = copyValue(args[index]);
        return copy;
    }}

    static boolean checkProperty(Object[] args, Object output) throws Exception {{
        Class<?> properties = Class.forName("AxiomaProperties");
        Method check = properties.getDeclaredMethod("check", Object[].class, Object.class);
        check.setAccessible(true);
        PrintStream out = System.out, err = System.err;
        try {{
            System.setOut(new PrintStream(new ByteArrayOutputStream()));
            System.setErr(new PrintStream(new ByteArrayOutputStream()));
            Object value = check.invoke(null, new Object[]{{copyArgs(args), copyValue(output)}});
            if (!(value instanceof Boolean)) throw new IllegalStateException("property check must return boolean");
            return (Boolean) value;
        }} finally {{ System.setOut(out); System.setErr(err); }}
    }}

    static long medianElapsed(String className, String methodName, Object[] args) throws Exception {{
        PrintStream out = System.out, err = System.err;
        try {{
            System.setOut(new PrintStream(new ByteArrayOutputStream()));
            System.setErr(new PrintStream(new ByteArrayOutputStream()));
            for (int warmup = 0; warmup < 5; warmup++) invoke(className, methodName, copyArgs(args));
            long[] elapsed = new long[9];
            for (int trial = 0; trial < elapsed.length; trial++) {{
                long start = System.nanoTime();
                invoke(className, methodName, copyArgs(args));
                elapsed[trial] = System.nanoTime() - start;
            }}
            Arrays.sort(elapsed);
            return elapsed[elapsed.length / 2];
        }} finally {{ System.setOut(out); System.setErr(err); }}
    }}

    static Long medianHeapPoolPeakIncrease(String className, String methodName, Object[] args) throws Exception {{
        PrintStream out = System.out, err = System.err;
        try {{
            System.setOut(new PrintStream(new ByteArrayOutputStream()));
            System.setErr(new PrintStream(new ByteArrayOutputStream()));
            List<MemoryPoolMXBean> pools = new ArrayList<>();
            for (MemoryPoolMXBean pool : ManagementFactory.getMemoryPoolMXBeans()) {{
                if (pool.getType() != MemoryType.HEAP) continue;
                try {{
                    pool.resetPeakUsage();
                    if (pool.getPeakUsage() != null && pool.getUsage() != null) pools.add(pool);
                }} catch (UnsupportedOperationException ignored) {{ }}
            }}
            if (pools.isEmpty()) return null;
            for (int warmup = 0; warmup < 5; warmup++) invoke(className, methodName, copyArgs(args));
            long[] deltas = new long[9];
            for (int trial = 0; trial < deltas.length; trial++) {{
                long[] before = new long[pools.size()];
                for (int index = 0; index < pools.size(); index++) {{
                    MemoryPoolMXBean pool = pools.get(index);
                    MemoryUsage usage = pool.getUsage();
                    before[index] = usage == null ? 0 : usage.getUsed();
                    pool.resetPeakUsage();
                }}
                invoke(className, methodName, copyArgs(args));
                long delta = 0;
                for (int index = 0; index < pools.size(); index++) {{
                    MemoryUsage peak = pools.get(index).getPeakUsage();
                    if (peak != null) delta += Math.max(0L, peak.getUsed() - before[index]);
                }}
                deltas[trial] = delta;
            }}
            Arrays.sort(deltas);
            return deltas[deltas.length / 2];
        }} finally {{ System.setOut(out); System.setErr(err); }}
    }}

    static String result(String name, String outcome, String reason) {{
        return result(name, outcome, reason, "");
    }}

    static String result(String name, String outcome, String reason, String strategy) {{
        String value = "{{\\\"name\\\":" + quote(name) + ",\\\"outcome\\\":" + quote(outcome)
            + ",\\\"details\\\":{{\\\"reason\\\":" + quote(reason);
        if (!strategy.isEmpty()) value += ",\\\"input_strategy\\\":" + quote(strategy);
        return value + "}}}}";
    }}

    static String benchmarkResult(int size, long elapsed, Long heapPoolPeakIncrease, Long optimizedElapsed, Long optimizedHeapPoolPeakIncrease) {{
        String value = "{{\\\"size\\\":" + size + ",\\\"elapsed_ns\\\":" + elapsed
            + ",\\\"warmups\\\":5,\\\"trials\\\":9";
        if (heapPoolPeakIncrease != null) value += ",\\\"heap_pool_peak_increase_bytes\\\":" + heapPoolPeakIncrease;
        if (optimizedElapsed != null) value += ",\\\"optimized_elapsed_ns\\\":" + optimizedElapsed;
        if (optimizedHeapPoolPeakIncrease != null) value += ",\\\"optimized_heap_pool_peak_increase_bytes\\\":" + optimizedHeapPoolPeakIncrease;
        return value + "}}";
    }}

    public static void main(String[] ignored) throws Exception {{
        List<Case> cases = Arrays.asList(
            {cases_source}
        );
        List<Case> referenceCases = Arrays.asList({reference_cases_source});
        List<Case> generatedCases = Arrays.asList({generated_cases_source});
        List<Case> propertyCases = Arrays.asList({property_cases_source});
        List<Benchmark> benchmarkCases = Arrays.asList({benchmark_cases_source});
        List<Mutation> mutationCases = Arrays.asList({mutation_cases_source});
        List<String> results = new ArrayList<>();
        List<String> sampleOutcomes = new ArrayList<>();
        List<String> generatedOutcomes = new ArrayList<>();
        boolean allExecutionChecksPassed = true;
        for (Case test : cases) {{
            String outcome = "failed", reason = "wrong answer";
            try {{
                Object actual = invokeQuietly({_java_string(class_name)}, {_java_string(method_name)}, test.args());
                if (equal(actual, test.expected())) {{ outcome = "passed"; reason = ""; }}
            }} catch (Throwable error) {{
                Throwable cause = error instanceof java.lang.reflect.InvocationTargetException && error.getCause() != null ? error.getCause() : error;
                reason = cause.getClass().getSimpleName() + ": " + String.valueOf(cause.getMessage());
                if (reason.length() > 300) reason = reason.substring(0, 300);
            }}
            sampleOutcomes.add(outcome);
            allExecutionChecksPassed &= outcome.equals("passed");
            results.add(result(test.name(), outcome, reason, test.strategy()));
        }}
        boolean referenceValid = !referenceCases.isEmpty();
        for (Case test : referenceCases) {{
            String outcome = "failed", reason = "reference output differs from provided sample";
            try {{
                Object actual = invokeQuietly("Reference", {_java_string(method_name)}, test.args());
                if (equal(actual, test.expected())) {{ outcome = "passed"; reason = ""; }}
                if ({str(independent_reference_enabled).lower()}) {{
                    Object independent = invokeQuietly("ReferenceIndependent", {_java_string(method_name)}, test.args());
                    if (!equal(actual, independent)) {{ outcome = "failed"; reason = "independent references disagree"; }}
                    else if (!equal(independent, test.expected())) {{ outcome = "failed"; reason = "independent reference differs from provided sample"; }}
                }}
            }} catch (Throwable error) {{
                Throwable cause = error instanceof java.lang.reflect.InvocationTargetException && error.getCause() != null ? error.getCause() : error;
                reason = cause.getClass().getSimpleName() + ": " + String.valueOf(cause.getMessage());
                if (reason.length() > 300) reason = reason.substring(0, 300);
            }}
            referenceValid &= outcome.equals("passed");
            allExecutionChecksPassed &= outcome.equals("passed");
            results.add(result("reference/" + test.name(), outcome, reason));
        }}
        for (Case test : generatedCases) {{
            String outcome = "skipped", reason = "reference did not pass all provided samples";
            if (referenceValid) {{
                try {{
                    Object expected = invokeQuietly("Reference", {_java_string(method_name)}, test.args());
                    Object independent = expected;
                    if ({str(independent_reference_enabled).lower()}) independent = invokeQuietly("ReferenceIndependent", {_java_string(method_name)}, test.args());
                    if (!equal(expected, independent)) {{
                        outcome = "skipped";
                        reason = "independent references disagree; candidate comparison not run";
                    }} else {{
                        Object actual = invokeQuietly({_java_string(class_name)}, {_java_string(method_name)}, test.args());
                        outcome = equal(actual, expected) ? "passed" : "failed";
                        reason = outcome.equals("passed") ? "" : {_java_string('candidate differs from corroborated user-supplied references' if independent_reference_enabled else 'candidate differs from user-supplied reference')};
                    }}
                    allExecutionChecksPassed &= outcome.equals("passed");
                }} catch (Throwable error) {{
                    Throwable cause = error instanceof java.lang.reflect.InvocationTargetException && error.getCause() != null ? error.getCause() : error;
                    outcome = "failed";
                    allExecutionChecksPassed = false;
                    reason = cause.getClass().getSimpleName() + ": " + String.valueOf(cause.getMessage());
                    if (reason.length() > 300) reason = reason.substring(0, 300);
                }}
            }}
            allExecutionChecksPassed &= outcome.equals("passed");
            generatedOutcomes.add(outcome);
            results.add(result(test.name(), outcome, reason, test.strategy()));
        }}
        if ({str(mutation_tests_requested > 0).lower()}) {{
            List<String> mutationOutcomes = new ArrayList<>();
            for (Mutation mutant : mutationCases) {{
                MutationResult mutation = runMutation(mutant, referenceCases, generatedCases, referenceValid, {_java_string(method_name)});
                String state = mutation.state();
                mutationOutcomes.add("{{\\\"id\\\":" + quote(mutant.id()) + ",\\\"label\\\":" + quote(mutant.label())
                    + ",\\\"state\\\":" + quote(state) + ",\\\"cases_checked\\\":"
                    + mutation.casesChecked() + "}}");
            }}
            String reason = referenceValid ? (ToolProvider.getSystemJavaCompiler() == null ? "JDK compiler unavailable" : "")
                : "reference did not pass validation samples";
            System.out.println("AXIOMA_MUTATION:{{\\\"requested\\\":{mutation_tests_requested},\\\"generated\\\":"
                + mutationCases.size() + ",\\\"outcomes\\\":[" + String.join(",", mutationOutcomes)
                + "],\\\"reason\\\":" + quote(reason) + "}}");
        }}
        for (int index = generatedCases.size(); index < {requested_generated}; index++) {{
            allExecutionChecksPassed = false;
            results.add(result("generated_" + (index + 1), "skipped", "no distinct valid input could be generated"));
        }}
        List<String> propertyExampleResults = new ArrayList<>();
        boolean propertyValid = {str(requested_property_tests == 0).lower()};
        if ({str(requested_property_tests > 0).lower()}) {{
            propertyValid = true;
        for (int index = 0; index < cases.size(); index++) {{
            Case test = cases.get(index);
            String outcome = "skipped", reason = "candidate did not pass the provided example";
            if (sampleOutcomes.get(index).equals("passed")) {{
                try {{
                    outcome = checkProperty(test.args(), test.expected()) ? "passed" : "failed";
                    reason = outcome.equals("passed") ? "" : "property returned false for a provided example";
                }} catch (Throwable error) {{
                    outcome = "failed";
                    reason = error.getClass().getSimpleName() + ": " + String.valueOf(error.getMessage());
                    if (reason.length() > 300) reason = reason.substring(0, 300);
                }}
            }}
            propertyValid &= outcome.equals("passed");
            propertyExampleResults.add(result("property/" + test.name(), outcome, reason));
        }}
        }}
        List<String> propertyGeneratedResults = new ArrayList<>();
        boolean allPropertyChecksPassed = {str(requested_property_tests == 0).lower()} || propertyValid;
        if ({str(requested_property_tests > 0).lower()}) {{
        for (Case test : propertyCases) {{
            String outcome = "skipped", reason = "property did not pass its example checks";
            if (propertyValid) {{
                try {{
                    Object output = invokeQuietly({_java_string(class_name)}, {_java_string(method_name)}, test.args());
                    outcome = checkProperty(test.args(), output) ? "passed" : "failed";
                    reason = outcome.equals("passed") ? "" : "property returned false";
                }} catch (Throwable error) {{
                    outcome = "failed";
                    reason = error.getClass().getSimpleName() + ": " + String.valueOf(error.getMessage());
                    if (reason.length() > 300) reason = reason.substring(0, 300);
                }}
            }}
            allPropertyChecksPassed &= outcome.equals("passed");
            propertyGeneratedResults.add(result("property/" + test.name(), outcome, reason));
        }}
        for (int index = propertyCases.size(); index < {requested_property_tests}; index++) {{
            allPropertyChecksPassed = false;
            propertyGeneratedResults.add(result("property/generated_" + (index + 1), "skipped", "no distinct valid input could be generated"));
        }}
        }}
        System.out.println("AXIOMA_PROPERTY:{{\\\"example_checks\\\":[" + String.join(",", propertyExampleResults)
            + "],\\\"generated_checks\\\":[" + String.join(",", propertyGeneratedResults)
            + "],\\\"requested\\\":{requested_property_tests},\\\"generated\\\":" + propertyCases.size()
            + ",\\\"property_validated_on_examples\\\":"
            + ({str(requested_property_tests > 0).lower()} ? Boolean.toString(propertyValid) : "null") + "}}");

        List<String> optimizationResults = new ArrayList<>();
        boolean optimizationValid = {str(optimization_enabled).lower()};
        if ({str(optimization_enabled).lower()}) {{
            for (int index = 0; index < cases.size(); index++) {{
                Case test = cases.get(index);
                String outcome = "skipped", reason = "candidate did not pass the provided example";
                if (sampleOutcomes.get(index).equals("passed")) {{
                    try {{
                        Object actual = invokeQuietly("AxiomaOptimized", {_java_string(method_name)}, test.args());
                        outcome = equal(actual, test.expected()) ? "passed" : "failed";
                        reason = outcome.equals("passed") ? "" : "optimized output differs from expected output";
                    }} catch (Throwable error) {{
                        Throwable cause = error instanceof java.lang.reflect.InvocationTargetException && error.getCause() != null ? error.getCause() : error;
                        outcome = "failed";
                        reason = cause.getClass().getSimpleName() + ": " + String.valueOf(cause.getMessage());
                        if (reason.length() > 300) reason = reason.substring(0, 300);
                    }}
                }}
                optimizationResults.add(result("optimization/" + test.name(), outcome, reason));
            }}
            for (int index = 0; index < generatedCases.size(); index++) {{
                Case test = generatedCases.get(index);
                String outcome = "skipped", reason = "candidate did not pass generated reference comparison";
                if (index < generatedOutcomes.size() && generatedOutcomes.get(index).equals("passed")) {{
                    try {{
                        Object expected = invokeQuietly("Reference", {_java_string(method_name)}, test.args());
                        Object actual = invokeQuietly("AxiomaOptimized", {_java_string(method_name)}, test.args());
                        outcome = equal(actual, expected) ? "passed" : "failed";
                        reason = outcome.equals("passed") ? "" : "optimized output differs from user-supplied reference";
                    }} catch (Throwable error) {{
                        Throwable cause = error instanceof java.lang.reflect.InvocationTargetException && error.getCause() != null ? error.getCause() : error;
                        outcome = "failed";
                        reason = cause.getClass().getSimpleName() + ": " + String.valueOf(cause.getMessage());
                        if (reason.length() > 300) reason = reason.substring(0, 300);
                    }}
                }}
                optimizationResults.add(result("optimization/" + test.name(), outcome, reason));
            }}
            for (int index = generatedCases.size(); index < {requested_generated}; index++) {{
                optimizationResults.add(result("optimization/generated_" + (index + 1), "skipped", "no distinct valid input could be generated"));
            }}
            int expectedOptimizationChecks = cases.size() + (referenceCases.isEmpty() ? 0 : {requested_generated});
            optimizationValid &= optimizationResults.size() == expectedOptimizationChecks;
            for (String item : optimizationResults) optimizationValid &= item.contains("\\\"outcome\\\":\\\"passed\\\"");
            System.out.println("AXIOMA_OPTIMIZATION:{{\\\"checks\\\":[" + String.join(",", optimizationResults)
                + "],\\\"requested\\\":" + expectedOptimizationChecks
                + ",\\\"checked\\\":" + optimizationResults.size() + "}}");
        }}

        if (!benchmarkCases.isEmpty()) {{
            List<String> measurements = new ArrayList<>();
            List<String> optimizedMeasurements = new ArrayList<>();
            String skippedReason = allExecutionChecksPassed && allPropertyChecksPassed
                ? "none" : "configured checks did not all pass";
            String optimizedSkippedReason = "no optimization candidate was supplied";
            if (allExecutionChecksPassed && allPropertyChecksPassed) {{
                for (Benchmark benchmark : benchmarkCases) {{
                    long elapsed = medianElapsed({_java_string(class_name)}, {_java_string(method_name)}, benchmark.args());
                    Long heapPoolPeakIncrease = medianHeapPoolPeakIncrease({_java_string(class_name)}, {_java_string(method_name)}, benchmark.args());
                    measurements.add(benchmarkResult(benchmark.size(), elapsed, heapPoolPeakIncrease, null, null));
                    if (optimizationValid) {{
                        long optimizedElapsed = medianElapsed("AxiomaOptimized", {_java_string(method_name)}, benchmark.args());
                        Long optimizedHeapPoolPeakIncrease = medianHeapPoolPeakIncrease("AxiomaOptimized", {_java_string(method_name)}, benchmark.args());
                        optimizedMeasurements.add(benchmarkResult(benchmark.size(), elapsed, heapPoolPeakIncrease, optimizedElapsed, optimizedHeapPoolPeakIncrease));
                    }}
                }}
                skippedReason = "none";
                if (optimizationValid) optimizedSkippedReason = "none";
                else if ({str(optimization_enabled).lower()}) optimizedSkippedReason = "optimization equivalence checks did not all pass";
            }}
            System.out.println("AXIOMA_COMPLEXITY:{{\\\"measurements\\\":[" + String.join(",", measurements)
                + "],\\\"optimized_measurements\\\":[" + String.join(",", optimizedMeasurements)
                + "],\\\"measurement_method\\\":\\\"jvm_reflective_wall_time\\\",\\\"warmups\\\":5,\\\"trials\\\":9"
                + ",\\\"skipped_reason\\\":" + quote(skippedReason)
                + ",\\\"optimized_skipped_reason\\\":" + quote(optimizedSkippedReason) + "}}");
        }}
        System.out.println("AXIOMA_RESULT:[" + String.join(",", results) + "]");
    }}
}}
"""
