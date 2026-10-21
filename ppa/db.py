from pathlib import Path
from sqlite3 import Connection

from sqlalchemy import create_engine, event

from .model import Base

engine = create_engine(
    "sqlite:///database.db",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(connection: Connection, record: object):
    del record
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


Base.metadata.create_all(engine)

with engine.connect() as connection:
    has_existing_data = connection.exec_driver_sql(
        "SELECT 1 FROM sites UNION ALL SELECT 1 FROM part_master LIMIT 1"
    ).first()

if has_existing_data is None:
    seed_file = Path(__file__).resolve().parent.parent / "data" / "seed.sql"
    raw_connection = engine.raw_connection()
    try:
        raw_connection.driver_connection.executescript(seed_file.read_text())
    finally:
        raw_connection.close()
