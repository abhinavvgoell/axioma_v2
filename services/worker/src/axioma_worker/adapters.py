from dataclasses import dataclass
from typing import Protocol


class LanguageAdapter(Protocol):
    language: str
    image: str
    filename: str
    execute_script: str


@dataclass(frozen=True)
class PythonAdapter:
    language: str = "python"
    image: str = "python:3.13-slim"
    filename: str = "main.py"
    execute_script: str = (
        "umask 077; python -I -m py_compile /work/main.py > /tmp/stdout 2> /tmp/stderr; "
        "code=$?; if [ \"$code\" -ne 0 ]; then printf '%s' compile_error > /tmp/axioma-failure-kind; "
        "else python -I /work/main.py > /tmp/stdout 2> /tmp/stderr; code=$?; "
        "if [ \"$code\" -eq 0 ]; then printf '%s' none > /tmp/axioma-failure-kind; "
        "else printf '%s' runtime_error > /tmp/axioma-failure-kind; fi; fi; "
        "printf '%s' \"$code\" > /tmp/exit-code; exit 0"
    )


@dataclass(frozen=True)
class JavaAdapter:
    language: str = "java"
    image: str = "eclipse-temurin:21-jdk"
    filename: str = "Main.java"
    execute_script: str = (
        "umask 077; javac -d /work /work/Main.java > /tmp/stdout 2> /tmp/stderr; code=$?; "
        'if [ "$code" -ne 0 ]; then printf "%s" compile_error > /tmp/axioma-failure-kind; '
        'else java -cp /work Main >> /tmp/stdout 2>> /tmp/stderr; code=$?; '
        'if [ "$code" -eq 0 ]; then printf "%s" none > /tmp/axioma-failure-kind; '
        'else printf "%s" runtime_error > /tmp/axioma-failure-kind; fi; fi; '
        "printf '%s' \"$code\" > /tmp/exit-code; exit 0"
    )


ADAPTERS: dict[str, LanguageAdapter] = {
    "python": PythonAdapter(),
    "java": JavaAdapter(),
}


def get_adapter(language: str) -> LanguageAdapter:
    try:
        return ADAPTERS[language]
    except KeyError as exc:
        raise ValueError(f"Unsupported language: {language}") from exc
