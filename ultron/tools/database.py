"""SQLite database tool for JARVIS pipeline."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from ultron.tools.base import Tool


class QueryDatabase(Tool):
    name = "query_database"
    description = (
        "Execute a SQL query on a SQLite database. "
        "Use this to read data, list tables, or explore database schema. "
        "Returns results as a list of dictionaries."
    )
    parameters = {
        "type": "object",
        "properties": {
            "database_path": {
                "type": "string",
                "description": "Path to the SQLite database file (.db or .sqlite).",
            },
            "query": {
                "type": "string",
                "description": "SQL query to execute (SELECT, PRAGMA, etc.).",
            },
            "params": {
                "type": "array",
                "description": "Optional query parameters for parameterized queries.",
                "items": {"type": "string"},
            },
        },
        "required": ["database_path", "query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "rows": {"type": "array"},
            "columns": {"type": "array"},
            "row_count": {"type": "integer"},
            "execution_time_ms": {"type": "number"},
        },
    }

    def run(
        self,
        database_path: str,
        query: str,
        params: Optional[List[str]] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        import time

        start = time.time()
        db = Path(database_path).expanduser()

        if not db.exists():
            return {"error": f"Database not found: {db}"}

        try:
            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = query.strip()
            is_select = query.upper().startswith(("SELECT", "PRAGMA", "EXPLAIN"))

            if is_select:
                if params:
                    cursor.execute(query, tuple(params))
                else:
                    cursor.execute(query)
                rows = [dict(row) for row in cursor.fetchall()]
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                result = {
                    "rows": rows,
                    "columns": columns,
                    "row_count": len(rows),
                    "execution_time_ms": round((time.time() - start) * 1000, 2),
                }
            else:
                if params:
                    cursor.execute(query, tuple(params))
                else:
                    cursor.execute(query)
                conn.commit()
                result = {
                    "rows": [],
                    "columns": [],
                    "row_count": cursor.rowcount,
                    "execution_time_ms": round((time.time() - start) * 1000, 2),
                    "affected_rows": cursor.rowcount,
                }

            conn.close()
            return result

        except sqlite3.Error as e:
            return {"error": f"SQLite error: {e}"}
        except Exception as e:
            return {"error": str(e)}


class ListTables(Tool):
    name = "list_tables"
    description = "List all tables in a SQLite database with their schema."
    parameters = {
        "type": "object",
        "properties": {
            "database_path": {
                "type": "string",
                "description": "Path to the SQLite database file.",
            },
        },
        "required": ["database_path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "tables": {"type": "array"},
        },
    }

    def run(self, database_path: str, **_: Any) -> Dict[str, Any]:
        db = Path(database_path).expanduser()

        if not db.exists():
            return {"error": f"Database not found: {db}"}

        try:
            conn = sqlite3.connect(str(db))
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]

            table_info = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                table_info[table] = [
                    {"name": col[1], "type": col[2], "nullable": not col[3], "default": col[4]}
                    for col in cursor.fetchall()
                ]

            conn.close()
            return {"tables": tables, "schema": table_info}

        except sqlite3.Error as e:
            return {"error": f"SQLite error: {e}"}
        except Exception as e:
            return {"error": str(e)}


class CreateTable(Tool):
    name = "create_table"
    description = "Create a new table in a SQLite database."
    parameters = {
        "type": "object",
        "properties": {
            "database_path": {
                "type": "string",
                "description": "Path to the SQLite database file.",
            },
            "table_name": {
                "type": "string",
                "description": "Name for the new table.",
            },
            "columns": {
                "type": "string",
                "description": "Column definitions (e.g., 'id INTEGER PRIMARY KEY, name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP').",
            },
        },
        "required": ["database_path", "table_name", "columns"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "table_name": {"type": "string"},
        },
    }
    mutates = True

    def run(
        self,
        database_path: str,
        table_name: str,
        columns: str,
        **_: Any,
    ) -> Dict[str, Any]:
        db = Path(database_path).expanduser()

        try:
            conn = sqlite3.connect(str(db))
            cursor = conn.cursor()

            create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})"
            cursor.execute(create_sql)
            conn.commit()
            conn.close()

            return {"success": True, "table_name": table_name}

        except sqlite3.Error as e:
            return {"error": f"SQLite error: {e}"}
        except Exception as e:
            return {"error": str(e)}


__all__ = [
    "QueryDatabase",
    "ListTables",
    "CreateTable",
]
