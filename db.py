import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# Pool tworzony raz przy starcie aplikacji.
# minconn=2  – zawsze trzymaj 2 gotowe połączenia
# maxconn=20 – przy 4 workerach Gunicorna masz 5 połączeń na worker, bezpiecznie
_pool = pool.ThreadedConnectionPool(
    minconn=2,
    maxconn=20,
    host="localhost",
    database="system_biletowy",
    user="postgres",
    password="admin"
)


@contextmanager
def get_db():
    """
    Użycie:
        with get_db() as (conn, cur):
            cur.execute(...)
            conn.commit()

    Połączenie wraca do pula automatycznie nawet przy wyjątku.
    Kursor jest RealDictCursor – wyniki jako słowniki, tak jak było.
    """
    conn = _pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield conn, cur
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
