from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from hinaa_api.persistence.db import make_engine
from hinaa_api.persistence.orm import Base
from hinaa_api.persistence.memory_service import MemoryService


def test_file_database_independent_connections_and_concurrent_owner_auth(tmp_path):
    engine = make_engine(f"sqlite+pysqlite:///{tmp_path / 'owner.db'}")
    Base.metadata.create_all(engine)
    memory = MemoryService(sessionmaker(bind=engine, expire_on_commit=False))
    owner = memory.ensure_user("test-owner")
    barrier = Barrier(4)
    def authenticate(_):
        with engine.connect() as connection:
            barrier.wait(timeout=10)
            assert connection.scalar(text("select 1")) == 1
            connection_id = id(connection.connection.driver_connection)
        return connection_id, memory.ensure_user("test-owner").id
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(authenticate, range(4)))
        assert len({identity for identity, _ in results}) == 4
        assert {user_id for _, user_id in results} == {owner.id}
    finally:
        engine.dispose()


def test_in_memory_database_still_shares_connection():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    try:
        assert isinstance(engine.pool, StaticPool)
    finally:
        engine.dispose()
