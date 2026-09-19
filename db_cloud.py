# -*- coding: utf-8 -*-
"""
上海 4 天 3 夜旅遊記帳與行程管理系統 - 雙軌資料庫適配層 (Dual-Mode DB Adapter)
支援：
  1. 雲端優先 (Cloud Mode): Supabase / PostgreSQL 外部資料庫 (透過 st.secrets 或環境變數)
  2. 本地回退 (Local Fallback): SQLite (travel.db)
"""

import os
import re
import sqlite3
from typing import Optional, Any
import streamlit as st

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
                url = st.secrets["connections"]["postgresql"].get("url")
                if url and isinstance(url, str) and url.strip():
                    return url.strip()
            if "supabase" in st.secrets and "db_url" in st.secrets["supabase"]:
                url = st.secrets["supabase"].get("db_url")
                if url and isinstance(url, str) and url.strip():
                    return url.strip()
            if "DATABASE_URL" in st.secrets:
                url = st.secrets["DATABASE_URL"]
                if url and isinstance(url, str) and url.strip():
                    return url.strip()
    except Exception:
        pass
        
    # 2. 次之從環境變數檢查
    url_env = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    return url_env.strip() if url_env else None

def is_cloud_mode() -> bool:
    """是否處於雲端資料庫模式"""
    return bool(get_cloud_db_url())

def adapt_sql_for_pg(sql: str) -> str:
    """將 SQLite 語法轉譯為 PostgreSQL 語法"""
    s = sql.strip()
    
    # 忽略 SQLite PRAGMA 指令
    if s.upper().startswith("PRAGMA"):
        return "SELECT 1"
        
    # 轉譯 INSERT OR IGNORE INTO
    if "INSERT OR IGNORE INTO" in s:
        s = s.replace("INSERT OR IGNORE INTO", "INSERT INTO")
        if "ON CONFLICT" not in s.upper():
            s = s.rstrip("; ") + " ON CONFLICT DO NOTHING"
            
    # 轉譯 INSERT OR REPLACE INTO settings
    elif "INSERT OR REPLACE INTO settings" in s:
        s = s.replace("INSERT OR REPLACE INTO settings", "INSERT INTO settings")
        if "ON CONFLICT" not in s.upper():
            s = s.rstrip("; ") + " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
            
    # 轉譯一般 INSERT OR REPLACE INTO
    elif "INSERT OR REPLACE INTO" in s:
        s = s.replace("INSERT OR REPLACE INTO", "INSERT INTO")

    # AUTOINCREMENT 轉換為 SERIAL PRIMARY KEY
    s = re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'SERIAL PRIMARY KEY', s, flags=re.IGNORECASE)

    # 欄位 desc TEXT 轉譯為 "desc" TEXT 避免保留關鍵字衝突
    s = re.sub(r'\bdesc\s+TEXT\b', '"desc" TEXT', s, flags=re.IGNORECASE)

    # 參數問號 ? 轉譯為 %s
    s = s.replace("?", "%s")
    return s

class RowAdapter:
    """相容性 Row 物件，支援 row[0]、row['column'] 以及 desc/desc_text 雙向映射"""
    def __init__(self, raw_row):
        self._raw = raw_row

    def __getitem__(self, key):
        if isinstance(key, str):
            if key == "desc" and "desc" not in self._raw and "desc_text" in self._raw:
                return self._raw["desc_text"]
            if key == "desc_text" and "desc_text" not in self._raw and "desc" in self._raw:
                return self._raw["desc"]
        return self._raw[key]

    def get(self, key, default=None):
        if key == "desc" and "desc" not in self._raw and "desc_text" in self._raw:
            return self._raw["desc_text"]
        if key == "desc_text" and "desc_text" not in self._raw and "desc" in self._raw:
            return self._raw["desc"]
        return self._raw.get(key, default) if hasattr(self._raw, "get") else default

    def __iter__(self):
        return iter(self._raw)

    def __len__(self):
        return len(self._raw)

    def __repr__(self):
        return repr(self._raw)

class CloudCursorWrapper:
    """包裝 psycopg2 cursor 使其介面與行為 100% 相容於 sqlite3 cursor"""
    def __init__(self, pg_cursor):
        self._cur = pg_cursor

    def execute(self, sql: str, params: tuple = ()):
        adapted_sql = adapt_sql_for_pg(sql)
        if adapted_sql == "SELECT 1":
            return self
        try:
            self._cur.execute(adapted_sql, params)
        except Exception as e:
            # 忽視建立表時的已存在或重複錯誤
            err_msg = str(e).lower()
            if "already exists" in err_msg or "duplicate key" in err_msg:
                pass
            else:
                raise e
        return self

    def executemany(self, sql: str, seq_of_params):
        adapted_sql = adapt_sql_for_pg(sql)
        self._cur.executemany(adapted_sql, seq_of_params)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        return RowAdapter(row) if row is not None else None

    def fetchall(self):
        rows = self._cur.fetchall()
        return [RowAdapter(r) for r in rows] if rows else []

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size else self._cur.fetchmany()
        return [RowAdapter(r) for r in rows] if rows else []

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        return None

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass

class CloudConnectionWrapper:
    """包裝 psycopg2 connection 使其與 sqlite3 connection 介面完全相容"""
    def __init__(self, db_url: str):
        import psycopg2
        from psycopg2.extras import DictCursor
        # 轉換 postgresql:// 格式
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        self._conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
        self._conn.autocommit = False

    def cursor(self):
        return CloudCursorWrapper(self._conn.cursor())

    def execute(self, sql: str, params: tuple = ()):
        cur = self.cursor()
        return cur.execute(sql, params)

    def executemany(self, sql: str, seq_of_params):
        cur = self.cursor()
        return cur.executemany(sql, seq_of_params)

    def commit(self):
        try:
            self._conn.commit()
        except Exception:
            pass

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

def get_compatible_db():
    """統一獲取資料庫連線（雲端連線優先，本地 SQLite 回退）"""
    cloud_url = get_cloud_db_url()
    if cloud_url:
        try:
            return CloudConnectionWrapper(cloud_url)
        except Exception as e:
            # 若雲端連線失敗，優雅回退到本地 SQLite 並提示
            st.error(f"⚠️ 雲端資料庫連線失敗，自動回退至本地 SQLite 模式。錯誤原因: {e}")
            conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
