"""Small PostgreSQL adapter for the application's fixed, parameterised SQL.

Only repository-owned queries pass through this adapter (not arbitrary SQL).
The application schema is private and is provisioned by app.setup_supabase.
"""
from contextlib import contextmanager
import atexit
from threading import Lock

_pools = {}
_pool_lock = Lock()


def close_pools():
    with _pool_lock:
        for pool in _pools.values():
            pool.close()
        _pools.clear()


atexit.register(close_pools)


def _get_pool(url):
    from psycopg_pool import ConnectionPool
    from psycopg.rows import dict_row
    with _pool_lock:
        if url not in _pools:
            _pools[url] = ConnectionPool(
                # Supabase's shared pooler can take several seconds to complete
                # TLS negotiation from this region. Open lazily, retain working
                # connections, and avoid an additional SELECT 1 for every lease.
                url, min_size=0, max_size=3, timeout=15, max_waiting=10,
                max_idle=600, max_lifetime=1800, open=True,
                kwargs=dict(connect_timeout=10, row_factory=dict_row,
                            prepare_threshold=None),
            )
        return _pools[url]


class PostgresConnection:
    def __init__(self, connection):
        self.raw = connection

    def execute(self, query, params=()):
        # Repository queries use SQLite qmark parameters and no literal '?'s.
        # Values are still bound by psycopg, never interpolated into SQL.
        query = query.replace('?', '%s')
        return self.raw.execute(query, tuple(int(v) if isinstance(v, bool) else v
                                             for v in params) if params else None)


@contextmanager
def connect(url):
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.conninfo import conninfo_to_dict

    options = conninfo_to_dict(url)
    # Local integration tests can use a loopback Postgres without TLS.
    if options.get('host') not in ('localhost', '127.0.0.1', '::1'):
        if options.get('sslmode') not in ('require', 'verify-ca', 'verify-full'):
            raise ValueError('Remote PostgreSQL requires sslmode=require or stronger.')
    # A small process-wide pool shares connections, not user identities or
    # open transactions. Transaction-local settings reset on commit/rollback.
    try:
        import psycopg_pool
    except ImportError:
        # Existing installations still work until dependencies are upgraded.
        lease = psycopg.connect(url, connect_timeout=10, row_factory=dict_row,
                                prepare_threshold=None)
    else:
        lease = _get_pool(url).connection()
    with lease as connection:
        connection.execute('SET LOCAL search_path TO fsd_app, pg_catalog')
        connection.execute("SET LOCAL statement_timeout = '30s'")
        yield PostgresConnection(connection)
