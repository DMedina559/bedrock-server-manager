"""Check API call signatures, including functions passed to run_task and partial."""

import ast
import importlib
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bedrock_server_manager.plugins.api_contract import get_contract  # noqa: E402
from bedrock_server_manager.plugins.api_types import API_METHODS  # noqa: E402


def contracts():
    result = {}
    for path in (ROOT / "src/bedrock_server_manager/api").glob("*.py"):
        if path.stem == "__init__":
            continue
        domain = path.stem
        module = importlib.import_module(f"bedrock_server_manager.api.{domain}")
        for name, operation in inspect.getmembers(module, inspect.isfunction):
            if "request" in inspect.signature(operation).parameters and get_contract(
                operation
            ):
                signature = inspect.signature(operation)
                qualified = f"{module.__name__}.{name}"
                result[qualified] = signature
                result["bridge:" + qualified] = signature.replace(
                    parameters=[
                        parameter
                        for parameter in signature.parameters.values()
                        if parameter.name not in {"app_context", "plugin_name"}
                    ]
                )
    return result


def check_source(source, package, signatures):
    tree = ast.parse(source)
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = {
                    item.name if item.asname else item.name.split(".")[0]
                }
        elif isinstance(node, ast.ImportFrom):
            module = (
                importlib.util.resolve_name(
                    "." * node.level + (node.module or ""), package
                )
                if node.level
                else node.module
            )
            for item in node.names:
                aliases[item.asname or item.name] = {f"{module}.{item.name}"}

    def resolve(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, {node.id})
        if isinstance(node, ast.Attribute):
            names = {f"{name}.{node.attr}" for name in resolve(node.value)}
            # Canonical plugin/core bridge methods have the same data contract.
            for name in tuple(names):
                parts = name.split(".")
                if (
                    len(parts) >= 3
                    and parts[-3] == "api"
                    and not name.startswith("bedrock_server_manager.api.")
                ):
                    domain, method = parts[-2:]
                    operation = API_METHODS.get(domain, {}).get(method)
                    if operation:
                        names.add(
                            f"bridge:bedrock_server_manager.api.{domain}.{operation}"
                        )
            return names
        return set()

    # Resolve statically selected deferred targets across conditional branches.
    for _ in range(3):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                names = resolve(node.value)
                for target in node.targets:
                    if isinstance(target, ast.Name) and names:
                        aliases.setdefault(target.id, set()).update(names)

    errors = []
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        names = resolve(node.func)
        deferred = any(
            name.endswith(".run_task") or name == "functools.partial" for name in names
        )
        args = node.args
        if deferred and args:
            names = resolve(args[0])
            args = args[1:]
        for name in names & signatures.keys():
            checked += 1
            if any(isinstance(arg, ast.Starred) for arg in args) or any(
                keyword.arg is None for keyword in node.keywords
            ):
                errors.append(
                    f"line {node.lineno}: {name}: cannot verify expanded arguments"
                )
                continue
            kwargs = {
                keyword.arg: None
                for keyword in node.keywords
                if not (deferred and keyword.arg == "username")
            }
            try:
                signatures[name].bind(*[None] * len(args), **kwargs)
            except TypeError as error:
                errors.append(f"line {node.lineno}: {name}: {error}")
    return checked, errors


def check_repository():
    signatures = contracts()
    checked = 0
    errors = []
    for root in (ROOT / "src", ROOT / "plugins"):
        for path in root.rglob("*.py"):
            package = (
                ".".join(path.relative_to(root).parent.parts)
                if root.name == "src"
                else ".".join(path.relative_to(ROOT).parent.parts)
            )
            count, failures = check_source(path.read_text(), package, signatures)
            checked += count
            errors.extend(f"{path.relative_to(ROOT)}:{failure}" for failure in failures)
    return checked, errors


if __name__ == "__main__":
    checked, errors = check_repository()
    if errors:
        sys.exit("\n".join(errors))
    print(f"Checked {checked} API calls, including deferred task targets.")
