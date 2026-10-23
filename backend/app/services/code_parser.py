
import ast


class PythonCodeParser:
    """Extract structural information from Python source code."""

    @staticmethod
    def parse(source: str) -> dict:
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return {
                "success": False,
                "error": str(exc),
                "functions": [],
                "classes": [],
                "imports": [],
            }

        functions = []
        classes = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": node.end_lineno,
                    "is_async": isinstance(
                        node, ast.AsyncFunctionDef
                    ),
                    "parameters": [
                        arg.arg for arg in node.args.args
                    ],
                })

            elif isinstance(node, ast.ClassDef):
                classes.append({
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": node.end_lineno,
                    "bases": [
                        ast.unparse(base) for base in node.bases
                    ],
                })

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "module": alias.name,
                        "line": node.lineno,
                        "kind": "import",
                    })

            elif isinstance(node, ast.ImportFrom):
                imports.append({
                    "module": node.module or "",
                    "line": node.lineno,
                    "kind": "from_import",
                    "names": [
                        alias.name for alias in node.names
                    ],
                    "level": node.level,
                })

        return {
            "success": True,
            "functions": sorted(
                functions, key=lambda item: item["line"]
            ),
            "classes": sorted(
                classes, key=lambda item: item["line"]
            ),
            "imports": sorted(
                imports, key=lambda item: item["line"]
            ),
        }
