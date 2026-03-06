"""Reliable DatabaseEngine wrapper around mysql-connector.

Features:
- Centralized connection management and validation
- Safe cursor context manager with transient-connection fallback
- `query()` for SELECTs and `execute()` for DML with commit/rollback
- Uses Streamlit `st.error`/`st.info` if available, otherwise prints
"""
from contextlib import contextmanager
from typing import Any, Generator, Optional, Tuple

try:
    import streamlit as st
except Exception:
    st = None

import mysql.connector


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

    Usage:
        db = DatabaseEngine(host, user, password, database)
        rows = db.query("SELECT ...", params)
        n = db.execute("INSERT ...", params)
        db.close()
    """

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection: Optional[Any] = None

    def connect(self) -> None:
        """Create a persistent connection and validate it."""
        try:
            if self.connection is not None:
                is_connected = getattr(self.connection, "is_connected", None)
                if callable(is_connected) and is_connected():
                    return
                if hasattr(self.connection, "cursor"):
                    return
        except Exception:
            # fall through to reconnect
            self.connection = None

        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                autocommit=False,
            )
        except Exception as e:
            _log_error(f"Database connection error: {e}")
            raise

        if not hasattr(self.connection, "cursor"):
            _log_error("Established DB connection has no cursor() method")
            raise RuntimeError("Invalid DB connection object")

    def close(self) -> None:
        """Close persistent connection if present."""
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
        """Yield (cursor, used_transient_connection).

        If `self.connection` is usable, yields a cursor from it and
        `used_transient_connection` is False. Otherwise opens a transient
        connection with the stored credentials and yields its cursor; in
        that case the transient connection is closed on exit and the flag
        is True.
        """
        # Try persistent connection first
        try:
            if self.connection is None:
                self.connect()
            conn = self.connection
            if conn is not None and callable(getattr(conn, "cursor", None)):
                cursor = conn.cursor(dictionary=dictionary)
                try:
                    yield cursor, False
                finally:
                    try:
                        cursor.close()
                    except Exception:
                        pass
                return
        except Exception:
            # If persistent connection fails, fall back to transient
            pass

        # Transient connection fallback
        transient = None
        try:
            transient = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
            )
            cursor = transient.cursor(dictionary=dictionary)
            try:
                yield cursor, True
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass
                try:
                    transient.close()
                except Exception:
                    pass
        except Exception as e:
            if transient is not None:
                try:
                    transient.close()
                except Exception:
                    pass
            _log_error(f"Failed to obtain cursor (transient fallback): {e}")
            raise

    def query(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> list:
        """Execute SELECT and return rows as list[dict]."""
        with self._cursor(dictionary=True) as (cursor, transient):
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
        with self._cursor(dictionary=False) as (cursor, transient):
            try:
                if params is not None:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                # Commit on the connection that produced the cursor
                conn = self.connection if not transient else getattr(cursor, "connection", None)
                if conn is None:
                    # try to get connection attribute from cursor
                    conn = getattr(cursor, "connection", None)
                commit = getattr(conn, "commit", None)
                if callable(commit):
                    commit()
                else:
                    raise RuntimeError("Connection object has no commit() method")
                return getattr(cursor, "rowcount", 0)
            except Exception as e:
                # Try rollback if possible
                try:
                    conn = self.connection if not transient else getattr(cursor, "connection", None)
                    rollback = getattr(conn, "rollback", None)
                    if callable(rollback):
                        rollback()
                except Exception:
                    pass
                _log_error(f"Execute failed: {e}")
                raise
