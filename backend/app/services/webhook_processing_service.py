from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.webhook_event import WebhookEvent
from app.repositories.webhook_event_repository import WebhookEventRepository
from app.services.source_code_service import SourceCodeService
from app.services.github_service import GitHubService
from app.services.code_scanner import CodeScanner
from app.services.code_parser import PythonCodeParser
from app.services.code_persistence_service import CodePersistenceService
from app.services.code_import_resolution_service import CodeImportResolutionService

class WebhookProcessingService:
    """Process GitHub webhook events and synchronize repository analysis."""

    def __init__(self, db: Session):
        self.db = db
        self.event_repository = WebhookEventRepository(db)

    def get_pending_events(self, limit: int = 20) -> list[WebhookEvent]:
        """Retrieve webhook events waiting to be processed."""

        if limit < 1:
            raise ValueError("Limit must be greater than zero.")

        return self.event_repository.get_pending(limit=limit)

    def validate_repository(self, event: WebhookEvent) -> Repository:
        """Verify that the repository associated with an event exists."""

        repository = self.db.get(Repository, event.repository_id)

        if repository is None:
            raise ValueError(
                f"Repository {event.repository_id} not found."
            )

        return repository

    
    def validate_default_branch(self, event: WebhookEvent, repository: Repository) -> None:
        """Process only events targeting the repository's default branch."""

        if not event.branch:
            raise ValueError("Webhook event does not contain a branch.")

        if event.branch != repository.default_branch:
            raise ValueError(
                f"Ignoring branch '{event.branch}'. "
                f"Only the default branch '{repository.default_branch}' "
                "is processed."
            )

    def get_github_context(self, repository: Repository):
        """Create an authenticated GitHub service for the repository owner."""

        source_service = SourceCodeService(self.db)

        owner_id = source_service.get_repository_owner(repository.id)

        if owner_id is None:
            raise ValueError("Unable to identify the repository owner.")

        github = GitHubService(self.db, owner_id)

        owner, repo_name = repository.full_name.split("/", 1)

        return github, owner, repo_name


    
    def get_changed_python_files(self, event: WebhookEvent) -> dict:
        """Identify supported, non-sensitive Python files in a webhook event."""

        changed_files = event.changed_files

        if not isinstance(changed_files, dict):
            raise ValueError("Invalid changed files data in webhook event.")

        added = changed_files.get("added", [])
        modified = changed_files.get("modified", [])
        removed = changed_files.get("removed", [])

        if not all(
            isinstance(paths, list)
            and all(isinstance(path, str) and path.strip() for path in paths)
            for paths in (added, modified, removed)
        ):
            raise ValueError("Invalid changed files data in webhook event.")

        def filter_python_files(paths):
            return sorted({
                path
                for path in paths
                if path.lower().endswith(".py")
                and CodeScanner.is_supported_file(path)
                and not SourceCodeService.is_sensitive_file(path)
            })

        return {
            "added": filter_python_files(added),
            "modified": filter_python_files(modified),
            "removed": filter_python_files(removed),
        }

    
    def analyze_changed_files(
        self,
        event: WebhookEvent,
        repository: Repository,
        github,
        owner: str,
        repo_name: str,
    ) -> dict:
        """Fetch, analyze, and persist added or modified Python files."""

        changed = self.get_changed_python_files(event)
        paths = changed["added"] + changed["modified"]

        if not paths:
            return {
                "files_analyzed": 0,
                "files_failed": 0,
                "failures": [],
            }

        analyzed_files = []
        failures = []

        parser = PythonCodeParser()

        ref = event.after_commit or repository.default_branch

        for path in paths:
            try:
                file_data = github.get_file_content(
                    owner,
                    repo_name,
                    path,
                    ref=ref,
                )

                parsed = parser.parse(file_data["content"])

                analyzed_files.append({
                    "path": file_data["path"],
                    "sha": file_data["sha"],
                    "size": file_data["size"],
                    "success": parsed["success"],
                    "error": parsed.get("error"),
                    "functions": parsed.get("functions", []),
                    "classes": parsed.get("classes", []),
                    "imports": parsed.get("imports", []),
                })

            except (ValueError, RuntimeError, KeyError) as error:
                failures.append({
                    "path": path,
                    "error": str(error),
                })

        if analyzed_files:
            persistence = CodePersistenceService(self.db)

            result = persistence.save_analysis(
                repository.id,
                {"files": analyzed_files},
            )

            CodeImportResolutionService(self.db).resolve_repository(
                repository.id
            )

            return {
                "files_analyzed": result.get("files_saved", 0),
                "files_failed": result.get("files_failed", 0) + len(failures),
                "failures": failures,
            }

        return {
            "files_analyzed": 0,
            "files_failed": len(failures),
            "failures": failures,
        }

    
    def delete_removed_files(
        self,
        event: WebhookEvent,
        repository: Repository,
    ) -> int:
        """Remove deleted Python files from the repository analysis."""

        changed = self.get_changed_python_files(event)
        removed_paths = changed["removed"]

        if not removed_paths:
            return 0

        persistence = CodePersistenceService(self.db)

        return persistence.delete_files(
            repository.id,
            removed_paths,
        )

    
    def process_event(self, event: WebhookEvent) -> dict:
        """Process one pending GitHub push event."""

        try:
            self.event_repository.update_status(event, "processing")

            repository = self.validate_repository(event)

            if not event.branch:
                raise ValueError("Webhook event does not contain a branch.")

            # Skip pushes to branches other than the default branch.
            if event.branch != repository.default_branch:
                reason = (
                    f"Skipped branch '{event.branch}'. "
                    f"Only '{repository.default_branch}' is processed."
                )

                self.event_repository.update_status(
                    event,
                    "processed",
                    error_message=reason,
                )

                return {
                    "event_id": event.id,
                    "status": "skipped",
                    "reason": reason,
                }

            github, owner, repo_name = self.get_github_context(repository)

            analysis_result = self.analyze_changed_files(
                event,
                repository,
                github,
                owner,
                repo_name,
            )

            deleted_count = self.delete_removed_files(
                event,
                repository,
            )

            self.event_repository.update_status(event, "processed")

            return {
                "event_id": event.id,
                "status": "processed",
                "files_analyzed": analysis_result["files_analyzed"],
                "files_failed": analysis_result["files_failed"],
                "files_deleted": deleted_count,
                "failures": analysis_result["failures"],
                "documentation_may_be_outdated": True,
            }

        except Exception as error:
            self.db.rollback()

            self.event_repository.update_status(
                event,
                "failed",
                error_message=str(error),
            )

            return {
                "event_id": event.id,
                "status": "failed",
                "error": str(error),
            } 
    
    def process_pending_events(
        self,
        owner_id: int,
        limit: int = 20,
    ) -> dict:
        """Process pending webhook events belonging to one workspace owner."""

        if limit < 1:
            raise ValueError("Limit must be greater than zero.")

        events = self.event_repository.get_pending_for_owner(
            owner_id=owner_id,
            limit=limit,
        )

        results = []

        for event in events:
            result = self.process_event(event)
            results.append(result)

        return {
            "total": len(results),
            "processed": sum(
                result["status"] == "processed" for result in results
            ),
            "skipped": sum(
                result["status"] == "skipped" for result in results
            ),
            "failed": sum(
                result["status"] == "failed" for result in results
            ),
            "results": results,
        }