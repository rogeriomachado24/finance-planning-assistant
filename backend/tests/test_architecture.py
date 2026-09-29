"""Enforce the dependency rules between layers (docs/PHASE1_DESIGN.md, section 5)."""

import ast
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def imported_modules(path: Path) -> set[str]:
    modules = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def imports_by_file(package: str) -> dict[str, set[str]]:
    files = list((APP_DIR / package).glob("*.py"))
    assert files, f"no modules found in app/{package}"
    return {path.name: imported_modules(path) for path in files}


def test_domain_depends_only_on_stdlib_and_itself():
    violations = {
        f"{name}: {module}"
        for name, modules in imports_by_file("domain").items()
        for module in modules
        if module.split(".")[0] not in sys.stdlib_module_names
        and not module.startswith("app.domain")
    }
    assert not violations, f"domain imports outside its boundary: {sorted(violations)}"


FORBIDDEN_IN_SERVICES = ("fastapi", "starlette", "langchain", "langgraph", "app.api", "app.agents")


def test_services_know_nothing_about_http_or_llms():
    """Services are shared by the REST API and the chat agent, so they depend on neither."""
    violations = {
        f"{name}: {module}"
        for name, modules in imports_by_file("services").items()
        for module in modules
        if module.startswith(FORBIDDEN_IN_SERVICES)
    }
    assert not violations, f"services import from an outer layer: {sorted(violations)}"


def test_services_do_not_depend_on_the_chat_layer():
    violations = {
        f"{name}: {module}"
        for name, modules in imports_by_file("services").items()
        for module in modules
        if module.startswith(("app.agents", "app.tools"))
    }
    assert not violations, f"services import the chat layer: {sorted(violations)}"


def test_chat_layer_does_not_depend_on_http():
    """The graph and its tools are driven by the API, never the other way round."""
    violations = {
        f"{package}/{name}: {module}"
        for package in ("agents", "tools")
        for name, modules in imports_by_file(package).items()
        for module in modules
        if module.startswith(("app.api", "fastapi", "starlette"))
    }
    assert not violations, f"chat layer imports the HTTP layer: {sorted(violations)}"
