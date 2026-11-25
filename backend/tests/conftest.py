
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from app.core.config import DATABASE_URL
from app.models import Base
from app.models.user import User
from app.models.workspace import Workspace
from app.models.project import Project
from app.models.repository import Repository
from app.models.generated_document import GeneratedDocument


EXPECTED_TEST_DATABASE = "ai_document_generator_test"


@pytest.fixture(scope="session")
def test_engine():
    test_url = make_url(DATABASE_URL).set(
        database=EXPECTED_TEST_DATABASE
    )

    if test_url.database != EXPECTED_TEST_DATABASE:
        raise RuntimeError("Refusing to connect to an unexpected database.")

    engine = create_engine(test_url, pool_pre_ping=True)

    if engine.url.database != EXPECTED_TEST_DATABASE:
        engine.dispose()
        raise RuntimeError("Test database verification failed.")

    Base.metadata.create_all(bind=engine)

    yield engine

    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()

    TestSession = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
        join_transaction_mode="create_savepoint",
    )

    session = TestSession()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def test_user(db_session):
    user = User(
        email=f"test-{uuid4().hex}@example.com",
        password_hash="test-password-hash",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def test_workspace(db_session, test_user):
    workspace = Workspace(
        name="Test Workspace",
        owner_id=test_user.id,
    )
    db_session.add(workspace)
    db_session.flush()
    return workspace


@pytest.fixture
def test_project(db_session, test_workspace):
    project = Project(
        name="Test Project",
        description="Project for automated tests",
        workspace_id=test_workspace.id,
    )
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture
def test_repository(db_session, test_project):
    repository = Repository(
        github_repo_id=uuid4().int % (2**63),
        name="test-repository",
        full_name="test-user/test-repository",
        url="https://github.com/test-user/test-repository",
        default_branch="main",
        project_id=test_project.id,
    )
    db_session.add(repository)
    db_session.flush()
    return repository

@pytest.fixture
def test_generated_document(db_session, test_repository):
    document = GeneratedDocument(
        repository_id=test_repository.id,
        document_type="repository_overview",
        title="Test Repository Documentation",
        content="Initial test content",
        status="completed",
        model_name="test-model",
    )
    db_session.add(document)
    db_session.flush()
    return document