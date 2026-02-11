"""Architecture tests that enforce orchestrator module boundaries."""

import ast
import importlib.util
from dataclasses import dataclass
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


@dataclass(frozen=True)
class BoundaryRule:
    """Boundary rule for one source namespace."""

    source: str
    forbidden: tuple[str, ...]


RULES = (
    BoundaryRule(
        source="src.api",
        forbidden=("src.main", "src.pipeline"),
    ),
    BoundaryRule(
        source="src.services",
        forbidden=(
            "src.api",
            "src.main",
            "src.composition",
            "src.pipeline",
            "src.adapters",
            "src.config",
        ),
    ),
    BoundaryRule(
        source="src.ports",
        forbidden=(
            "src.api",
            "src.main",
            "src.composition",
            "src.adapters",
            "src.services",
            "src.pipeline",
        ),
    ),
    BoundaryRule(
        source="src.adapters",
        forbidden=("src.api", "src.main", "src.composition"),
    ),
)


def _matches(module: str, prefix: str) -> bool:
    """Return true if module is equal to prefix or nested under it."""
    return module == prefix or module.startswith(f"{prefix}.")


def _module_name(path: Path) -> str:
    """Convert source file path to import module path."""
    return "src." + ".".join(path.relative_to(SRC_ROOT).with_suffix("").parts)


def _extract_imports(path: Path, current_module: str) -> set[str]:
    """Extract imported module names from one Python file."""
    tree = ast.parse(path.read_text(), filename=str(path))
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        if node.level == 0:
            if node.module:
                imports.add(node.module)
            continue

        relative_name = "." * node.level + (node.module or "")
        try:
            resolved = importlib.util.resolve_name(relative_name, current_module)
        except ImportError:
            continue
        imports.add(resolved)

    return imports


def test_orchestrator_module_boundaries() -> None:
    """Ensure domain layers do not take forbidden dependencies."""
    violations: list[str] = []

    for path in SRC_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue

        module = _module_name(path)
        imports = _extract_imports(path, module)
        relative_path = path.relative_to(SRC_ROOT.parent)

        for rule in RULES:
            if not _matches(module, rule.source):
                continue

            for imported_module in sorted(imports):
                if not imported_module.startswith("src."):
                    continue
                for forbidden_prefix in rule.forbidden:
                    if _matches(imported_module, forbidden_prefix):
                        violations.append(
                            f"{relative_path}: {module} imports {imported_module} "
                            f"(forbidden for {rule.source})"
                        )
                        break

    assert not violations, "Architecture boundary violations:\n" + "\n".join(violations)
