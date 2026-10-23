"""Canonical source loading, validation, and Python lowering for Nexa."""

from __future__ import annotations

import ast as python_ast
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from .ast_utils import normalize_ast, walk_nodes
from .code_generator import CodeGenerator
from .harness_validator import HarnessMode, HarnessReport, HarnessValidator
from .nexa_parser import parse


class CompilationError(ValueError):
    """Source-aware error shared by all compilation entry points."""


@dataclass(frozen=True)
class Compilation:
    python_code: str
    ast: dict[str, Any]
    sources: tuple[str, ...]
    diagnostics: HarnessReport


class SourceLoader:
    def __init__(self) -> None:
        self.sources: list[str] = []
        self._visited: set[Path] = set()
        self._stack: list[Path] = []

    def resolve(self, include: str, parent: Path) -> Path:
        local = parent / include
        if local.is_file():
            return local.resolve()
        relative = include.removeprefix("stdlib/")
        # Distributions install the data package next to src; no checkout required.
        bundled = Path(str(files("stdlib"))) / relative
        if bundled.is_file():
            return bundled.resolve()
        raise CompilationError(f"{parent}: included file '{include}' not found")

    def load(self, source: str, path: Path | None = None) -> dict[str, Any]:
        if path is not None:
            path = path.resolve()
            if path in self._stack:
                cycle = " -> ".join(str(item) for item in [*self._stack, path])
                raise CompilationError(f"Include cycle: {cycle}")
            if path in self._visited:
                return {"type": "Program", "body": [], "configs": [], "includes": []}
            self._stack.append(path)
        name = str(path) if path else "<source>"
        try:
            program = normalize_ast(parse(source, include_spans=True))
            if not isinstance(program, dict):
                raise CompilationError(f"{name}: parser did not produce a program")
            self.sources.append(name)
            for node in walk_nodes(program):
                node["_source_path"] = name
            body: list[dict[str, Any]] = []
            configs: list[dict[str, Any]] = []
            for include in program.get("includes", []):
                if include["path"].endswith(".nxs"):
                    continue
                included = self.resolve(include["path"], path.parent if path else Path.cwd())
                module = self.load(included.read_text(encoding="utf-8"), included)
                body.extend(module["body"])
                configs.extend(module.get("configs", []))
                program.setdefault("annotations", []).extend(module.get("annotations", []))
            program["body"] = body + program.get("body", [])
            program["configs"] = configs + program.get("configs", [])
            if path is not None:
                self._visited.add(path)
            return program
        except CompilationError:
            raise
        except Exception as error:
            raise CompilationError(f"{name}: {error}") from error
        finally:
            if path is not None:
                self._stack.pop()


def load_program(source: str, source_path: str | Path | None = None) -> tuple[dict[str, Any], tuple[str, ...]]:
    loader = SourceLoader()
    program = loader.load(source, Path(source_path) if source_path is not None else None)
    return program, tuple(loader.sources)


def compile_source(source: str, *, source_path: str | Path | None = None, harness_mode: str = "warn") -> Compilation:
    program, sources = load_program(source, source_path)
    diagnostics = HarnessValidator(HarnessMode(harness_mode)).validate(program)
    if diagnostics.has_errors():
        details = "; ".join(f"{item.location or source_path or '<source>'}: {item.rule_id}: {item.message}" for item in diagnostics.errors)
        raise CompilationError(f"{source_path or '<source>'}: {details}")
    generator = CodeGenerator(program)
    if source_path is not None:
        generator.source_path = str(Path(source_path).resolve())
    try:
        code = generator.generate()
        python_ast.parse(code, filename=f"{source_path or '<source>'} (generated)")
    except Exception as error:
        raise CompilationError(f"{source_path or '<source>'}: Python lowering failed: {error}") from error
    return Compilation(code, program, sources, diagnostics)


def compile_file(path: str | Path, *, harness_mode: str = "warn") -> Compilation:
    source_path = Path(path).resolve()
    return compile_source(source_path.read_text(encoding="utf-8"), source_path=source_path, harness_mode=harness_mode)
