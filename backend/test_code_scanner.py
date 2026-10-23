from app.services.code_scanner import CodeScanner


def test_code_scanner_filters_supported_source_files():
    sample_tree = [
        {"path": "app/main.py", "type": "blob"},
        {"path": "app/services/auth.py", "type": "blob"},
        {"path": "frontend/src/App.jsx", "type": "blob"},
        {"path": "frontend/src/api.ts", "type": "blob"},
        {"path": "node_modules/example/index.js", "type": "blob"},
        {"path": "README.md", "type": "blob"},
        {"path": "app", "type": "tree"},
        {"path": "frontend", "type": "tree"},
    ]

    result = CodeScanner.scan_tree(sample_tree)

    assert result["total_source_files"] == 4
    assert len(result["source_files"]) == 4
    assert "node_modules/example/index.js" not in result["source_files"]
    assert "README.md" not in result["source_files"]
