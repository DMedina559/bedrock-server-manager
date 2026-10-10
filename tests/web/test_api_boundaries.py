"""HTTP operations sharing an API contract must delegate to that API."""

import ast
from pathlib import Path

import bedrock_server_manager

ROOT = Path(bedrock_server_manager.__file__).parent


def test_routers_delegate_operations_with_corresponding_apis():
    operations = {}
    for path in (ROOT / "api").glob("*.py"):
        for function in ast.parse(path.read_text()).body:
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(arg.arg == "request" for arg in function.args.args):
                continue
            target = f"{path.stem}.{function.name}"
            operations[function.name] = target
            for decorator in function.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and ast.unparse(decorator.func) == "api_method"
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                ):
                    operations[decorator.args[0].value] = target

    checked = 0
    for path in (ROOT / "web" / "routers").glob("*.py"):
        tree = ast.parse(path.read_text())
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "api" or node.module.endswith(".api"):
                    for item in node.names:
                        aliases[item.asname or item.name] = item.name
                elif node.module.startswith("api.") or ".api." in node.module:
                    module = node.module.rsplit(".", 1)[-1]
                    for item in node.names:
                        aliases[item.asname or item.name] = f"{module}.{item.name}"
        for function in tree.body:
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in function.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not ast.unparse(decorator.func).startswith("router."):
                    continue
                operation = next(
                    (
                        keyword.value.value
                        for keyword in decorator.keywords
                        if keyword.arg == "operation_id"
                        and isinstance(keyword.value, ast.Constant)
                    ),
                    None,
                )
                if operation not in operations:
                    continue
                target = operations[operation]
                references = set()
                for node in ast.walk(function):
                    if isinstance(node, ast.Name) and node.id in aliases:
                        references.add(aliases[node.id])
                    elif (
                        isinstance(node, ast.Attribute)
                        and isinstance(node.value, ast.Name)
                        and node.value.id in aliases
                    ):
                        references.add(f"{aliases[node.value.id]}.{node.attr}")
                assert target in references, (
                    f"{path.name}:{function.name} bypasses API {target} "
                    f"for operation {operation}"
                )
                checked += 1
    assert checked > 10, "The audit must cover the shared HTTP/API operations"
