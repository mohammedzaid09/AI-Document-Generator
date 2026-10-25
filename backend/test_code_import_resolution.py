from app.services.code_import_resolution_service import CodeImportResolutionService


def test_absolute_module_candidates():
    assert CodeImportResolutionService._module_candidates(
        "app.services.auth"
    ) == [
        "app/services/auth.py",
        "app/services/auth/__init__.py",
    ]


def test_relative_import_in_same_package():
    assert CodeImportResolutionService._relative_module(
        "app/services/routes.py", "auth", 1
    ) == "app.services.auth"


def test_relative_import_from_parent_package():
    assert CodeImportResolutionService._relative_module(
        "app/services/routes.py", "config", 2
    ) == "app.config"


def test_import_from_current_package():
    assert CodeImportResolutionService._relative_module(
        "app/services/routes.py", "", 1
    ) == "app.services"


def test_backend_source_root_detection():
    paths = [
        "backend/app/main.py",
        "backend/app/services/auth.py",
    ]
    assert CodeImportResolutionService._source_root_prefix(paths) == "backend/"


def test_repository_root_detection():
    paths = ["app/main.py", "app/services/auth.py"]
    assert CodeImportResolutionService._source_root_prefix(paths) == ""
