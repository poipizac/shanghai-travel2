"""
SQLite Database Module: Users & Tasks Management
提供使用者（users）與任務（tasks）資料表的建立與完整 CRUD 操作。
支援記憶體模式 (:memory:) 及實體檔案資料庫，內建外鍵約束 (PRAGMA foreign_keys = ON)。
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Union


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    completed BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


class Database:
    """SQLite 資料庫管理類別，封裝連線管理與 CRUD 操作。"""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()
        self.init_db()

    def _connect(self) -> None:
        """建立 SQLite 連線並啟用外鍵約束。"""
        if self._conn is None:
            if self.db_path != ":memory:":
                db_dir = os.path.dirname(self.db_path)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            self._conn = conn

    @property
    def connection(self) -> sqlite3.Connection:
        """取得當前資料庫連線，若已關閉則重新建立。"""
        if self._conn is None:
            self._connect()
        assert self._conn is not None
        return self._conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """交易管理 Context Manager：自動提交 (commit) 或回滾 (rollback)。"""
        with self._lock:
            conn = self.connection
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def init_db(self) -> None:
        """初始化資料庫架構（建立 users 與 tasks 資料表）。"""
        with self.transaction() as cursor:
            cursor.executescript(SCHEMA_SQL)

    def close(self) -> None:
        """關閉資料庫連線。"""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __enter__(self) -> Database:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ==========================================
    # User CRUD Operations
    # ==========================================

    def create_user(self, username: str, email: str) -> int:
        """建立新使用者，回傳使用者 ID (int)。若 username 或 email 重複會拋出 sqlite3.IntegrityError。"""
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO users (username, email) VALUES (?, ?)",
                (username, email),
            )
            return cursor.lastrowid

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """依 user_id 查詢使用者，若不存在回傳 None。"""
        with self.transaction() as cursor:
            cursor.execute(
                "SELECT id, username, email, created_at FROM users WHERE id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """依 username 查詢使用者，若不存在回傳 None。"""
        with self.transaction() as cursor:
            cursor.execute(
                "SELECT id, username, email, created_at FROM users WHERE username = ?",
                (username,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        email: Optional[str] = None,
    ) -> bool:
        """更新使用者資料。若成功更新回傳 True，無更新欄位或找不到使用者回傳 False。"""
        fields = []
        params = []
        if username is not None:
            fields.append("username = ?")
            params.append(username)
        if email is not None:
            fields.append("email = ?")
            params.append(email)

        if not fields:
            return False

        params.append(user_id)
        with self.transaction() as cursor:
            cursor.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = ?",
                params,
            )
            return cursor.rowcount > 0

    def delete_user(self, user_id: int) -> bool:
        """刪除指定 user_id 使用者（因 CASCADE 外鍵約束，關聯 tasks 將一併刪除）。成功回傳 True。"""
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return cursor.rowcount > 0

    def get_all_users(self) -> List[Dict[str, Any]]:
        """查詢所有使用者列表，依 id ASC 排列。"""
        with self.transaction() as cursor:
            cursor.execute(
                "SELECT id, username, email, created_at FROM users ORDER BY id ASC"
            )
            return [dict(r) for r in cursor.fetchall()]

    # ==========================================
    # Task CRUD Operations
    # ==========================================

    def create_task(
        self,
        user_id: int,
        title: str,
        description: str = "",
    ) -> int:
        """為指定使用者建立任務，回傳任務 ID (int)。若 user_id 不存在會因外鍵約束拋出 sqlite3.IntegrityError。"""
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO tasks (user_id, title, description, completed) VALUES (?, ?, ?, 0)",
                (user_id, title, description),
            )
            return cursor.lastrowid

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """依 task_id 查詢任務，若不存在回傳 None。completed 轉換為布林值。"""
        with self.transaction() as cursor:
            cursor.execute(
                "SELECT id, user_id, title, description, completed, created_at FROM tasks WHERE id = ?",
                (task_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["completed"] = bool(data["completed"])
            return data

    def get_tasks_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        """查詢特定使用者的所有任務列表，依建立順序 (id ASC) 排列。"""
        with self.transaction() as cursor:
            cursor.execute(
                "SELECT id, user_id, title, description, completed, created_at FROM tasks WHERE user_id = ? ORDER BY id ASC",
                (user_id,),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["completed"] = bool(item["completed"])
                results.append(item)
            return results

    def update_task(
        self,
        task_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        completed: Optional[bool] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        """更新任務資料。若成功更新回傳 True，無更新欄位或找不到任務回傳 False。"""
        fields = []
        params = []
        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if description is not None:
            fields.append("description = ?")
            params.append(description)
        if completed is not None:
            fields.append("completed = ?")
            params.append(1 if completed else 0)
        if user_id is not None:
            fields.append("user_id = ?")
            params.append(user_id)

        if not fields:
            return False

        params.append(task_id)
        with self.transaction() as cursor:
            cursor.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?",
                params,
            )
            return cursor.rowcount > 0

    def delete_task(self, task_id: int) -> bool:
        """刪除指定 task_id 任務。成功回傳 True。"""
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cursor.rowcount > 0

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """查詢所有任務列表（聯集使用者名稱），依 id ASC 排列。"""
        with self.transaction() as cursor:
            cursor.execute(
                """
                SELECT t.id, t.user_id, u.username, t.title, t.description, t.completed, t.created_at
                FROM tasks t
                LEFT JOIN users u ON t.user_id = u.id
                ORDER BY t.id ASC
                """
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["completed"] = bool(item["completed"])
                results.append(item)
            return results


# ==========================================
# Module-level Instances & Convenience API
# ==========================================

DEFAULT_DB_PATH = ":memory:"
_instances: Dict[str, Database] = {}
_registry_lock = threading.Lock()


def get_database(db_path: Union[str, Database, None] = None) -> Database:
    """取得或建立對應 db_path 的 Database 實例。支援傳入 Database 物件、檔案路徑或 None（預設記憶體）。"""
    if isinstance(db_path, Database):
        return db_path

    target_path = db_path if db_path is not None else DEFAULT_DB_PATH
    with _registry_lock:
        if target_path not in _instances:
            db = Database(target_path)
            db.init_db()
            _instances[target_path] = db
        return _instances[target_path]


def reset_databases() -> None:
    """關閉並清除所有已快取的 Database 實例（主要用於測試重置）。"""
    with _registry_lock:
        for db in _instances.values():
            db.close()
        _instances.clear()


def init_db(db_path: Union[str, Database, None] = None) -> Database:
    """初始化資料庫。若指定 db_path 則初始化該資料庫，並回傳 Database 實例。"""
    db = get_database(db_path)
    db.init_db()
    return db


def create_user(username: str, email: str, db_path: Union[str, Database, None] = None) -> int:
    """[模組級函式] 建立使用者"""
    return get_database(db_path).create_user(username, email)


def get_user(user_id: int, db_path: Union[str, Database, None] = None) -> Optional[Dict[str, Any]]:
    """[模組級函式] 依 user_id 取得使用者"""
    return get_database(db_path).get_user(user_id)


def get_user_by_username(username: str, db_path: Union[str, Database, None] = None) -> Optional[Dict[str, Any]]:
    """[模組級函式] 依 username 取得使用者"""
    return get_database(db_path).get_user_by_username(username)


def update_user(
    user_id: int,
    username: Optional[str] = None,
    email: Optional[str] = None,
    db_path: Union[str, Database, None] = None,
) -> bool:
    """[模組級函式] 更新使用者"""
    return get_database(db_path).update_user(user_id, username=username, email=email)


def delete_user(user_id: int, db_path: Union[str, Database, None] = None) -> bool:
    """[模組級函式] 刪除使用者"""
    return get_database(db_path).delete_user(user_id)


def create_task(
    user_id: int,
    title: str,
    description: str = "",
    db_path: Union[str, Database, None] = None,
) -> int:
    """[模組級函式] 建立任務"""
    return get_database(db_path).create_task(user_id, title, description=description)


def get_task(task_id: int, db_path: Union[str, Database, None] = None) -> Optional[Dict[str, Any]]:
    """[模組級函式] 依 task_id 取得任務"""
    return get_database(db_path).get_task(task_id)


def get_tasks_by_user(user_id: int, db_path: Union[str, Database, None] = None) -> List[Dict[str, Any]]:
    """[模組級函式] 取得使用者的所有任務"""
    return get_database(db_path).get_tasks_by_user(user_id)


def update_task(
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    completed: Optional[bool] = None,
    user_id: Optional[int] = None,
    db_path: Union[str, Database, None] = None,
) -> bool:
    """[模組級函式] 更新任務"""
    return get_database(db_path).update_task(
        task_id,
        title=title,
        description=description,
        completed=completed,
        user_id=user_id,
    )


def delete_task(task_id: int, db_path: Union[str, Database, None] = None) -> bool:
    """[模組級函式] 刪除任務"""
    return get_database(db_path).delete_task(task_id)


def get_all_users(db_path: Union[str, Database, None] = None) -> List[Dict[str, Any]]:
    """[模組級函式] 取得所有使用者列表"""
    return get_database(db_path).get_all_users()


def get_all_tasks(db_path: Union[str, Database, None] = None) -> List[Dict[str, Any]]:
    """[模組級函式] 取得所有任務列表（含使用者名稱）"""
    return get_database(db_path).get_all_tasks()
