"""Compare an existing schema with a transactional copy of the historical DDL."""

from __future__ import annotations

import re
from typing import Any


async def structure(conn: Any, schema: str) -> dict[str, Any]:
    """Read columns, validated constraints and ready index definitions."""
    columns = await conn.fetch(
        """SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod) typ,
        a.attnotnull,a.attidentity FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=$1 AND c.relkind='r'
        AND a.attnum>0 AND NOT a.attisdropped""",
        schema,
    )
    constraints = await conn.fetch(
        """SELECT c.relname,pg_get_constraintdef(p.oid) definition
        FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=$1 AND p.convalidated""",
        schema,
    )
    indexes = await conn.fetch(
        """SELECT t.relname,pg_get_indexdef(i.indexrelid) definition
        FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname=$1 AND i.indisvalid AND i.indisready""",
        schema,
    )

    def norm(value: Any) -> Any:
        return value.replace(schema + ".", "").replace("public.", "")

    return {
        "columns": {(r["relname"], r["attname"]): (norm(r["typ"]), r["attnotnull"], r["attidentity"]) for r in columns},
        "constraints": {(r["relname"], norm(r["definition"])) for r in constraints},
        "indexes": {(r["relname"], norm(re.sub(r"INDEX \S+ ON ", "INDEX ON ", r["definition"]))) for r in indexes},
    }


async def validate_original(conn: Any, sql: str) -> None:
    """Reject missing or changed structure without touching user tables."""
    version = await conn.fetchval("SELECT extversion FROM pg_extension WHERE extname='vector'")
    if not version or tuple(map(int, version.split(".")[:2])) < (0, 8):
        raise RuntimeError("Требуется установленное расширение pgvector >= 0.8")
    if int(await conn.fetchval("SHOW server_version_num")) < 160000:
        raise RuntimeError("Требуется PostgreSQL >= 16")
    actual = await structure(conn, "public")
    await conn.execute("CREATE SCHEMA cleanup_schema_check")
    try:
        await conn.execute("SET LOCAL search_path TO cleanup_schema_check, public")
        await conn.execute(sql.replace("CREATE EXTENSION IF NOT EXISTS vector;", ""))
        expected = await structure(conn, "cleanup_schema_check")
        for key, value in expected["columns"].items():
            if actual["columns"].get(key) != value:
                raise RuntimeError(f"Несовместимый столбец {key[0]}.{key[1]}: ожидается {value}")
        for section in ("constraints", "indexes"):
            missing = expected[section] - actual[section]
            if missing:
                raise RuntimeError(f"Несовместимая схема: {section}: {sorted(missing)[:3]}")
    finally:
        await conn.execute("SET LOCAL search_path TO public")
        await conn.execute("DROP SCHEMA cleanup_schema_check CASCADE")
