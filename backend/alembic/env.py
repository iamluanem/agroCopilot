from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import text

from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.base import Base, engine

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)


def run_migrations_online() -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
        context.configure(
            connection=conn,
            target_metadata=Base.metadata,
            include_object=alembic_helpers.include_object,
            process_revision_directives=alembic_helpers.writer,
            render_item=alembic_helpers.render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
