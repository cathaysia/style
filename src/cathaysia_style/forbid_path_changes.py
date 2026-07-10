"""Fail when changed paths match protected path rules."""

from __future__ import annotations

import ast
import fnmatch
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Sequence


class RuleConfigError(ValueError):
    """An invalid protected path rule."""


@dataclass(frozen=True)
class ProtectedPathRule:
    """A protected path pattern and its optional explanation."""

    path: str
    reason: str | None = None


@dataclass(frozen=True)
class ForbiddenChange:
    """A changed path that matches a protected path rule."""

    path: Path
    rule: ProtectedPathRule


def _path_parts(value: str | Path) -> tuple[str, ...]:
    """Return platform-independent path parts for pattern matching."""
    return PurePosixPath(str(value).replace("\\", "/")).parts


def matches_path_pattern(path: str | Path, pattern: str) -> bool:
    """Return whether path matches a root-relative path pattern."""
    path_segments = _path_parts(path)
    pattern_segments = _path_parts(pattern)

    @lru_cache(maxsize=None)
    def matches(pattern_index: int, path_index: int) -> bool:
        if pattern_index == len(pattern_segments):
            return path_index == len(path_segments)

        pattern_segment = pattern_segments[pattern_index]
        if pattern_segment == "**":
            return matches(pattern_index + 1, path_index) or (
                path_index < len(path_segments)
                and matches(pattern_index, path_index + 1)
            )

        return (
            path_index < len(path_segments)
            and fnmatch.fnmatchcase(path_segments[path_index], pattern_segment)
            and matches(pattern_index + 1, path_index + 1)
        )

    return matches(0, 0)


def _split_fields(source: str) -> list[str]:
    """Split rule fields without splitting quoted values."""
    fields = []
    start = 0
    quote: str | None = None
    escaped = False

    for index, character in enumerate(source):
        if escaped:
            escaped = False
            continue
        if quote is not None and character == "\\":
            escaped = True
            continue
        if character in ("'", '"'):
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            continue
        if character in (",", "\n") and quote is None:
            fields.append(source[start:index])
            start = index + 1

    if quote is not None:
        raise RuleConfigError("unterminated quoted value")
    fields.append(source[start:])
    return fields


def _split_key_value(field: str) -> tuple[str, str]:
    """Split one mapping field at its first unquoted ':' or '='."""
    quote: str | None = None
    escaped = False

    for index, character in enumerate(field):
        if escaped:
            escaped = False
            continue
        if quote is not None and character == "\\":
            escaped = True
            continue
        if character in ("'", '"'):
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            continue
        if character in (":", "=") and quote is None:
            return field[:index], field[index + 1 :]

    raise RuleConfigError(f"expected key/value field, got {field.strip()!r}")


def _parse_string(value: str, *, field: str) -> str:
    """Parse a quoted or unquoted string value."""
    value = value.strip()
    if not value:
        raise RuleConfigError(f"{field} must not be empty")
    if value[0] not in ("'", '"'):
        return value

    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError) as error:
        raise RuleConfigError(f"invalid quoted {field}") from error
    if not isinstance(parsed, str):
        raise RuleConfigError(f"{field} must be a string")
    return parsed


def parse_rule(value: str) -> ProtectedPathRule:
    """Parse one protected path rule."""
    source = value.strip()
    if source.startswith("{"):
        if not source.endswith("}"):
            raise RuleConfigError("inline rule is missing its closing brace")
        source = source[1:-1]

    values: dict[str, str] = {}
    for raw_field in _split_fields(source):
        if not raw_field.strip():
            continue
        key, raw_value = _split_key_value(raw_field)
        key = key.strip()
        if key not in ("path", "reason"):
            raise RuleConfigError(f"unknown field {key!r}")
        if key in values:
            raise RuleConfigError(f"duplicate field {key!r}")
        values[key] = _parse_string(raw_value, field=key)

    if "path" not in values:
        raise RuleConfigError("path is required")
    return ProtectedPathRule(values["path"], values.get("reason"))


def _looks_like_rule(value: str) -> bool:
    """Return whether an argument starts a protected path rule."""
    source = value.lstrip()
    if source.startswith("{"):
        return True
    return any(
        separator in source and source.split(separator, 1)[0].strip() == "path"
        for separator in (":", "=")
    )


def split_args(argv: Sequence[str]) -> tuple[list[ProtectedPathRule], list[Path]]:
    """Split leading rule arguments from the changed paths that follow."""
    rules = []
    for value in argv:
        if not _looks_like_rule(value):
            break
        rules.append(parse_rule(value))

    if not rules:
        raise RuleConfigError("at least one path rule is required")
    return rules, [Path(value) for value in argv[len(rules) :]]


def find_forbidden_changes(
    paths: Sequence[Path], rules: Sequence[ProtectedPathRule]
) -> list[ForbiddenChange]:
    """Return changed paths that match the first applicable rule."""
    violations = []
    for path in paths:
        rule = next(
            (rule for rule in rules if matches_path_pattern(path, rule.path)),
            None,
        )
        if rule is not None:
            violations.append(ForbiddenChange(path, rule))
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    """Reject changed paths that match protected path rules."""
    try:
        rules, paths = split_args(sys.argv[1:] if argv is None else argv)
    except RuleConfigError as error:
        print(f"Error: invalid protected path rule: {error}")
        return 2

    violations = find_forbidden_changes(paths, rules)
    if not violations:
        return 0

    print("Error: changes to protected paths are forbidden.")
    for violation in violations:
        print(f"  {violation.path} (protected path: {violation.rule.path})")
        if violation.rule.reason:
            print(f"    Reason: {violation.rule.reason}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
