def test_test_database_connection(test_engine):
    assert test_engine.url.database == "ai_document_generator_test"


def test_database_tables_created(test_engine):
    from sqlalchemy import inspect

    inspector = inspect(test_engine)
    tables = inspector.get_table_names()

    assert "users" in tables
    assert "repositories" in tables
    assert "generated_documents" in tables
    assert "ai_usage" in tables