"""
Unit Tests for SQLite Database Module (database.py)
涵蓋使用者 (users) 與任務 (tasks) 的 CRUD、外鍵約束、級聯刪除、
檔案型資料庫持久化、以及模組級函式的自動化測試。
"""

import os
import sqlite3
import tempfile
import unittest

import database
from database import (
    Database,
    create_task,
    create_user,
    delete_task,
    delete_user,
    get_database,
    get_task,
    get_tasks_by_user,
    get_user,
    get_user_by_username,
    init_db,
    reset_databases,
    update_task,
    update_user,
)


class TestDatabaseOOP(unittest.TestCase):
    """測試 Database 類別導向介面與 CRUD 邏輯"""

    def setUp(self):
        """每個測試使用獨立的記憶體資料庫"""
        self.db = Database(":memory:")
        self.db.init_db()

    def tearDown(self):
        """測試結束後關閉連線"""
        self.db.close()

    # -------------------------------------------------------------
    # 使用者 (User) CRUD 測試
    # -------------------------------------------------------------
    def test_create_user_success(self):
        """測試成功建立使用者並驗證回傳 ID 與欄位"""
        user_id = self.db.create_user("alice", "alice@example.com")
        self.assertIsInstance(user_id, int)
        self.assertGreater(user_id, 0)

        user = self.db.get_user(user_id)
        self.assertIsNotNone(user)
        self.assertEqual(user["id"], user_id)
        self.assertEqual(user["username"], "alice")
        self.assertEqual(user["email"], "alice@example.com")
        self.assertIn("created_at", user)

    def test_get_user_by_username(self):
        """測試依 username 查詢使用者"""
        user_id = self.db.create_user("bob", "bob@example.com")
        user = self.db.get_user_by_username("bob")
        self.assertIsNotNone(user)
        self.assertEqual(user["id"], user_id)
        self.assertEqual(user["username"], "bob")

        # 查詢不存在的使用者
        non_existent = self.db.get_user_by_username("ghost")
        self.assertIsNone(non_existent)

    def test_get_nonexistent_user(self):
        """測試查詢不存在的 user_id 回傳 None"""
        user = self.db.get_user(99999)
        self.assertIsNone(user)

    def test_duplicate_username_raises_error(self):
        """測試重複的使用者名稱拋出 sqlite3.IntegrityError"""
        self.db.create_user("charlie", "charlie1@example.com")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.create_user("charlie", "charlie2@example.com")

    def test_duplicate_email_raises_error(self):
        """測試重複的 Email 拋出 sqlite3.IntegrityError"""
        self.db.create_user("david", "david@example.com")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.create_user("david2", "david@example.com")

    def test_update_user(self):
        """測試更新使用者的 username 與 email"""
        user_id = self.db.create_user("eve", "eve@example.com")

        # 僅更新 email
        updated = self.db.update_user(user_id, email="eve_new@example.com")
        self.assertTrue(updated)
        user = self.db.get_user(user_id)
        self.assertEqual(user["email"], "eve_new@example.com")
        self.assertEqual(user["username"], "eve")

        # 同時更新 username 與 email
        updated = self.db.update_user(user_id, username="eve_updated", email="eve_final@example.com")
        self.assertTrue(updated)
        user = self.db.get_user(user_id)
        self.assertEqual(user["username"], "eve_updated")
        self.assertEqual(user["email"], "eve_final@example.com")

        # 未提供更新欄位回傳 False
        self.assertFalse(self.db.update_user(user_id))

        # 更新不存在的使用者回傳 False
        self.assertFalse(self.db.update_user(99999, username="nobody"))

    def test_delete_user(self):
        """測試刪除使用者"""
        user_id = self.db.create_user("frank", "frank@example.com")
        self.assertTrue(self.db.delete_user(user_id))

        # 刪除後應查無此人
        self.assertIsNone(self.db.get_user(user_id))

        # 再次刪除回傳 False
        self.assertFalse(self.db.delete_user(user_id))

    # -------------------------------------------------------------
    # 任務 (Task) CRUD 測試
    # -------------------------------------------------------------
    def test_create_task_success(self):
        """測試成功為使用者建立任務"""
        user_id = self.db.create_user("grace", "grace@example.com")
        task_id = self.db.create_task(user_id, "撰寫測試", "完成自動化單元測試")
        self.assertIsInstance(task_id, int)
        self.assertGreater(task_id, 0)

        task = self.db.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task["id"], task_id)
        self.assertEqual(task["user_id"], user_id)
        self.assertEqual(task["title"], "撰寫測試")
        self.assertEqual(task["description"], "完成自動化單元測試")
        self.assertFalse(task["completed"])
        self.assertIn("created_at", task)

    def test_get_nonexistent_task(self):
        """測試查詢不存在的任務回傳 None"""
        self.assertIsNone(self.db.get_task(99999))

    def test_get_tasks_by_user(self):
        """測試依 user_id 取得任務列表與排序"""
        user_id = self.db.create_user("heidi", "heidi@example.com")
        other_user_id = self.db.create_user("ivan", "ivan@example.com")

        # 使用者無任務時應回傳空列表
        self.assertEqual(self.db.get_tasks_by_user(user_id), [])

        # 建立任務
        t1 = self.db.create_task(user_id, "任務一", "第一項工作")
        t2 = self.db.create_task(user_id, "任務二", "第二項工作")
        self.db.create_task(other_user_id, "他人的任務", "不應被查到")

        tasks = self.db.get_tasks_by_user(user_id)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["id"], t1)
        self.assertEqual(tasks[0]["title"], "任務一")
        self.assertEqual(tasks[1]["id"], t2)
        self.assertEqual(tasks[1]["title"], "任務二")

    def test_update_task(self):
        """測試更新任務的標題、描述與完成狀態"""
        user_id = self.db.create_user("judy", "judy@example.com")
        task_id = self.db.create_task(user_id, "待辦任務", "初始描述")

        # 更新狀態為已完成
        updated = self.db.update_task(task_id, completed=True)
        self.assertTrue(updated)
        task = self.db.get_task(task_id)
        self.assertTrue(task["completed"])

        # 更新標題與描述
        updated = self.db.update_task(task_id, title="新標題", description="新描述", completed=False)
        self.assertTrue(updated)
        task = self.db.get_task(task_id)
        self.assertEqual(task["title"], "新標題")
        self.assertEqual(task["description"], "新描述")
        self.assertFalse(task["completed"])

        # 未提供欄位回傳 False
        self.assertFalse(self.db.update_task(task_id))

        # 更新不存在的任務回傳 False
        self.assertFalse(self.db.update_task(99999, title="不存在"))

    def test_delete_task(self):
        """測試刪除任務"""
        user_id = self.db.create_user("kevin", "kevin@example.com")
        task_id = self.db.create_task(user_id, "臨時任務")
        self.assertTrue(self.db.delete_task(task_id))

        # 刪除後查詢應為 None
        self.assertIsNone(self.db.get_task(task_id))

        # 再次刪除回傳 False
        self.assertFalse(self.db.delete_task(task_id))

    # -------------------------------------------------------------
    # 外鍵約束與級聯刪除 (Foreign Key & Cascade) 測試
    # -------------------------------------------------------------
    def test_foreign_key_insert_nonexistent_user(self):
        """測試為不存在的使用者建立任務時觸發外鍵約束拋出 sqlite3.IntegrityError"""
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.create_task(user_id=99999, title="孤兒任務")

    def test_cascade_delete_user_removes_tasks(self):
        """測試刪除使用者時，關聯任務會因 ON DELETE CASCADE 自動刪除"""
        user_id = self.db.create_user("leo", "leo@example.com")
        task1_id = self.db.create_task(user_id, "任務 A")
        task2_id = self.db.create_task(user_id, "任務 B")

        # 確認任務存在
        self.assertIsNotNone(self.db.get_task(task1_id))
        self.assertIsNotNone(self.db.get_task(task2_id))

        # 刪除使用者
        self.assertTrue(self.db.delete_user(user_id))

        # 驗證關聯任務已被自動級聯刪除
        self.assertIsNone(self.db.get_task(task1_id))
        self.assertIsNone(self.db.get_task(task2_id))
        self.assertEqual(self.db.get_tasks_by_user(user_id), [])

    # -------------------------------------------------------------
    # Context Manager 連線測試
    # -------------------------------------------------------------
    def test_context_manager(self):
        """測試 Database 類別支援 with 陳述式"""
        with Database(":memory:") as db:
            db.init_db()
            uid = db.create_user("mallory", "mallory@example.com")
            self.assertIsNotNone(db.get_user(uid))


class TestFileDatabase(unittest.TestCase):
    """測試實體檔案 SQLite 資料庫的持久化與重連行為"""

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_path = self.temp_file.name
        self.temp_file.close()

    def tearDown(self):
        if os.path.exists(self.temp_path):
            try:
                os.remove(self.temp_path)
            except PermissionError:
                pass

    def test_file_persistence_and_reconnect(self):
        """測試檔案資料庫在關閉後重新開啟，資料仍完整保留"""
        db1 = Database(self.temp_path)
        db1.init_db()
        uid = db1.create_user("persisted_user", "persisted@example.com")
        tid = db1.create_task(uid, "持久化任務", "檔案存檔測試")
        db1.close()

        # 重新開啟相同檔案連線
        db2 = Database(self.temp_path)
        user = db2.get_user(uid)
        task = db2.get_task(tid)
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "persisted_user")
        self.assertIsNotNone(task)
        self.assertEqual(task["title"], "持久化任務")
        db2.close()


class TestModuleLevelFunctions(unittest.TestCase):
    """測試模組級便利函式 (create_user, create_task 等)"""

    def setUp(self):
        reset_databases()

    def tearDown(self):
        reset_databases()

    def test_module_user_and_task_crud(self):
        """測試模組級函式直接操作預設資料庫"""
        init_db()
        uid = create_user("module_user", "module@example.com")
        self.assertIsInstance(uid, int)

        user = get_user(uid)
        self.assertEqual(user["username"], "module_user")

        user_by_name = get_user_by_username("module_user")
        self.assertEqual(user_by_name["id"], uid)

        self.assertTrue(update_user(uid, email="module_updated@example.com"))
        self.assertEqual(get_user(uid)["email"], "module_updated@example.com")

        tid = create_task(uid, "模組任務", "模組層級呼叫")
        task = get_task(tid)
        self.assertEqual(task["title"], "模組任務")

        tasks = get_tasks_by_user(uid)
        self.assertEqual(len(tasks), 1)

        self.assertTrue(update_task(tid, completed=True))
        self.assertTrue(get_task(tid)["completed"])

        self.assertTrue(delete_task(tid))
        self.assertIsNone(get_task(tid))

        self.assertTrue(delete_user(uid))
        self.assertIsNone(get_user(uid))

    def test_module_with_custom_db_instance(self):
        """測試模組函式接受自訂 Database 實例作為參數"""
        custom_db = Database(":memory:")
        custom_db.init_db()

        uid = create_user("custom_user", "custom@example.com", db_path=custom_db)
        self.assertIsNotNone(get_user(uid, db_path=custom_db))

        # 確認預設資料庫中並無此使用者
        self.assertIsNone(get_user(uid))
        custom_db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
