"""
Streamlit 簡易任務與使用者管理後台 (app.py)
基於 database.py 提供直覺的 Web 介面，支援：
- 使用者新增與即時名單
- 任務建立、指派給使用者
- 任務狀態切換 (未完成/已完成) 與刪除
- 資料庫即時表格檢視 (users & tasks) 與資料統計
"""

from __future__ import annotations

import os
import sqlite3
import pandas as pd
import streamlit as st

import database
from database import Database

# 頁面配置
st.set_page_config(
    page_title="任務與使用者管理後台",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = os.environ.get("DB_PATH", "app.db")



@st.cache_resource
def get_db_instance() -> Database:
    """快取資料庫實例以供 Streamlit 頁面共用"""
    db = Database(DB_PATH)
    db.init_db()
    return db


db = get_db_instance()


def seed_sample_data():
    """若資料庫為空，快速注入範例資料"""
    users = db.get_all_users()
    if not users:
        u1 = db.create_user("alice_chen", "alice@example.com")
        u2 = db.create_user("bob_lin", "bob@example.com")
        u3 = db.create_user("carol_wang", "carol@example.com")
        db.create_task(u1, "設計 SQLite 資料表架構", "包含 users 與 tasks 資料表及 CASCADE 外鍵")
        db.create_task(u1, "撰寫 database.py 模組", "封裝 CRUD 函式與 Database 類別")
        db.create_task(u2, "撰寫自動化單元測試", "使用 unittest 涵蓋所有 CRUD 與例外情況")
        db.create_task(u3, "建立 Streamlit 管理後台", "提供即時使用者指派與任務追蹤介面")
        st.toast("已自動載入範例資料！", icon="🎉")


def generate_test_data() -> tuple[int, int]:
    """寫入 3 位使用者與 10 筆不同狀態的測試任務"""
    import time

    batch_tag = int(time.time()) % 100000

    # 3 位使用者
    user_specs = [
        (f"dev_john_{batch_tag}", f"john_{batch_tag}@example.com"),
        (f"qa_emma_{batch_tag}", f"emma_{batch_tag}@example.com"),
        (f"pm_alex_{batch_tag}", f"alex_{batch_tag}@example.com"),
    ]

    created_user_ids = []
    for uname, uemail in user_specs:
        uid = db.create_user(uname, uemail)
        created_user_ids.append(uid)

    u_dev, u_qa, u_pm = created_user_ids

    # 10 筆不同狀態的測試任務 (包含 5 筆已完成, 5 筆進行中)
    tasks_to_create = [
        (u_dev, "重構 SQLite 連線池機制", "提升高並行情境下的連線復用率", True),
        (u_dev, "導入資料庫交易 Retry 機制", "處理鎖定與競爭條件例外", False),
        (u_dev, "優化任務查詢 SQL 索引", "針對 user_id 與 completed 欄位建立複合索引", True),
        (u_dev, "撰寫後端健康檢查 API", "提供 /_stcore/health 端點監控", True),
        (u_qa, "執行外鍵約束負面測試", "驗證不存在之 user_id 無法插入 tasks", True),
        (u_qa, "驗證 CASCADE 級聯刪除行為", "確認刪除使用者後任務完整被清理", False),
        (u_qa, "自動化效能壓力測試", "模擬並行 CRUD 請求並產出效能報告", False),
        (u_pm, "整理 Q3 專案里程碑規劃", "彙整開發與 QA 進度，排定 Release 日期", True),
        (u_pm, "召開跨部門需求審查會議", "確認管理後台儀表板第二期功能清單", False),
        (u_pm, "撰寫系統使用者操作說明手冊", "產出 Markdown 與 PDF 格式操作手冊", False),
    ]

    created_tasks_count = 0
    for uid, title, desc, comp in tasks_to_create:
        tid = db.create_task(uid, title, desc)
        if comp:
            db.update_task(tid, completed=True)
        created_tasks_count += 1

    return len(created_user_ids), created_tasks_count


def analyze_task_risks_and_recommendations(
    filtered_tasks: list[dict],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """根據當前篩選出的任務自動分析 2-3 項瓶頸風險與工程改善建議"""
    pending_tasks = [t for t in filtered_tasks if not t.get("completed")]
    total_count = len(filtered_tasks)
    pending_count = len(pending_tasks)

    if not pending_tasks:
        return (
            [
                (
                    "無明顯阻塞風險（全數達標）",
                    "當前篩選範圍內的所有任務均已標記為完成，流程運作正常，無交付延遲風險。",
                )
            ],
            [
                (
                    "發布前封版檢驗與資料庫快照",
                    "建議排定版本發布封版 (Code Freeze)，並對 SQLite 實體資料庫進行 VACUUM 與定時備份。",
                ),
                (
                    "維護單元測試與自動化回歸管線",
                    "持績執行 test_database.py 確保既有 18 項測試案例於 CI 流程持續維持 100% 通過率。",
                ),
            ],
        )

    risks: list[tuple[str, str]] = []
    recommendations: list[tuple[str, str]] = []

    # 1. 資源負載集中度分析 (Workload Concentration)
    user_pending_counts: dict[str, int] = {}
    for t in pending_tasks:
        uname = t.get("username") or f"未知成員 (#{t['user_id']})"
        user_pending_counts[uname] = user_pending_counts.get(uname, 0) + 1

    if user_pending_counts:
        top_user, top_count = max(user_pending_counts.items(), key=lambda x: x[1])
        if top_count >= 2 and (top_count / pending_count >= 0.4 or top_count >= 3):
            ratio = (top_count / pending_count) * 100
            risks.append(
                (
                    f"人力資源負載集中風險 ({top_user})",
                    f"成員 `{top_user}` 承擔了 {top_count} 筆未完成任務（佔進行中總數之 {ratio:.0f}%），極易形成關鍵交付路徑上的單點延遲瓶頸 (SPOF)。",
                )
            )
            recommendations.append(
                (
                    "工作負載平衡與結對支援",
                    f"建議將 `{top_user}` 名下非核心相依的任務適度分流或指派其他成員協助，或安排結對編程 (Pair Programming) 加速收斂。",
                )
            )

    # 2. 關鍵字與工程領域分析 (Domain Risk Analysis)
    all_text = " ".join(
        f"{t.get('title', '')} {t.get('description', '')}".lower() for t in pending_tasks
    )

    # 核心資料庫與交易風險
    if any(k in all_text for k in ["sqlite", "資料庫", "連線池", "交易", "retry", "鎖定", "索引", "lock"]):
        risks.append(
            (
                "儲存層連線競爭與死鎖風險",
                "進行中包含 SQLite 連線池管理、交易重試或索引調整等底層任務，若未經完整隔離可能引發高併發讀寫下的 `database is locked` 異常。",
            )
        )
        recommendations.append(
            (
                "強化交易逾時與冪等性機制",
                "為 SQLite 連線設定合適的 timeout 參數，落實 Context Manager 交易原子性，並在單元測試中模擬多執行緒併發寫入情境。",
            )
        )

    # 測試與驗證滯後風險
    if any(k in all_text for k in ["測試", "qa", "壓力", "外鍵", "cascade", "驗證", "回歸"]):
        risks.append(
            (
                "品質門禁與壓力測試滯後風險",
                "外鍵約束負面測試、CASCADE 刪除驗證或壓力測試尚未結案，若提早上線可能隱含資料孤兒或記憶體洩漏風險。",
            )
        )
        recommendations.append(
            (
                "落實 CI/CD 自動化測試門檻",
                "將自動化測試腳本掛載至 Pre-commit Hook 與持續整合流程，確保全部測試通過前禁止合併至生產主分支。",
            )
        )

    # 跨部門需求與文件風險
    if any(k in all_text for k in ["需求", "審查", "會議", "手冊", "里程碑", "規格", "文件"]):
        risks.append(
            (
                "跨部門需求定義與交付驗收風險",
                "需求審查與操作手冊尚在進行中，若規格未及時凍結容易引發範疇蔓延 (Scope Creep) 與使用者操作門檻增加。",
            )
        )
        recommendations.append(
            (
                "凍結完工標準 (DoD) 並採用滾動式文件編撰",
                "與產品團隊明確規範 Definition of Done，並隨開發進度同步維護 Markdown 與 API 文件，縮短交接週期。",
            )
        )

    # 3. WIP 在製品積壓分析
    if pending_count >= 5:
        risks.append(
            (
                f"在製品 (WIP) 過高引發切換損耗 ({pending_count} 筆進行中)",
                "多條任務並行推進容易導致開發人員頻繁發生上下文切換 (Context Switching)，進而拉長整體交付週期 (Cycle Time)。",
            )
        )
        recommendations.append(
            (
                "推行 WIP 限制與精實交付",
                "嚴格設定各成員進行中任務上限 (建議不超過 2 筆)，貫徹『停止開始，聚焦完成』原則，集中火力結清卡片。",
            )
        )

    # 4. 兜底補充（確保提供 2-3 項分析）
    fallback_risks = [
        (
            "時程依賴度與關鍵路徑不確定性",
            "進行中任務可能存在隱性上下游依賴關係，任一環節受阻均可能連鎖影響後續交付進程。",
        ),
        (
            "可觀測性與健康度監控盲點",
            "服務端若缺乏統一的結構化日誌或即時告警機制，異常發生時將提高平均修復時間 (MTTR)。",
        ),
    ]
    fallback_recs = [
        (
            "細化任務顆粒度與優先級標記",
            "將大於 1 個工作天的任務拆解成具體可量化的子任務，並標註相依性圖譜以識別關鍵路徑。",
        ),
        (
            "導入端點監控與結構化日誌 (Structured Logging)",
            "善用健康檢查端點 (/_stcore/health) 結合日誌追蹤，確保異常能於秒級內捕捉與警示。",
        ),
    ]

    for fb_r, fb_rec in zip(fallback_risks, fallback_recs):
        if len(risks) < 3:
            risks.append(fb_r)
        if len(recommendations) < 3:
            recommendations.append(fb_rec)

    return risks[:3], recommendations[:3]


def auto_balance_workload(db: Database) -> list[dict[str, Any]]:
    """自動分析成員負載，將進行中任務從負載過高的成員轉移指派至相對空閒成員，寫入資料庫並回傳調度日誌。"""
    all_users = db.get_all_users()
    if len(all_users) < 2:
        return []

    all_tasks = db.get_all_tasks()
    pending_tasks = [t for t in all_tasks if not t.get("completed")]
    if not pending_tasks:
        return []

    user_names = {u["id"]: u["username"] for u in all_users}
    user_pending_tasks: dict[int, list[dict[str, Any]]] = {u["id"]: [] for u in all_users}

    for t in pending_tasks:
        uid = t.get("user_id")
        if uid in user_pending_tasks:
            user_pending_tasks[uid].append(t)

    reassigned_logs: list[dict[str, Any]] = []

    while True:
        # 找出當前負載最高與最低的成員
        max_uid = max(user_pending_tasks.keys(), key=lambda uid: len(user_pending_tasks[uid]))
        min_uid = min(user_pending_tasks.keys(), key=lambda uid: len(user_pending_tasks[uid]))
        max_count = len(user_pending_tasks[max_uid])
        min_count = len(user_pending_tasks[min_uid])

        # 若最大與最小差值 <= 1，代表已達到最佳平衡狀態
        if max_count - min_count <= 1:
            break

        # 從負載最高者移轉一筆任務至負載最低者
        task_to_move = user_pending_tasks[max_uid].pop()
        success = db.update_task(task_to_move["id"], user_id=min_uid)

        if success:
            reassigned_logs.append(
                {
                    "task_id": task_to_move["id"],
                    "title": task_to_move["title"],
                    "from_user": user_names.get(max_uid, f"User #{max_uid}"),
                    "to_user": user_names.get(min_uid, f"User #{min_uid}"),
                }
            )
            user_pending_tasks[min_uid].append(task_to_move)
        else:
            break

    return reassigned_logs


# 嘗試注入範例資料（如為空資料庫）
seed_sample_data()

# -------------------------------------------------------------
# 側邊欄：使用者管理與系統統計
# -------------------------------------------------------------
with st.sidebar:
    st.header("👤 使用者管理")

    with st.expander("➕ 快速新增使用者", expanded=True):
        with st.form(key="create_user_form", clear_on_submit=True):
            new_username = st.text_input("使用者名稱 (Username)", placeholder="例如: david_wu").strip()
            new_email = st.text_input("電子信箱 (Email)", placeholder="例如: david@example.com").strip()
            submitted = st.form_submit_button("新增使用者", use_container_width=True)

            if submitted:
                if not new_username or not new_email:
                    st.error("使用者名稱與電子信箱均為必填！")
                else:
                    try:
                        user_id = db.create_user(new_username, new_email)
                        st.success(f"使用者 `{new_username}` (ID: {user_id}) 建立成功！")
                        st.rerun()
                    except sqlite3.IntegrityError as e:
                        st.error(f"建立失敗：使用者名稱或信箱可能已存在！\n詳細: {e}")
                    except Exception as e:
                        st.error(f"發生未知錯誤: {e}")

    st.divider()

    # 測試資料產生工具
    st.subheader("🧪 測試工具")
    st.caption("點擊下方按鈕自動寫入 3 位使用者與 10 筆不同狀態之任務：")
    if st.button("🎲 產生測試資料", use_container_width=True, type="primary"):
        try:
            u_count, t_count = generate_test_data()
            st.toast(f"已成功建立 {u_count} 位使用者與 {t_count} 筆測試任務！", icon="🎉")
            st.rerun()
        except Exception as e:
            st.error(f"產生測試資料失敗: {e}")

    st.divider()

    # 統計指標
    all_users = db.get_all_users()
    all_tasks = db.get_all_tasks()
    completed_count = sum(1 for t in all_tasks if t.get("completed"))
    pending_count = len(all_tasks) - completed_count

    st.subheader("📊 系統總覽")
    col_stat1, col_stat2 = st.columns(2)
    col_stat1.metric("註冊使用者", len(all_users))
    col_stat2.metric("任務總數", len(all_tasks))

    col_stat3, col_stat4 = st.columns(2)
    col_stat3.metric("進行中任務", pending_count)
    col_stat4.metric("已完成任務", completed_count)

    st.divider()
    st.caption(f"📁 儲存路徑: `{DB_PATH}`")
    if st.button("🔄 重新整理資料", use_container_width=True):
        st.rerun()

# -------------------------------------------------------------
# 主畫面：標題與分頁
# -------------------------------------------------------------
st.title("📋 任務與使用者管理後台")
st.markdown("透過直覺介面即時新增任務、指派使用者，並即時檢視 SQLite 資料庫內的表格變動。")

tab_tasks, tab_add_task, tab_users = st.tabs(["📝 任務列表與管理", "➕ 新增並指派任務", "👥 使用者名冊"])

# -------------------------------------------------------------
# Tab 1: 任務列表與管理
# -------------------------------------------------------------
with tab_tasks:
    st.subheader("即時任務清單")

    # 1. 快速多選過濾區
    f_col1, f_col2, f_col3 = st.columns([3, 2, 3])
    with f_col1:
        user_list = sorted(list({u["username"] for u in all_users if u.get("username")}))
        selected_usernames = st.multiselect(
            "👤 依使用者名稱過濾",
            options=user_list,
            placeholder="可多選使用者（留空顯示全部）",
            key="filter_users_multiselect",
        )
    with f_col2:
        selected_statuses = st.multiselect(
            "📌 依任務狀態過濾",
            options=["進行中", "已完成"],
            placeholder="可多選狀態（留空顯示全部）",
            key="filter_status_multiselect",
        )
    with f_col3:
        search_query = st.text_input(
            "🔍 搜尋任務標題或描述",
            placeholder="輸入關鍵字...",
            key="filter_search_input",
        ).strip().lower()

    # 執行篩選資料
    filtered_tasks = all_tasks.copy()

    # 依使用者多選篩選
    if selected_usernames:
        filtered_tasks = [t for t in filtered_tasks if t.get("username") in selected_usernames]

    # 依狀態多選篩選
    if selected_statuses:
        allowed_completed_values = []
        if "進行中" in selected_statuses:
            allowed_completed_values.append(False)
        if "已完成" in selected_statuses:
            allowed_completed_values.append(True)
        filtered_tasks = [t for t in filtered_tasks if t.get("completed") in allowed_completed_values]

    # 依關鍵字搜尋
    if search_query:
        filtered_tasks = [
            t
            for t in filtered_tasks
            if search_query in t["title"].lower()
            or (t["description"] and search_query in t["description"].lower())
            or (t.get("username") and search_query in t["username"].lower())
        ]

    # 2. 一鍵生成任務進度摘要按鈕與統計文字卡片
    if "show_progress_summary" not in st.session_state:
        st.session_state.show_progress_summary = False

    s_btn_col, s_info_col = st.columns([2, 5])
    with s_btn_col:
        if st.button("📊 一鍵生成任務進度摘要", use_container_width=True, type="secondary"):
            st.session_state.show_progress_summary = True

    if st.session_state.show_progress_summary:
        total_filtered = len(filtered_tasks)
        completed_filtered = sum(1 for t in filtered_tasks if t.get("completed"))
        pending_filtered = total_filtered - completed_filtered
        completion_rate = (completed_filtered / total_filtered * 100) if total_filtered > 0 else 0.0

        with st.container(border=True):
            card_title_col, card_close_col = st.columns([6, 1])
            with card_title_col:
                st.markdown("#### 📋 任務進度摘要統計卡片")
            with card_close_col:
                if st.button("收合 ✕", key="close_summary_card"):
                    st.session_state.show_progress_summary = False
                    st.rerun()

            stat_c1, stat_c2, stat_c3, stat_c4 = st.columns(4)
            stat_c1.metric("篩選任務總數", f"{total_filtered} 筆")
            stat_c2.metric("已完成任務", f"{completed_filtered} 筆")
            stat_c3.metric("進行中任務", f"{pending_filtered} 筆")
            stat_c4.metric("完成進度", f"{completion_rate:.1f}%")

            st.progress(completion_rate / 100.0)

            if total_filtered > 0:
                user_task_breakdown = {}
                for t in filtered_tasks:
                    uname = t.get("username") or f"未知成員 (ID: {t['user_id']})"
                    if uname not in user_task_breakdown:
                        user_task_breakdown[uname] = {"total": 0, "completed": 0}
                    user_task_breakdown[uname]["total"] += 1
                    if t.get("completed"):
                        user_task_breakdown[uname]["completed"] += 1

                user_summary_lines = []
                for uname, data in sorted(user_task_breakdown.items()):
                    u_pct = (data["completed"] / data["total"] * 100) if data["total"] > 0 else 0.0
                    user_summary_lines.append(
                        f"- **{uname}**：共 `{data['total']}` 筆任務，已完成 `{data['completed']}` 筆 (`{u_pct:.1f}%`)"
                    )

                if completion_rate == 100.0:
                    status_text = "🎉 **全數達標**：當前篩選出的任務已 100% 全數完成！"
                elif completion_rate >= 50.0:
                    status_text = "🚀 **進度良好**：完成度已超過半數，推進進展順利！"
                else:
                    status_text = "⏳ **進行中**：目前尚有過半任務待處理，請持續追蹤。"

                st.markdown(
                    f"""
> **💡 進度總評**：{status_text}
>
> **👥 成員執行狀況**：
{"\n".join(user_summary_lines)}
                    """
                )

                # 3. 智慧工程分析與風險洞察區塊
                st.divider()
                st.markdown("### 🧠 智慧工程分析與風險洞察")

                risks, recs = analyze_task_risks_and_recommendations(filtered_tasks)

                if pending_filtered == 0:
                    st.success("🎉 **進度完美達標**：當前篩選範圍內所有任務均已完成，無待處理的阻礙風險！")
                    with st.container(border=True):
                        st.markdown("#### 💡 維運與發布建議")
                        for idx, (title, desc) in enumerate(recs, 1):
                            st.markdown(f"**{idx}. {title}**\n\n{desc}")
                else:
                    col_risk, col_rec = st.columns(2)
                    with col_risk:
                        st.markdown("#### ⚠️ 當前瓶頸風險 (Bottlenecks & Risks)")
                        risk_content = [f"**{idx}. {title}**\n\n{desc}" for idx, (title, desc) in enumerate(risks, 1)]
                        st.warning("\n\n---\n\n".join(risk_content))

                    with col_rec:
                        st.markdown("#### 💡 工程改善建議 (Engineering Action Items)")
                        rec_content = [f"**{idx}. {title}**\n\n{desc}" for idx, (title, desc) in enumerate(recs, 1)]
                        st.info("\n\n---\n\n".join(rec_content))

                        if "last_balance_msg" in st.session_state and st.session_state["last_balance_msg"]:
                            st.success(f"**⚡ 最近調度平衡紀錄：**\n\n{st.session_state.pop('last_balance_msg')}")

                        if st.button(
                            "⚖️ 自動平衡成員負載並更新狀態",
                            key="auto_balance_workload_btn",
                            use_container_width=True,
                            type="primary",
                        ):
                            reassigned_log = auto_balance_workload(db)
                            if reassigned_log:
                                summary_items = [
                                    f"- 任務 `#{item['task_id']}` ({item['title']})：`{item['from_user']}` ➔ `{item['to_user']}`"
                                    for item in reassigned_log
                                ]
                                st.toast(f"🎉 已成功重新平衡 {len(reassigned_log)} 筆任務指派！", icon="⚖️")
                                st.session_state["last_balance_msg"] = "\n".join(summary_items)
                            else:
                                st.toast("ℹ️ 各成員負載已處於平衡狀態，無需額外調度！", icon="👌")
                            st.rerun()


            else:
                st.caption("ℹ️ 目前篩選條件下無符合的任務項目。")

    if not filtered_tasks:
        st.info("尚無符合篩選條件的任務。")

    else:
        # 以互動表格與卡片形式展示
        for task in filtered_tasks:
            status_badge = "✅ **已完成**" if task["completed"] else "⏳ **進行中**"
            assigned_name = task.get("username") or f"未知使用者 (ID: {task['user_id']})"

            with st.container(border=True):
                t_col1, t_col2, t_col3, t_col4 = st.columns([4, 2, 2, 2])
                with t_col1:
                    st.markdown(f"### {task['title']}")
                    if task["description"]:
                        st.caption(task["description"])
                    st.caption(f"建立時間: `{task['created_at']}` | 任務 ID: `#{task['id']}`")

                with t_col2:
                    st.markdown(f"**指派給**\n\n👤 `{assigned_name}`")

                with t_col3:
                    st.markdown(f"**狀態**\n\n{status_badge}")
                    new_status = not task["completed"]
                    toggle_btn_text = "標示為未完成" if task["completed"] else "標示為已完成"
                    if st.button(toggle_btn_text, key=f"toggle_{task['id']}", use_container_width=True):
                        db.update_task(task["id"], completed=new_status)
                        st.toast(f"任務 #{task['id']} 狀態已更新！")
                        st.rerun()

                with t_col4:
                    st.markdown("**操作**")
                    if st.button("🗑️ 刪除", key=f"delete_task_{task['id']}", use_container_width=True):
                        db.delete_task(task["id"])
                        st.toast(f"任務 #{task['id']} 已刪除！")
                        st.rerun()

    # 資料庫原始資料表檢視 (tasks)
    with st.expander("🔍 檢視 `tasks` 資料庫原始表格 (Raw Table)", expanded=False):
        if all_tasks:
            df_tasks = pd.DataFrame(all_tasks)
            st.dataframe(df_tasks, use_container_width=True)
        else:
            st.write("資料表目前為空。")

# -------------------------------------------------------------
# Tab 2: 新增並指派任務
# -------------------------------------------------------------
with tab_add_task:
    st.subheader("新增任務並指派成員")

    if not all_users:
        st.warning("目前資料庫中尚無任何使用者！請先於左側邊欄新增至少一位使用者。")
    else:
        with st.form(key="create_task_form", clear_on_submit=True):
            user_select_dict = {
                f"{u['username']} (ID: {u['id']}, {u['email']})": u["id"] for u in all_users
            }
            selected_assignee_label = st.selectbox(
                "選擇指派對象 (Assignee)*",
                options=list(user_select_dict.keys()),
            )
            task_title = st.text_input("任務標題 (Title)*", placeholder="例如: 撰寫 API 文件").strip()
            task_desc = st.text_area(
                "任務詳細描述 (Description)",
                placeholder="詳細任務目標、需求與備註...",
                height=120,
            ).strip()

            submit_task = st.form_submit_button("🚀 建立任務並指派", use_container_width=True)

            if submit_task:
                if not task_title:
                    st.error("請輸入任務標題！")
                else:
                    target_user_id = user_select_dict[selected_assignee_label]
                    try:
                        task_id = db.create_task(
                            user_id=target_user_id,
                            title=task_title,
                            description=task_desc,
                        )
                        st.success(f"任務建立成功！任務編號: `#{task_id}` 已指派給 `{selected_assignee_label}`")
                        st.rerun()
                    except Exception as e:
                        st.error(f"建立任務失敗: {e}")

# -------------------------------------------------------------
# Tab 3: 使用者名冊與管理
# -------------------------------------------------------------
with tab_users:
    st.subheader("即時使用者名冊")

    if not all_users:
        st.info("尚無使用者資料。")
    else:
        # 計算每個使用者名下的任務數量
        user_table_data = []
        for u in all_users:
            u_tasks = [t for t in all_tasks if t["user_id"] == u["id"]]
            u_completed = sum(1 for t in u_tasks if t["completed"])
            user_table_data.append(
                {
                    "ID": u["id"],
                    "使用者名稱": u["username"],
                    "電子信箱": u["email"],
                    "指派任務數": len(u_tasks),
                    "已完成任務數": u_completed,
                    "註冊時間": u["created_at"],
                }
            )

        df_users_display = pd.DataFrame(user_table_data)
        st.dataframe(df_users_display, use_container_width=True)

        st.divider()
        st.markdown("#### ⚠️ 使用者維護與刪除")
        del_user_dict = {f"{u['username']} (ID: {u['id']})": u["id"] for u in all_users}
        del_selected_label = st.selectbox("選擇欲刪除的使用者", list(del_user_dict.keys()))
        target_del_id = del_user_dict[del_selected_label]

        st.caption("提示：由於啟用了外鍵級聯刪除 (`ON DELETE CASCADE`)，刪除該使用者將一併刪除其所有關聯任務！")
        if st.button(f"確認刪除使用者 {del_selected_label}", type="secondary"):
            deleted = db.delete_user(target_del_id)
            if deleted:
                st.toast(f"使用者 {del_selected_label} 及其關聯任務已全數刪除！")
                st.rerun()
            else:
                st.error("刪除失敗，使用者可能不存在。")
