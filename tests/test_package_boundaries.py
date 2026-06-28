import ast
from pathlib import Path


FORBIDDEN_PACKAGE_IMPORTS = ("app", "worker")
SOURCE_ROOTS = ("app", "packages", "tests", "worker")


def test_reusable_packages_do_not_import_app_business_layers():
    package_root = Path("packages")
    violations = []

    for path in package_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module_name = imported_module_name(node)
            if module_name and module_name.split(".", 1)[0] in FORBIDDEN_PACKAGE_IMPORTS:
                violations.append(f"{path}: {module_name}")

    assert violations == []


def test_source_does_not_import_removed_engine_namespace():
    violations = []

    for root_name in SOURCE_ROOTS:
        for path in Path(root_name).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                module_name = imported_module_name(node)
                if module_name and module_name.split(".", 1)[0] == "engine":
                    violations.append(f"{path}: {module_name}")

    assert violations == []


def imported_module_name(node):
    if isinstance(node, ast.ImportFrom):
        return node.module
    if isinstance(node, ast.Import) and node.names:
        return node.names[0].name
    return None
