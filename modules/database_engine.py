"""Reliable DatabaseEngine wrapper around mysql-connector.

Features:
- Shared MySQL connection pooling for multi-user Streamlit sessions
- Safe cursor context manager with transient-connection fallback
- `query()` for SELECTs and `execute()` for DML with commit/rollback
- Uses Streamlit `st.error`/`st.info` if available, otherwise prints
"""
from contextlib import contextmanager
import hashlib
from threading import Lock
from typing import Any, Dict, Generator, Optional, Tuple

try:
    import streamlit as st
except Exception:
    st = None

import mysql.connector
from mysql.connector import pooling


def _log_error(msg: str) -> None:
    if st is not None:
        try:
            st.error(msg)
            return
        except Exception:
            pass
    print("ERROR:", msg)


def _log_info(msg: str) -> None:
    if st is not None:
        try:
            st.info(msg)
            return
        except Exception:
            pass
    print("INFO:", msg)


class DatabaseEngine:
    """Small helper around mysql.connector connections.

    Uses a shared pool across sessions for the same DB config, so each query
    borrows a connection and returns it immediately.
    """

    _pools: Dict[str, Any] = {}
    _pool_lock: Lock = Lock()

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        database: str,
        port: int = 3306,
        pool_size: int = 10,
    ) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = int(port)
        self.pool_size = max(int(pool_size), 1)
        # Legacy field kept for backward compatibility with previous code paths.
        self.connection: Optional[Any] = None

    def _pool_key(self) -> str:
        raw = f"{self.host}|{self.port}|{self.user}|{self.database}|{self.password}|{self.pool_size}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _pool_name(self) -> str:
        return f"testops_{self._pool_key()[:16]}"

    def _get_or_create_pool(self) -> Any:
        key = self._pool_key()
        existing = DatabaseEngine._pools.get(key)
        if existing is not None:
            return existing

        with DatabaseEngine._pool_lock:
            existing = DatabaseEngine._pools.get(key)
            if existing is not None:
                return existing

            pool = pooling.MySQLConnectionPool(
                pool_name=self._pool_name(),
                pool_size=self.pool_size,
                pool_reset_session=True,
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                autocommit=False,
            )
            DatabaseEngine._pools[key] = pool
            return pool

    def connect(self) -> None:
        """Initialize/validate pool by borrowing one connection."""
        try:
            pool = self._get_or_create_pool()
            conn = pool.get_connection()
            try:
                if not hasattr(conn, "cursor"):
                    raise RuntimeError("Invalid pooled DB connection object")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            _log_error(f"Database pool initialization error: {e}")
            raise

    def close(self) -> None:
        """Close legacy persistent connection if present."""
        if self.connection is not None:
            try:
                close = getattr(self.connection, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass
        self.connection = None

    @contextmanager
    def _cursor(self, dictionary: bool = False) -> Generator[Tuple[Any, bool], None, None]:
        """Yield (cursor, used_transient_connection)."""
        conn = None
        cursor = None
        used_transient = False

        try:
            pool = self._get_or_create_pool()
            conn = pool.get_connection()
        except Exception as pool_err:
            # Fallback preserves service if pool init/borrow fails unexpectedly.
            _log_info(f"Pool unavailable; using direct connection fallback: {pool_err}")
            try:
                conn = mysql.connector.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    autocommit=False,
                )
                used_transient = True
            except Exception as e:
                _log_error(f"Failed to obtain cursor (fallback connect): {e}")
                raise

        try:
            cursor = conn.cursor(dictionary=dictionary)
            yield cursor, used_transient
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    # For pooled connections this returns the connection to pool.
                    conn.close()
                except Exception:
                    pass

    def query(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> list:
        """Execute SELECT and return rows as list[dict]."""
        with self._cursor(dictionary=True) as (cursor, _):
            try:
                if params is not None:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                return cursor.fetchall()
            except Exception as e:
                _log_error(f"Query failed: {e}")
                raise

    def execute(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> int:
        """Execute DML, commit and return affected row count."""
        with self._cursor(dictionary=False) as (cursor, _):
            try:
                if params is not None:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)

                conn = getattr(cursor, "connection", None)
                commit = getattr(conn, "commit", None)
                if callable(commit):
                    commit()
                else:
                    raise RuntimeError("Connection object has no commit() method")
                return getattr(cursor, "rowcount", 0)
            except Exception as e:
                try:
                    conn = getattr(cursor, "connection", None)
                    rollback = getattr(conn, "rollback", None)
                    if callable(rollback):
                        rollback()
                except Exception:
                    pass
                _log_error(f"Execute failed: {e}")
                raise
