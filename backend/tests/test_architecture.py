"""Enforce the dependency rule: the domain layer imports only the standard library
and itself, never FastAPI, SQLAlchemy, LangChain or other app layers."""

import ast
import sys
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parents[1] / "app" / "domain"


def imported_modules(path: Path) -> set[str]:
    modules = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_domain_depends_only_on_stdlib_and_itself():
    files = list(DOMAIN_DIR.glob("*.py"))
    assert files
    violations = {
        f"{path.name}: {module}"
        for path in files
        for module in imported_modules(path)
        if module.split(".")[0] not in sys.stdlib_module_names
        and not module.startswith("app.domain")
    }
    assert not violations, f"domain imports outside its boundary: {sorted(violations)}"
