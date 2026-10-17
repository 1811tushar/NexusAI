"""AI-TL-02, SEC-03: hostile queries against the AST guard, then the real read-only role."""
import psycopg
import pytest

from app.tools.sql_guard import validate_sql

OK = [
    "SELECT region_id, SUM(revenue) FROM sales GROUP BY region_id",
    "select r.name, sum(s.revenue) from sales s join regions r on r.id = s.region_id where s.sale_month >= '2026-01-01' group by 1",
    "WITH q AS (SELECT * FROM sales) SELECT count(*) FROM q",
    "SELECT date_trunc('quarter', sale_month) AS q, sum(units) FROM public.sales GROUP BY 1",
    "SELECT 1 /* ; DROP TABLE sales */ -- trailing",
    "SELECT stddev(revenue) FROM sales",
]
HOSTILE = {
    "drop": "DROP TABLE sales", "delete": "DELETE FROM sales", "update": "UPDATE sales SET units = 0", "insert": "INSERT INTO regions VALUES (9,'X')",
    "truncate": "TRUNCATE sales", "alter": "ALTER TABLE sales ADD COLUMN x int", "create": "CREATE TABLE t (a int)", "grant": "GRANT ALL ON sales TO PUBLIC",
    "multi": "SELECT 1; DELETE FROM sales", "multi_select": "SELECT * FROM sales; SELECT * FROM users",
    "users": "SELECT * FROM users", "users_sub": "SELECT * FROM sales WHERE id IN (SELECT id FROM users)",
    "users_join": "SELECT s.id FROM sales s JOIN users u ON u.id = s.id", "ai_schema": "SELECT * FROM ai.document_chunks",
    "pg_catalog": "SELECT * FROM pg_catalog.pg_user", "info_schema": "SELECT * FROM information_schema.tables", "pg_tables": "SELECT * FROM pg_tables",
    "pg_sleep": "SELECT pg_sleep(30)", "pg_sleep_from": "SELECT 1 FROM sales WHERE pg_sleep(5) IS NOT NULL", "read_file": "SELECT pg_read_file('/etc/passwd')",
    "ls_dir": "SELECT pg_ls_dir('/')", "lo_import": "SELECT lo_import('/etc/passwd')", "dblink": "SELECT dblink('host=x','select 1')",
    "set_config": "SELECT set_config('default_transaction_read_only','off',false)", "current_setting": "SELECT current_setting('server_version')",
    "version": "SELECT version()", "current_user": "SELECT current_user", "cte_delete": "WITH d AS (DELETE FROM sales RETURNING *) SELECT * FROM d",
    "cte_insert": "WITH i AS (INSERT INTO regions VALUES (9,'X') RETURNING *) SELECT * FROM i", "cte_users": "WITH u AS (SELECT * FROM users) SELECT * FROM u",
    "union": "SELECT id FROM regions UNION SELECT id FROM users", "intersect": "SELECT id FROM regions INTERSECT SELECT id FROM products",
    "into": "SELECT * INTO newt FROM sales", "for_update": "SELECT * FROM sales FOR UPDATE", "set": "SET default_transaction_read_only = off",
    "copy": "COPY sales TO '/tmp/x'", "begin": "BEGIN; DROP TABLE sales; COMMIT", "generate_series": "SELECT * FROM generate_series(1,100000000)",
    "dollar_param": "SELECT * FROM sales WHERE id = $1", "empty": "   ", "garbage": "SELEC FROM WHERE ((", "comment_only": "-- just a comment",
    "other_db": "SELECT * FROM otherdb.public.sales", "unnest": "SELECT * FROM unnest(ARRAY[1,2,3])", "values": "VALUES (1),(2)",
    "explain": "EXPLAIN ANALYZE DELETE FROM sales", "do": "DO $$ BEGIN DELETE FROM sales; END $$",
}


@pytest.mark.parametrize("sql", OK)
def test_valid_queries_pass_with_forced_limit(sql):
    r = validate_sql(sql, row_limit=200)
    assert r.ok, r.reason
    assert r.sql.upper().rstrip().endswith("LIMIT 200")


@pytest.mark.parametrize("name", sorted(HOSTILE))
def test_hostile_queries_are_rejected_with_a_reason(name):
    r = validate_sql(HOSTILE[name], row_limit=200)
    assert not r.ok and r.sql is None and r.reason and len(r.reason) < 300


def test_limit_is_clamped_never_raised():
    assert validate_sql("SELECT * FROM sales LIMIT 99999", row_limit=200).sql.endswith("LIMIT 200")
    assert validate_sql("SELECT * FROM sales LIMIT 5", row_limit=200).sql.endswith("LIMIT 5")
    assert validate_sql("SELECT * FROM sales FETCH FIRST 9999 ROWS ONLY", row_limit=200).sql.endswith("LIMIT 200")


def test_executed_sql_is_rerendered_without_comments():
    r = validate_sql("SELECT 1 /* x */ -- y", row_limit=10)
    assert "/*" not in r.sql and "--" not in r.sql


def test_too_long_query_rejected():
    assert not validate_sql("SELECT " + "1," * 3000 + "1", row_limit=10).ok


# ------------------------------------------------------------- the DB itself (defence in depth: even if the guard were bypassed)
def test_readonly_role_rejects_writes_and_private_tables(biz):
    with biz.ro.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM sales").fetchone()["n"] == 1008
        for bad in ("INSERT INTO regions VALUES (9,'X')", "DELETE FROM sales", "UPDATE sales SET units = 0", "TRUNCATE sales", "DROP TABLE sales"):
            with pytest.raises(psycopg.Error):
                c.execute(bad)
            c.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT * FROM users")
        c.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("SELECT * FROM ai.memories")
        c.rollback()


def test_run_sql_tool_end_to_end_and_error_reasons(biz):
    import threading

    from app.agents.testing import ScriptedLlm
    from app.tools.registry import ToolError
    from app.tools.sql_tool import SqlArgs, run_sql
    from tests.agents.harness import make_runtime, mkreq
    ctx = make_runtime(biz, ScriptedLlm({})).make_ctx(user_id=1, investigation_id=1, thread_id="t", options=mkreq().options, now="x",
                                                      emit=lambda e: None, cancel=threading.Event())
    ok = run_sql(ctx, SqlArgs(sql="SELECT r.name, SUM(s.revenue) AS revenue FROM sales s JOIN regions r ON r.id = s.region_id GROUP BY r.name ORDER BY 1"))
    assert ok.evidence[0].kind == "SQL" and ok.evidence[0].data["columns"] == ["name", "revenue"] and len(ok.evidence[0].data["rows"]) == 4
    assert "<untrusted_data" in ok.observation
    with pytest.raises(ToolError) as e1:
        run_sql(ctx, SqlArgs(sql="SELECT nonexistent FROM sales"))
    assert "nonexistent" in e1.value.reason and "does not exist" in e1.value.reason          # readable DB reason the agent can fix
    with pytest.raises(ToolError) as e2:
        run_sql(ctx, SqlArgs(sql="SELECT * FROM users"))
    assert "SQL guard" in e2.value.reason
    big = run_sql(ctx, SqlArgs(sql="SELECT * FROM sales"))
    assert big.evidence[0].data["truncated"] is True and len(big.evidence[0].data["rows"]) == 50      # preview cap (contract: <= 50 rows)


def test_statement_timeout_is_enforced_for_slow_queries(biz):
    # the guard forbids pg_sleep, so prove the DB-level timeout with a raw read-only connection
    with biz.ro.connection() as c:
        with pytest.raises(psycopg.errors.QueryCanceled):
            c.execute("SELECT count(*) FROM sales a, sales b, sales c, sales d").fetchall()
        c.rollback()
