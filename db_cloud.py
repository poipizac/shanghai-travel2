# -*- coding: utf-8 -*-
"""
上海 4 天 3 夜旅遊記帳與行程管理系統 - 雙軌資料庫適配層 (Dual-Mode DB Adapter)
支援：
  1. 雲端優先 (Cloud Mode): Supabase / PostgreSQL 外部資料庫 (透過 st.secrets 或環境變數)
  2. 本地回退 (Local Fallback): SQLite (travel.db)
"""

import os
import sqlite3
from typing import List, Dict, Any, Optional
import streamlit as st
from itinerary_data import DEFAULT_ITINERARY

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "travel.db")

# 預設核心三人組
DEFAULT_MEMBERS = ["本人", "Chris", "Angus"]

def get_cloud_db_url() -> Optional[str]:
    """獲取雲端 PostgreSQL / Supabase 連線字串"""
    # 1. 優先從 st.secrets 檢查
    try:
        if hasattr(st, "secrets"):
            if "connections" in st.secrets and "postgresql" in st.secrets["connections"]:
                return st.secrets["connections"]["postgresql"].get("url")
            if "supabase" in st.secrets and "db_url" in st.secrets["supabase"]:
                return st.secrets["supabase"].get("db_url")
            if "DATABASE_URL" in st.secrets:
                return st.secrets["DATABASE_URL"]
    except Exception:
        pass
        
    # 2. 次之從環境變數檢查
    return os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")

def is_cloud_mode() -> bool:
    """是否處於雲端資料庫模式"""
    return bool(get_cloud_db_url())

_engine = None

def get_engine():
    """獲取 SQLAlchemy Engine (僅在雲端模式下)"""
    global _engine
    if not is_cloud_mode():
        return None
    if _engine is None:
        from sqlalchemy import create_engine
        url = get_cloud_db_url()
        # SQLAlchemy 需將 postgres:// 轉換為 postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        _engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    return _engine

class DBConnectionWrapper:
    """輕量統一的資料庫查詢與事務封裝器"""
    
    @staticmethod
    def execute_query(sql_sqlite: str, sql_pg: Optional[str] = None, params: tuple = ()) -> List[Dict[str, Any]]:
        """執行查詢並回傳字典列表"""
        if is_cloud_mode():
            from sqlalchemy import text
            engine = get_engine()
            query_sql = sql_pg or sql_sqlite.replace("?", ":param")
            # 轉換參數格式
            with engine.connect() as conn:
                if isinstance(params, (list, tuple)) and len(params) > 0:
                    # 將 ? 依序替換為 :p0, :p1, ...
                    named_sql = sql_pg if sql_pg else sql_sqlite
                    param_dict = {}
                    parts = named_sql.split("?")
                    if len(parts) - 1 == len(params):
                        rebuilt = []
                        for i, part in enumerate(parts[:-1]):
                            pname = f"p{i}"
                            rebuilt.append(part + f":{pname}")
                            param_dict[pname] = params[i]
                        rebuilt.append(parts[-1])
                        named_sql = "".join(rebuilt)
                    result = conn.execute(text(named_sql), param_dict)
                else:
                    result = conn.execute(text(query_sql))
                return [dict(row._mapping) for row in result]
        else:
            conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(sql_sqlite, params)
            rows = [dict(row) for row in cur.fetchall()]
            conn.close()
            return rows

    @staticmethod
    def execute_commit(sql_sqlite: str, sql_pg: Optional[str] = None, params: tuple = ()):
        """執行寫入/修改/刪除並提交"""
        if is_cloud_mode():
            from sqlalchemy import text
            engine = get_engine()
            with engine.begin() as conn:
                named_sql = sql_pg if sql_pg else sql_sqlite
                param_dict = {}
                parts = named_sql.split("?")
                if len(parts) - 1 == len(params):
                    rebuilt = []
                    for i, part in enumerate(parts[:-1]):
                        pname = f"p{i}"
                        rebuilt.append(part + f":{pname}")
                        param_dict[pname] = params[i]
                    rebuilt.append(parts[-1])
                    named_sql = "".join(rebuilt)
                conn.execute(text(named_sql), param_dict if param_dict else params)
        else:
            conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
            cur = conn.cursor()
            cur.execute(sql_sqlite, params)
            conn.commit()
            conn.close()

# -------------------------------------------------------------
# 核心業務資料庫操作介面
# -------------------------------------------------------------

def init_all_tables():
    """初始化所有資料表與預設三人組名單（本人、Chris、Angus）"""
    if is_cloud_mode():
        # 雲端模式下透過 SQLAlchemy 檢查與確保基礎設定
        try:
            for member in DEFAULT_MEMBERS:
                DBConnectionWrapper.execute_commit(
                    "INSERT OR IGNORE INTO members (name) VALUES (?)",
                    "INSERT INTO members (name) VALUES (?) ON CONFLICT (name) DO NOTHING",
                    (member,)
                )
                DBConnectionWrapper.execute_commit(
                    "INSERT OR IGNORE INTO users (name) VALUES (?)",
                    "INSERT INTO users (name) VALUES (?) ON CONFLICT (name) DO NOTHING",
                    (member,)
                )
        except Exception as e:
            st.warning(f"雲端資料庫初始化警告: {e}")
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        
        # 建立系統設定表
        cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('total_budget', '20100')")
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('itinerary_version', 'v2')")

        # 建立成員表
        cur.execute("CREATE TABLE IF NOT EXISTS members (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS users (name TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

        # 寫入預設核心三人組
        for member in DEFAULT_MEMBERS:
            cur.execute("INSERT OR IGNORE INTO members (name) VALUES (?)", (member,))
            cur.execute("INSERT OR IGNORE INTO users (name) VALUES (?)", (member,))

        # 行程表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS itinerary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day INTEGER NOT NULL,
            time_slot TEXT NOT NULL,
            title TEXT NOT NULL,
            tag TEXT,
            desc TEXT,
            transit TEXT,
            tip TEXT,
            sort_order INTEGER DEFAULT 0
        )
        """)

        # 支出表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day INTEGER DEFAULT 0,
            category TEXT NOT NULL,
            item_name TEXT NOT NULL,
            amount_twd REAL NOT NULL,
            amount_rmb REAL NOT NULL,
            payment_method TEXT DEFAULT '微信支付',
            expense_date TEXT,
            notes TEXT,
            user_name TEXT DEFAULT '本人',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 檢查欄位相容性
        cur.execute("PRAGMA table_info(expenses)")
        existing_cols = [row[1] for row in cur.fetchall()]
        if "user_name" not in existing_cols:
            cur.execute("ALTER TABLE expenses ADD COLUMN user_name TEXT DEFAULT '本人'")

        # 準備清單
        cur.execute("""
        CREATE TABLE IF NOT EXISTS checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            is_checked INTEGER DEFAULT 0,
            category TEXT DEFAULT '重要證件與App'
        )
        """)

        # 預算表
        cur.execute("""
        CREATE TABLE IF NOT EXISTS budget_limits (
            category TEXT PRIMARY KEY,
            budget_twd REAL NOT NULL,
            budget_rmb REAL NOT NULL
        )
        """)

        conn.commit()
        conn.close()

def get_setting(key: str, default: str = "") -> str:
    rows = DBConnectionWrapper.execute_query(
        "SELECT value FROM settings WHERE key = ?",
        "SELECT value FROM settings WHERE key = ?",
        (key,)
    )
    return rows[0]["value"] if rows else default

def set_setting(key: str, value: str):
    if is_cloud_mode():
        DBConnectionWrapper.execute_commit(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (key, value)
        )
    else:
        DBConnectionWrapper.execute_commit(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            params=(key, value)
        )

def get_all_members() -> List[str]:
    rows = DBConnectionWrapper.execute_query(
        "SELECT name FROM members ORDER BY id ASC",
        "SELECT name FROM members ORDER BY id ASC"
    )
    names = [r["name"] for r in rows]
    # 保證預設三人組都在名單中
    for m in DEFAULT_MEMBERS:
        if m not in names:
            names.append(m)
    return names

def add_new_member(name: str) -> bool:
    try:
        if is_cloud_mode():
            DBConnectionWrapper.execute_commit(
                "INSERT OR IGNORE INTO members (name) VALUES (?)",
                "INSERT INTO members (name) VALUES (?) ON CONFLICT (name) DO NOTHING",
                (name,)
            )
            DBConnectionWrapper.execute_commit(
                "INSERT OR IGNORE INTO users (name) VALUES (?)",
                "INSERT INTO users (name) VALUES (?) ON CONFLICT (name) DO NOTHING",
                (name,)
            )
        else:
            DBConnectionWrapper.execute_commit("INSERT OR IGNORE INTO members (name) VALUES (?)", params=(name,))
            DBConnectionWrapper.execute_commit("INSERT OR IGNORE INTO users (name) VALUES (?)", params=(name,))
        return True
    except Exception:
        return False

def get_expenses_by_user(user_name: str) -> List[Dict[str, Any]]:
    return DBConnectionWrapper.execute_query(
        "SELECT * FROM expenses WHERE user_name = ? ORDER BY day ASC, id ASC",
        "SELECT * FROM expenses WHERE user_name = ? ORDER BY day ASC, id ASC",
        (user_name,)
    )

def add_expense_record(day: int, category: str, item_name: str, amount_twd: float, amount_rmb: float, payment_method: str, expense_date: str, notes: str, user_name: str):
    DBConnectionWrapper.execute_commit(
        """
        INSERT INTO expenses (day, category, item_name, amount_twd, amount_rmb, payment_method, expense_date, notes, user_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        params=(day, category, item_name, amount_twd, amount_rmb, payment_method, expense_date, notes, user_name)
    )

def update_expense_record(exp_id: int, day: int, category: str, item_name: str, amount_twd: float, amount_rmb: float, payment_method: str, expense_date: str, notes: str):
    DBConnectionWrapper.execute_commit(
        """
        UPDATE expenses SET day = ?, category = ?, item_name = ?, amount_twd = ?, amount_rmb = ?, payment_method = ?, expense_date = ?, notes = ?
        WHERE id = ?
        """,
        params=(day, category, item_name, amount_twd, amount_rmb, payment_method, expense_date, notes, exp_id)
    )

def delete_expense_record(exp_id: int):
    DBConnectionWrapper.execute_commit("DELETE FROM expenses WHERE id = ?", params=(exp_id,))

def clone_user_data(source_user: str, target_user: str):
    """將來源成員的全部消費明細與預算設定同步複製到目標成員"""
    # 複製預算
    source_budget = get_setting(f"budget_{source_user}", "20100")
    set_setting(f"budget_{target_user}", source_budget)
    
    # 複製消費明細
    source_expenses = get_expenses_by_user(source_user)
    # 先清除目標既有明細再匯入
    DBConnectionWrapper.execute_commit("DELETE FROM expenses WHERE user_name = ?", params=(target_user,))
    for exp in source_expenses:
        add_expense_record(
            exp.get("day", 0),
            exp.get("category", "其他"),
            exp.get("item_name", ""),
            float(exp.get("amount_twd", 0.0)),
            float(exp.get("amount_rmb", 0.0)),
            exp.get("payment_method", "微信支付"),
            str(exp.get("expense_date", "")),
            exp.get("notes", ""),
            target_user
        )
