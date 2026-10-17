"""AI-FD-05 / SEC-03: the read-only pool really cannot write, and cannot see anything it was not granted."""
import psycopg
import pytest


def test_ro_pool_can_select_granted_table(pools):
    with pools[1].connection() as c:
        assert [r["name"] for r in c.execute("SELECT name FROM regions ORDER BY id")] == ["North", "South"]


def test_ro_pool_rejects_writes(pools):
    with pools[1].connection() as c, pytest.raises(psycopg.errors.Error) as e:
        c.execute("INSERT INTO regions VALUES (9, 'Hack')")
    assert isinstance(e.value, (psycopg.errors.ReadOnlySqlTransaction, psycopg.errors.InsufficientPrivilege))


def test_session_is_read_only_by_default(pools):
    with pools[1].connection() as c:
        assert c.execute("SHOW default_transaction_read_only").fetchone()["default_transaction_read_only"] == "on"
        assert c.execute("SHOW statement_timeout").fetchone()["statement_timeout"] == "5s"


def test_turning_read_only_off_still_cannot_write(pools):
    """Defence in depth: even if an attacker flips the session flag, the ROLE has no INSERT/UPDATE/DELETE privilege."""
    with pools[1].connection() as c:
        c.execute("SET default_transaction_read_only = off")
        c.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE")
        c.commit()   # the flag only affects NEW transactions; the next statement starts a read-write one
        for stmt in ("INSERT INTO regions VALUES (9,'Hack')", "UPDATE regions SET name='x'", "DELETE FROM regions",
                     "DROP TABLE regions", "CREATE TABLE public.evil (a int)"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(stmt)
            c.rollback()


def test_ro_role_cannot_read_private_or_ai_tables(pools):
    with pools[1].connection() as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT * FROM users")
        c.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT * FROM ai.document_chunks")


def test_statement_timeout_enforced(pools):
    with pools[1].connection() as c, pytest.raises(psycopg.errors.QueryCanceled):
        c.execute("SET statement_timeout = 200")
        c.execute("SELECT pg_sleep(2)")


def test_rw_pool_works_in_schema_ai_and_cannot_touch_public_users(pools):
    rw = pools[0]
    with rw.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM ai.document_chunks").fetchone()["n"] >= 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT * FROM users")
