import streamlit as st
import pandas as pd
import altair as alt
import sqlite3
import datetime
import os
import folium
from folium.plugins import LocateControl
from streamlit_folium import st_folium

# ==========================================
# 1. 頁面基本配置 (Mobile-First 原生架構)
# ==========================================
st.set_page_config(
    page_title="上海 4 天 3 夜旅遊記帳與行程",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. SQLite 資料庫初始化與操作函式
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "travel.db")

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 使用者名單表 (個人帳本切換隔離)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        name TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("INSERT OR IGNORE INTO users (name) VALUES ('本人')")
    cursor.execute("INSERT OR IGNORE INTO users (name) VALUES ('同行好友')")
    
    # 行程表
    cursor.execute("""
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
    
    # 支出表 (支援多使用者個人帳本隔離)
    cursor.execute("""
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
    
    # 檢查現有 expenses 是否有 user_name 欄位，若無則自動遷移加入
    cursor.execute("PRAGMA table_info(expenses)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if "user_name" not in existing_cols:
        cursor.execute("ALTER TABLE expenses ADD COLUMN user_name TEXT DEFAULT '本人'")
        conn.commit()
    
    # 清單表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS checklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        is_checked INTEGER DEFAULT 0,
        category TEXT DEFAULT '重要證件與App'
    )
    """)

    # 預算表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budget_limits (
        category TEXT PRIMARY KEY,
        budget_twd REAL NOT NULL,
        budget_rmb REAL NOT NULL
    )
    """)
    
    # 系統設定表 (持久化使用者自訂預算等設定)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('total_budget', '20100')")
    
    conn.commit()
    
    # 預填預算目標（若為空）
    cursor.execute("SELECT COUNT(*) FROM budget_limits")

    if cursor.fetchone()[0] == 0:
        default_budgets = [
            ("來回機票", 6500, 1460),
            ("飯店住宿", 4200, 940),
            ("景點門票", 4200, 940),
            ("交通出行", 1200, 270),
            ("餐飲伴手", 4000, 910)
        ]
        cursor.executemany("INSERT INTO budget_limits (category, budget_twd, budget_rmb) VALUES (?, ?, ?)", default_budgets)
        conn.commit()

    # 預填檢查清單（若為空）
    cursor.execute("SELECT COUNT(*) FROM checklist")
    if cursor.fetchone()[0] == 0:
        default_checklist = [
            ("台胞證（確認有效期限 6 個月以上）與護照正本", 1, "證件與通訊"),
            ("下載「微信 (WeChat)」並綁定台灣信用卡開通微信支付", 1, "數位支付"),
            ("下載「支付寶 (Alipay)」綁定信用卡，開通上海地鐵乘車碼", 1, "數位支付"),
            ("下載「上海迪士尼度假區 App」並提前註冊會員帳號", 1, "行程必備"),
            ("開通中港澳漫遊 eSIM / 漫遊通話（免翻牆連 LINE/FB/IG）", 0, "證件與通訊"),
            ("預訂耀雪冰雪世界全日滑雪門票與自備長厚襪", 0, "行程必備"),
            ("下載「高德地圖 App」儲存地鐵線路與離線地圖", 1, "交通導航"),
            ("下載「大眾點評 App」查詢周邊美食避坑與團購券", 0, "美食娛樂")
        ]
        cursor.executemany("INSERT INTO checklist (item_name, is_checked, category) VALUES (?, ?, ?)", default_checklist)
        conn.commit()

    # 預填行程表（若為空）
    cursor.execute("SELECT COUNT(*) FROM itinerary")
    if cursor.fetchone()[0] == 0:
        default_itinerary = [
            # Day 1
            (1, "13:20 - 15:30", "【光速卸重】浦東機場 ➔ 磁浮列車 ➔ 龍陽路站寄存行李", "磁浮體驗 & 輕裝就緒",
             "• 去程航班：春秋航空 9C8952 (11:15 桃園T1起飛 ➔ 13:20 抵達浦東T2)。\n• 浦東機場T2步行至磁浮站，憑登機證享優惠價 40 RMB（7分20秒直達龍陽路站）。\n• 抵達龍陽路後，使用支付寶搜尋「途簡單」或「小鐵寄存」預約站內行李寄存。", "磁懸浮 8分鐘 / 車資 ¥40", "💡 記得保留紙本或電子登機證享磁浮優惠！", 1),
            (1, "15:30 - 18:30", "【黃金直行線】龍陽路 ➔ 雲南南路美食街 ➔ 金陵東路 ➔ 豫園華寶樓", "聽勸老字號 & 豫園華寶樓",
             "• 搭地鐵2號線由龍陽路至人民廣場站（約15分鐘），步行5分鐘達雲南南路美食街。\n• 美食推薦：阿寶炸豬排、小紹興白斬雞、大壺春生煎包。\n• 沿金陵東路騎樓步行10分鐘直達豫園華寶樓1F，購買爆紅「裕蓮茶樓 蔥香牛軋萬德福」。", "地鐵 2號線 / 步行", "💡 傍晚剛好能欣賞豫園仿古建築群璀璨亮燈！", 2),
            (1, "18:30 - 20:30", "聽勸夜景 2 選 1（極順接駁回龍陽路）", "聽勸夜景 2 選 1",
             "• 選項 A（最推薦）：步行至金陵東路渡口，花 2 元搭乘浦江輪渡至東昌路渡口，江風吹拂欣賞兩岸夜景，接著漫步陸家嘴搭2號線3站直達龍陽路！\n• 選項 B：豫園打車12分鐘至北外灘「白玉蘭廣場」人民咖啡館免費俯瞰高空夜景與東方明珠打卡。", "2元浦江輪渡 或 網約車", "💡 避開外灘核心人擠人觀景台，北外灘視野最乾淨！", 3),
            (1, "20:45 - 22:00", "【順方向下】龍陽路站取行李 ➔ 臨港冰雪明城酒店", "取行李 ➔ 前往臨港飯店",
             "• 選擇 1：搭乘地鐵 16 號線（龍陽路為起點站必有座，直達臨港大道站約45-55分鐘，票價約 8 RMB，末班車 22:30）。\n• 選擇 2：龍陽路直接叫滴滴打車直奔臨港（避開市區塞車，約45分鐘車程，約 130-150 RMB）。", "地鐵 16號線 或 滴滴打車", "💡 晚上入住臨港冰雪明城酒店，隔天走路即可到耀雪滑雪！", 4),

            # Day 2
            (2, "08:30 - 09:00", "「臨港冰雪明城酒店」退房與前台寄存大行李", "退房寄存",
             "• 早起辦理退房，將行李直接寄存於飯店前台，輕裝前往耀雪冰雪世界。", "步行 / 車程 3 分鐘", "💡 雪場離飯店極近。", 1),
            (2, "09:15 - 17:45", "「耀雪冰雪世界」世界級室內滑雪暢玩全日 ＆ 園區午餐", "極限冰雪全日",
             "• 現場領取租借專業雪服與雪鞋，暢玩超大室內滑雪坡道與冰雪娛雪區！\n• 中午於雪場主題餐廳享用午餐與熱飲。", "步行 / 打車", "💡 必備：請自備厚長襪與保暖防寒手套，門票已含雪服與雪靴。", 2),
            (2, "18:00 - 18:30", "返回臨港飯店領取行李 ➔ 出發前往迪士尼周邊", "取回行李",
             "• 滑雪結束後返回臨港冰雪明城酒店取回行李，準備轉移住宿陣地。", "步行 / 叫車", "💡 稍微更換乾爽衣物後出發。", 3),
            (2, "18:30 - 19:30", "抵達「上海漫庭酒店（國際旅遊度假區店）」Check-in", "飯店換會",
             "• 搭乘網約車直達迪士尼周邊飯店（車程約 40 分鐘），辦理連續兩晚入住。\n• 飯店提供隔天清晨迪士尼樂園免費接駁專車服務。", "網約車（約 110-130 RMB）", "💡 記得先向櫃檯預約隔天早晨前往迪士尼的接駁班次！", 4),
            (2, "19:30 - 21:00", "周浦特色美食晚餐 ＆ 早點休息儲備體力", "休養生息",
             "• 於飯店周邊品嚐在地小吃或叫外賣，早點梳洗就寢，為 Day 3 迪士尼全日大挑戰備戰！", "周邊步行", "💡 充足睡眠是暢玩迪士尼的最強武器。", 5),

            # Day 3
            (3, "07:30 - 08:30", "早起搭接駁車入園 ＆ 綁定上海迪士尼度假區 App", "早起入園",
             "• 搭乘漫庭飯店免費專車抵達上海迪士尼樂園。\n• 驗票入園第一時間打開 App 綁定門票，搶抽預約熱門項目尊享卡！", "飯店免費接駁專車", "💡 提早抵達安檢口排隊，第一批入園排隊時間至少省一半！", 1),
            (3, "08:30 - 12:00", "必衝 No.1：瘋狂動物城 (Zootopia) 熱力追蹤 ＆ 創極速光輪", "必衝熱門",
             "• 直奔全球首座「瘋狂動物城」體驗熱力追蹤，購買經典爪爪冰棒打卡拍照！\n• 前往明日世界挑戰地表最強雲霄飛車「創極速光輪 (TRON)」！", "樂園內部步行", "💡 爪爪棒棒糖拍照超吸睛，園區內拍照細節滿滿！", 2),
            (3, "13:30 - 17:30", "必衝 No.2：加勒比海盜 ＆ 米奇童話專列大巡遊 ＆ 礦山車", "經典體驗",
             "• 體驗光影視覺震撼無比的「加勒比海盜——沉落寶藏之戰」！\n• 欣賞米奇童話專列花車巡遊，搭乘七個小矮人礦山車。", "樂園內部", "💡 加勒比海盜是全球迪士尼中科技水準最高的項目之一，必看！", 3),
            (3, "20:00 - 21:00", "壓軸大秀：奇夢之光幻影秀（城堡璀璨光影煙火秀）", "壓軸大秀",
             "• 提前在奇幻童話城堡正前方尋找無遮擋視角，欣賞融合水幕、光雕與煙火的夢幻盛宴！\n• 散場後搭乘飯店接駁車返回漫庭酒店休息。", "接駁專車", "💡 建議提前 45 分鐘在奇想花園卡位。", 4),

            # Day 4
            (4, "09:30 - 10:30", "漫庭酒店退房 ➔ 攜帶行李搭車直奔靜安「宮宴」", "退房啟程",
             "• 辦理退房，攜帶行李搭網約車前往靜安區「宮宴（上海店）」（車程約 40 分鐘）。\n• 宮宴現場提供大件行李寄存服務，兩手空空用餐逛街超輕鬆。", "網約車（約 100-120 RMB）", "💡 也可以寄存在地鐵靜安寺站行李櫃。", 1),
            (4, "10:45 - 12:00", "關鍵前置！挑選漢服華服 ＆ 尊榮古風髮型妝造", "漢服換裝妝造",
             "• ⏰ 開宴前黃金關鍵（12:10 準時開宴）：\n• 宮宴規定開宴前需換裝完畢，挑選華服與髮型梳化約需 50-60 分鐘！\n• 強烈建議於 10:45-11:00 前抵達完成簽到與妝髮造型，在燈籠長廊大拍神仙古風照！", "抵達靜安區北京西路1485號", "💡 專業造型師打造精緻漢服髮型，儀式感拉滿！", 2),
            (4, "12:10 - 14:30", "【上海宮宴】一菜一演藝・宮廷御宴與國風歌舞沉浸盛宴", "華燈初上・宮廷盛宴",
             "• 沉浸式品嚐古代皇家宮廷御膳，欣賞絕美舞踏樂曲表演、行酒令與古典互動！\n• 餐後可自由穿著漢服在各場景盡情合影留念。", "宮宴盛宴廳", "💡 沉浸式體驗古代貴族開宴的尊榮禮儀。", 3),
            (4, "14:30 - 16:30", "換回便服 ➔ 打車至武康路梧桐區漫步（打卡武康大樓）", "市區質感漫步",
             "• 宮宴距離武康路僅約 3.5 公里（打車約 12 分鐘，車資約 18 RMB）。\n• 漫步於綠意盎然的梧桐樹下，打卡經典歷史地標「武康大樓」，走訪特色文藝小店。", "網約車 / 步行", "💡 感受最道地的上海海派慢節奏浪漫氛圍。", 4),
            (4, "16:30 - 18:00", "前往上海浦東國際機場 T2 辦理長榮 BR721 登機報到", "前往機場",
             "• 取回行李搭網約車直達浦東國際機場 T2 航廈（車程約 45-50 分鐘）。\n• 建議 18:00 前抵達（起飛前 2 小時）完成報到托運與出境安檢，逛免稅店採買伴手禮。", "網約車直達機場", "💡 國際航班務必預留足夠通關與安檢時間！", 5),
            (4, "20:05 - 22:00", "搭乘長榮航空 BR721 班機（立榮 B77017）圓滿返台", "圓滿返台",
             "• 回程航班：長榮 BR721 (20:05 浦東T2起飛 ➔ 22:00 抵達桃園T2)。\n• 帶著滿滿宮廷御宴、迪士尼歡樂與滑雪美好回憶圓滿結束精彩旅程！", "長榮航班", "💡 班機準時起飛，順利平安返抵台灣！", 6)
        ]
        cursor.executemany("""
            INSERT INTO itinerary (day, time_slot, title, tag, desc, transit, tip, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, default_itinerary)
        conn.commit()

    conn.close()

def get_setting(key, default=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 3. 頂部 Hero 總覽 (原生 Markdown + 原生 Container)
# ==========================================
st.title("✨ 上海 4 天 3 夜夢幻之旅")
st.caption("📅 9/20(日) - 9/23(三) ｜ 🏨 臨港明城 + 漫庭度假區店 ｜ ✈️ 春秋 9C8952 / 長榮 BR721")

# 原生航班資訊卡片
with st.expander("🛫 去程與回程航班詳細資訊 (點擊展開)", expanded=False):
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        with st.container(border=True):
            st.markdown("**✈️ 【去程】9/20 (週日) 春秋航空 9C8952**")
            st.write("桃園機場 T1 (11:15) ➔ 浦東機場 T2 (13:20)")
            st.caption("飛行時間約 2 小時 5 分")
    with f_col2:
        with st.container(border=True):
            st.markdown("**🛬 【回程】9/23 (週三) 長榮航空 BR721**")
            st.write("浦東機場 T2 (20:05) ➔ 桃園機場 T2 (22:00)")
            st.caption("飛行時間約 1 小時 55 分 (立榮聯營)")

# ==========================================
# 側邊欄：切換個人帳本與獨立預算設定
# ==========================================
conn = get_db()
cur = conn.cursor()
user_rows = [r[0] for r in cur.execute("SELECT name FROM users ORDER BY rowid ASC").fetchall()]
conn.close()
if not user_rows:
    user_rows = ["本人"]

# 維護當前選中成員狀態
if "active_user" not in st.session_state or st.session_state["active_user"] not in user_rows:
    st.session_state["active_user"] = user_rows[0]

st.sidebar.markdown("### 👤 個人帳本管理")
current_user = st.sidebar.selectbox(
    "切換當前帳本：",
    user_rows,
    index=user_rows.index(st.session_state["active_user"]),
    key="user_select_box"
)
st.session_state["active_user"] = current_user

with st.sidebar.expander("➕ 新增成員帳本"):
    with st.form("add_user_form", clear_on_submit=True):
        new_uname = st.text_input("成員名稱", placeholder="例如：伴侶 / 媽媽 / 小明")
        copy_template = st.checkbox("複製現有成員的消費明細作為初始範本", value=True)
        default_copy_src = "本人" if "本人" in user_rows else user_rows[0]
        copy_source = st.selectbox(
            "選擇複製來源成員：",
            user_rows,
            index=user_rows.index(default_copy_src) if default_copy_src in user_rows else 0,
            help="選擇要作為範本的成員，系統會將該成員的所有消費明細複製一份至新成員帳本"
        )
        submit_new_user = st.form_submit_button("新增帳本", type="secondary")
        if submit_new_user:
            uname_clean = new_uname.strip()
            if not uname_clean:
                st.sidebar.error("請輸入成員名稱！")
            elif uname_clean in user_rows:
                st.sidebar.warning(f"成員【{uname_clean}】已存在！")
            else:
                db = get_db()
                c = db.cursor()
                c.execute("INSERT OR IGNORE INTO users (name) VALUES (?)", (uname_clean,))
                
                copied_count = 0
                if copy_template and copy_source:
                    c.execute("""
                        INSERT INTO expenses (day, category, item_name, amount_twd, amount_rmb, payment_method, expense_date, notes, user_name)
                        SELECT day, category, item_name, amount_twd, amount_rmb, payment_method, expense_date, notes, ?
                        FROM expenses
                        WHERE user_name = ?
                    """, (uname_clean, copy_source))
                    copied_count = c.rowcount
                    
                    # 同步複製預算設定
                    src_budget = get_setting(f"total_budget_{copy_source}", get_setting("total_budget", "20100"))
                    set_setting(f"total_budget_{uname_clean}", src_budget)
                
                db.commit()
                db.close()
                
                # 自動切換到新成員帳本，並即時觸發重新整理
                st.session_state["active_user"] = uname_clean
                if copied_count > 0:
                    st.sidebar.success(f"已成功新增【{uname_clean}】並複製【{copy_source}】的 {copied_count} 筆消費明細！")
                else:
                    st.sidebar.success(f"已成功新增空白帳本【{uname_clean}】！")
                st.rerun()

st.sidebar.divider()
st.sidebar.markdown(f"### ⚙️ 【{current_user}】預算設定")
user_budget_key = f"total_budget_{current_user}"
saved_budget_str = get_setting(user_budget_key, get_setting("total_budget", "20100"))
try:
    current_budget_val = float(saved_budget_str)
except ValueError:
    current_budget_val = 20100.0

new_budget_input = st.sidebar.number_input(
    f"💰 【{current_user}】總預算 (TWD)",
    min_value=1000.0,
    step=500.0,
    value=current_budget_val,
    help=f"設定【{current_user}】的獨立預算上限，自動持久化儲存於 SQLite"
)

if new_budget_input != current_budget_val:
    set_setting(user_budget_key, str(new_budget_input))
    st.sidebar.success(f"已更新【{current_user}】總預算為 NT$ {new_budget_input:,.0f}")
    st.rerun()

st.sidebar.caption("💡 每個成員的消費與預算上限完全隔離儲存。")

# ==========================================
# 4. 畫面上方即時預算與累計支出看板 (圓餅圖與長條圖並列)
# ==========================================
conn = get_db()
# 依當前使用者隔離載入消費記錄
expenses_df = pd.read_sql_query(
    "SELECT * FROM expenses WHERE user_name = ? ORDER BY id DESC", 
    conn, 
    params=(current_user,)
)
budgets_df = pd.read_sql_query("SELECT * FROM budget_limits", conn)
conn.close()

# 總預算連動該成員側邊欄動態持久化數值
total_budget_twd = new_budget_input
total_spent_twd = expenses_df['amount_twd'].sum() if not expenses_df.empty else 0.0
total_spent_rmb = expenses_df['amount_rmb'].sum() if not expenses_df.empty else 0.0
remain_twd = total_budget_twd - total_spent_twd
spent_pct = (total_spent_twd / total_budget_twd * 100) if total_budget_twd > 0 else 0

with st.container(border=True):
    st.markdown(f"### 💳 【{current_user}】預算與累計支出即時看板")
    
    # 4 個原生 Metric 卡片 (動態連動個人總預算)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("🎯 總預算上限", f"NT$ {total_budget_twd:,.0f}")
    with m2:
        st.metric("💸 累計支出 (TWD)", f"NT$ {total_spent_twd:,.0f}", delta=f"{spent_pct:.1f}% 已使用", delta_color="off")
    with m3:
        st.metric("💴 累計支出 (RMB)", f"¥ {total_spent_rmb:,.1f}")
    with m4:
        st.metric("💰 剩餘預算餘額", f"NT$ {remain_twd:,.0f}", delta=f"剩餘 {100-spent_pct:.1f}%", delta_color="normal" if remain_twd >= 0 else "inverse")

    # 原生圖表區塊：圓餅圖 (Altair) 與 長條圖 並列呈現
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.caption(f"🥧 【{current_user}】各消費類別佔比圓餅圖")
        if not expenses_df.empty:
            cat_summary = expenses_df.groupby("category", as_index=False)["amount_twd"].sum()
            pie_chart = alt.Chart(cat_summary).mark_arc(innerRadius=42).encode(
                theta=alt.Theta(field="amount_twd", type="quantitative", title="支出金額 (TWD)"),
                color=alt.Color(field="category", type="nominal", title="類別", scale=alt.Scale(scheme="category10")),
                tooltip=[
                    alt.Tooltip("category:N", title="類別"),
                    alt.Tooltip("amount_twd:Q", title="金額 (TWD)", format=",.0f")
                ]
            ).properties(height=230)
            st.altair_chart(pie_chart, use_container_width=True)
        else:
            st.info(f"【{current_user}】目前尚無支出記錄，可在下方隨手記帳。")
            
    with chart_col2:
        st.caption(f"📊 【{current_user}】各類別預算目標與實支對比長條圖")
        if not budgets_df.empty:
            base_sum = budgets_df['budget_twd'].sum() or 20100.0
            scale_ratio = total_budget_twd / base_sum
            actual_map = expenses_df.groupby("category")["amount_twd"].sum().to_dict() if not expenses_df.empty else {}
            chart_data = []
            for _, row in budgets_df.iterrows():
                cat = row['category']
                b_val = round(row['budget_twd'] * scale_ratio, 0)
                a_val = actual_map.get(cat, 0.0)
                chart_data.append({"類別": cat, "預算目標": b_val, "實際支出": a_val})
            
            plot_df = pd.DataFrame(chart_data).set_index("類別")
            st.bar_chart(plot_df, height=230)

    # 隨手記帳面板 (自動標記當前成員)
    with st.expander(f"⚡ 為【{current_user}】動態新增消費記錄 (自動更新上方看板)", expanded=False):
        with st.form("top_quick_expense_form", clear_on_submit=True):
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            with f_col1:
                exp_date = st.date_input("消費日期", datetime.date(2026, 9, 20), key="quick_date")
                exp_day = st.selectbox("所屬天數", [1, 2, 3, 4, 0], format_func=lambda x: f"Day {x}" if x > 0 else "行前/通用", key="quick_day")
            with f_col2:
                exp_category = st.selectbox("支出類別", ["來回機票", "飯店住宿", "景點門票", "交通出行", "餐飲伴手", "其他購物"], key="quick_cat")
                exp_item = st.text_input("消費項目名稱", placeholder="例如：裕蓮茶樓蔥香牛軋餅", key="quick_item")
            with f_col3:
                curr_mode = st.radio("輸入幣別", ["人民幣 (RMB)", "新台幣 (TWD)"], horizontal=True, key="quick_curr")
                input_amount = st.number_input("輸入金額", min_value=0.0, step=10.0, value=50.0, key="quick_amt")
            with f_col4:
                exp_pay = st.selectbox("支付方式", ["微信支付", "支付寶", "信用卡", "現金"], key="quick_pay")
                exp_notes = st.text_input("備註說明", placeholder="可選填備註", key="quick_note")
                
            submit_quick = st.form_submit_button(f"記入【{current_user}】帳本並更新看板", type="primary")
            if submit_quick:
                if exp_item.strip():
                    EXCHANGE_RATE = 4.45
                    if "RMB" in curr_mode:
                        amt_rmb = float(input_amount)
                        amt_twd = round(amt_rmb * EXCHANGE_RATE, 1)
                    else:
                        amt_twd = float(input_amount)
                        amt_rmb = round(amt_twd / EXCHANGE_RATE, 1)
                    
                    db = get_db()
                    cur = db.cursor()
                    cur.execute("""
                        INSERT INTO expenses (day, category, item_name, amount_twd, amount_rmb, payment_method, expense_date, notes, user_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (exp_day, exp_category, exp_item, amt_twd, amt_rmb, exp_pay, str(exp_date), exp_notes, current_user))
                    db.commit()
                    db.close()
                    st.success(f"🎉 成功為【{current_user}】記下一筆！【{exp_item}】NT$ {amt_twd:,.0f} (¥ {amt_rmb})")
                    st.rerun()
                else:
                    st.error("請填寫項目名稱！")


# ==========================================
# 5. 主功能分頁導覽
# ==========================================
tabs = st.tabs([
    "📅 每日行程節點",
    "💰 消費明細與手動修改",
    "🛡️ 聽勸避坑指南",
    "🚇 交通轉乘樞紐",
    "🎒 行前必備清單"
])

# ----------------------------------------------------
# TAB 1: 每日行程節點 (原生 Container 渲染)
# ----------------------------------------------------
with tabs[0]:
    st.markdown("### 🗺️ 4 天 3 夜精準時間軸行程")
    
    day_select = st.radio(
        "選擇要檢視的日期：",
        [1, 2, 3, 4],
        format_func=lambda x: f"Day {x} (9/{19+x} " + ["週日", "週一", "週二", "週三"][x-1] + ")",
        horizontal=True,
        key="itinerary_radio"
    )
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM itinerary WHERE day = ? ORDER BY sort_order ASC, id ASC", (day_select,))
    day_nodes = c.fetchall()
    conn.close()
    
    for node in day_nodes:
        with st.container(border=True):
            st.markdown(f"**⏰ {node['time_slot']}** ｜ `{node['tag'] if node['tag'] else '精選行程'}`")
            st.markdown(f"#### {node['title']}")
            st.markdown(node['desc'])
            if node['transit']:
                st.info(f"🚇 **推薦交通：** {node['transit']}")
            if node['tip']:
                st.warning(f"{node['tip']}")

    with st.expander(f"➕ 為 Day {day_select} 新增行程節點"):
        with st.form(f"add_node_form_{day_select}", clear_on_submit=True):
            col_a, col_b = st.columns([1, 2])
            with col_a:
                new_time = st.text_input("時間區段 (如 14:00 - 15:30)", value="14:00 - 15:30")
                new_tag = st.text_input("行程標籤", value="打卡體驗")
                new_transit = st.text_input("推薦交通方式", value="地鐵出行")
            with col_b:
                new_title = st.text_input("行程名稱", placeholder="例如：靜安寺商圈逛街採買")
                new_desc = st.text_area("詳細行程說明", placeholder="輸入詳細動線或攻略細節...")
                new_tip = st.text_input("貼心建議或避坑提醒", placeholder="例如：提前領取優惠券...")
            
            submit_node = st.form_submit_button("儲存並加入行程", type="primary")
            if submit_node:
                if new_title.strip():
                    db = get_db()
                    cur = db.cursor()
                    cur.execute("SELECT MAX(sort_order) FROM itinerary WHERE day = ?", (day_select,))
                    max_order = cur.fetchone()[0] or 0
                    cur.execute("""
                        INSERT INTO itinerary (day, time_slot, title, tag, desc, transit, tip, sort_order)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (day_select, new_time, new_title, new_tag, new_desc, new_transit, new_tip, max_order + 1))
                    db.commit()
                    db.close()
                    st.success("✅ 行程已成功儲存至 SQLite！")
                    st.rerun()
                else:
                    st.error("請輸入行程名稱！")

    # --------------------------------------------
    # 行程下方互動式地圖 (標記核心座標點)
    # --------------------------------------------
    with st.container(border=True):
        st.markdown("#### 🗺️ 4 天 3 夜核心景點與樞紐互動地圖")
        st.caption("點擊標記點可查看詳細地點說明與行程亮點（支援平移與縮放）")

        # 建立 Folium 地圖物件，以浦東新區與市區中樞為預設中心點
        m = folium.Map(location=[31.13, 121.68], zoom_start=10, tiles="OpenStreetMap")

        # 定義核心座標點清單
        spots = [
            {
                "name": "浦東國際機場 T2",
                "coord": [31.14488, 121.81055],
                "popup": "✈️ 浦東國際機場 T2 (春秋航空去程 / 長榮航空回程起降)",
                "icon": "plane",
                "color": "blue"
            },
            {
                "name": "龍陽路站",
                "coord": [31.20371, 121.55776],
                "popup": "🧳 龍陽路地鐵站 (磁浮列車終點 / 行李寄存樞紐)",
                "icon": "suitcase",
                "color": "purple"
            },
            {
                "name": "耀雪冰雪世界",
                "coord": [30.89850, 121.92110],
                "popup": "🎿 耀雪冰雪世界 (Day 2 全日室內滑雪暢玩)",
                "icon": "snowflake",
                "color": "cadetblue"
            },
            {
                "name": "臨港冰雪明城酒店",
                "coord": [30.91730, 121.90677],
                "popup": "🏨 臨港冰雪明城酒店 (Day 1 入住 / 步行直達雪場)",
                "icon": "bed",
                "color": "darkblue"
            },
            {
                "name": "上海漫庭酒店 (國際旅遊度假區店)",
                "coord": [31.14569, 121.69030],
                "popup": "🏨 上海漫庭酒店 (Day 2-3 入住 / 迪士尼專車免費接送)",
                "icon": "home",
                "color": "orange"
            },
            {
                "name": "上海迪士尼樂園",
                "coord": [31.14151, 121.65796],
                "popup": "🏰 上海迪士尼樂園 (Day 3 全日瘋狂動物城與煙火秀)",
                "icon": "star",
                "color": "red"
            },
            {
                "name": "宮宴 (上海店)",
                "coord": [31.22693, 121.44772],
                "popup": "🍱 宮宴上海店 (Day 4 漢服妝造挑選與沉浸式宮廷盛宴)",
                "icon": "cutlery",
                "color": "green"
            },
            {
                "name": "武康大樓 (梧桐區)",
                "coord": [31.20443, 121.43828],
                "popup": "📸 武康大樓 (Day 4 海派浪漫梧桐區漫步巡禮)",
                "icon": "camera",
                "color": "pink"
            }
        ]

        for s in spots:
            folium.Marker(
                location=s["coord"],
                popup=folium.Popup(s["popup"], max_width=260),
                tooltip=s["name"],
                icon=folium.Icon(color=s["color"], icon=s["icon"], prefix="fa")
            ).add_to(m)

        # 引入 LocateControl 定位插件（左上角按鈕，點擊調用 GPS 並繪製目前位置藍點）
        LocateControl(
            auto_start=False,
            position="topleft",
            flyTo=True,
            keepCurrentZoomLevel=False,
            strings={"title": "定位目前所在位置", "popup": "您目前所在位置"},
            locateOptions={"enableHighAccuracy": True}
        ).add_to(m)

        # 嵌入 Streamlit 頁面中 (returned_objects=[] 避免地圖操作觸發全頁 rerun)
        st_folium(m, height=450, use_container_width=True, returned_objects=[])


# ----------------------------------------------------
# TAB 2: 消費明細與手動修改
# ----------------------------------------------------
with tabs[1]:
    st.markdown(f"### 📋 【{current_user}】歷史消費明細記錄與手動修改管理")
    
    if not expenses_df.empty:
        disp_df = expenses_df[['id', 'expense_date', 'day', 'category', 'item_name', 'amount_twd', 'amount_rmb', 'payment_method', 'notes']].copy()
        disp_df.columns = ['ID', '日期', '天數', '類別', '項目名稱', '新台幣 (TWD)', '人民幣 (RMB)', '支付方式', '備註']
        st.dataframe(disp_df, use_container_width=True, hide_index=True)
        
        st.markdown(f"##### ⚙️ 【{current_user}】記錄操作管理")
        op_tab1, op_tab2 = st.tabs(["✏️ 手動修改金額與記錄", "🗑️ 刪除記錄"])
        
        with op_tab1:
            edit_id = st.selectbox(
                f"選擇【{current_user}】要修改的消費記錄 (依 ID)：", 
                expenses_df['id'].tolist(),
                key="select_edit_box",
                format_func=lambda x: f"ID #{x} - {expenses_df[expenses_df['id']==x]['item_name'].values[0]} (NT$ {expenses_df[expenses_df['id']==x]['amount_twd'].values[0]:,.0f} / ¥ {expenses_df[expenses_df['id']==x]['amount_rmb'].values[0]:,.1f})"
            )
            
            cur_item = expenses_df[expenses_df['id'] == edit_id].iloc[0]
            
            with st.form(f"edit_form_{edit_id}"):
                e_col1, e_col2, e_col3 = st.columns(3)
                with e_col1:
                    new_item_name = st.text_input("項目名稱", value=str(cur_item['item_name']))
                    new_cat = st.selectbox(
                        "支出類別", 
                        ["來回機票", "飯店住宿", "景點門票", "交通出行", "餐飲伴手", "其他購物"],
                        index=["來回機票", "飯店住宿", "景點門票", "交通出行", "餐飲伴手", "其他購物"].index(cur_item['category']) if cur_item['category'] in ["來回機票", "飯店住宿", "景點門票", "交通出行", "餐飲伴手", "其他購物"] else 0
                    )
                    new_pay = st.selectbox(
                        "支付方式", 
                        ["微信支付", "支付寶", "信用卡", "現金"],
                        index=["微信支付", "支付寶", "信用卡", "現金"].index(cur_item['payment_method']) if cur_item['payment_method'] in ["微信支付", "支付寶", "信用卡", "現金"] else 0
                    )
                with e_col2:
                    new_amt_twd = st.number_input("新台幣金額 (TWD)", min_value=0.0, step=10.0, value=float(cur_item['amount_twd']))
                    new_amt_rmb = st.number_input("人民幣金額 (RMB)", min_value=0.0, step=5.0, value=float(cur_item['amount_rmb']))
                    auto_sync_rmb = st.checkbox("修改時依 1 RMB ≈ 4.45 TWD 自動同步換算人民幣", value=False)
                with e_col3:
                    try:
                        cur_date_obj = datetime.date.fromisoformat(str(cur_item['expense_date']))
                    except Exception:
                        cur_date_obj = datetime.date(2026, 9, 20)
                    new_date = st.date_input("消費日期", cur_date_obj)
                    new_day = st.selectbox(
                        "所屬天數", 
                        [1, 2, 3, 4, 0], 
                        index=[1, 2, 3, 4, 0].index(int(cur_item['day'])) if int(cur_item['day']) in [1, 2, 3, 4, 0] else 0,
                        format_func=lambda x: f"Day {x}" if x > 0 else "行前/通用"
                    )
                    new_notes = st.text_input("備註說明", value=str(cur_item['notes'] or ""))
                
                save_edit = st.form_submit_button("💾 儲存修改金額與記錄", type="primary")
                if save_edit:
                    final_twd = float(new_amt_twd)
                    if auto_sync_rmb:
                        final_rmb = round(final_twd / 4.45, 1)
                    else:
                        final_rmb = float(new_amt_rmb)
                    
                    db = get_db()
                    cur = db.cursor()
                    cur.execute("""
                        UPDATE expenses 
                        SET item_name = ?, category = ?, amount_twd = ?, amount_rmb = ?, payment_method = ?, expense_date = ?, day = ?, notes = ?
                        WHERE id = ?
                    """, (new_item_name, new_cat, final_twd, final_rmb, new_pay, str(new_date), new_day, new_notes, edit_id))
                    db.commit()
                    db.close()
                    st.success(f"✅ ID #{edit_id} 【{new_item_name}】金額已成功更新為 NT$ {final_twd:,.0f} (¥ {final_rmb:,.1f})！")
                    st.rerun()
                    
        with op_tab2:
            del_col1, del_col2 = st.columns([3, 1])
            with del_col1:
                del_id = st.selectbox(f"選擇【{current_user}】要刪除的支出記錄 (依 ID)：", expenses_df['id'].tolist(),
                                      format_func=lambda x: f"ID #{x} - {expenses_df[expenses_df['id']==x]['item_name'].values[0]} (NT$ {expenses_df[expenses_df['id']==x]['amount_twd'].values[0]:,.0f})")
            with del_col2:
                st.write("")
                st.write("")
                if st.button("🗑️ 確認刪除此筆記錄", type="secondary"):
                    db = get_db()
                    db.execute("DELETE FROM expenses WHERE id = ?", (del_id,))
                    db.commit()
                    db.close()
                    st.warning(f"已刪除 ID #{del_id} 支出記錄！")
                    st.rerun()
    else:
        st.info(f"【{current_user}】目前帳本尚無消費明細。可於畫面上方「隨手動態記帳」面板為該成員記入第一筆開銷！")


# ----------------------------------------------------
# TAB 3: 聽勸避坑指南 (原生 Container 渲染)
# ----------------------------------------------------
with tabs[2]:
    st.markdown("### 🛡️ 上海 5 大聽勸避坑平替攻略")
    
    traps = [
        {
            "num": "1",
            "title": "俯瞰上海全景與高空天際線",
            "trap": "❌ 不要盲目登東方明珠：排隊動輒 2 小時以上、旋轉餐廳與高空門票昂貴，且常有高額強制低消限制。",
            "advice": "💡 聽勸推薦平替：北外灘「白玉蘭廣場人民咖啡館」\n免費入場、無強制低消限制，輕鬆俯瞰浦江兩岸與東方明珠同框絕美視角！"
        },
        {
            "num": "2",
            "title": "黃浦江兩岸夢幻夜景巡禮",
            "trap": "❌ 不要花 50 元走「外灘觀光隧道」：票價偏貴，且內部視覺燈光特效老舊、毫無觀賞深度。",
            "advice": "💡 聽勸推薦平替：花 2 元搭乘「浦江輪渡」\n從金陵東路渡口刷 2 元搭到東昌路渡口，站在甲板上吹著涼爽江風，零死角欣賞兩岸金碧輝煌的燈光秀！"
        },
        {
            "num": "3",
            "title": "特色道地小吃與爆紅伴手禮",
            "trap": "❌ 避開豫園/城隍廟主街觀光小吃：觀光客高度集中、價格偏高且口味往往商業化易踩雷。",
            "advice": "💡 聽勸推薦平替：直奔「雲南南路美食街」與「裕蓮茶樓」\n1. 雲南南路聚集阿寶炸豬排、小紹興白斬雞等百年老字號，平價又道地！\n2. 豫園華寶樓 1F 裕蓮茶樓購買超人氣「蔥香牛軋萬德福」。"
        },
        {
            "num": "4",
            "title": "拍照打卡外灘東方明珠天際線",
            "trap": "❌ 避開外灘正核心觀景台人擠人：入夜後遊客人山人海，拍照背景全是人頭，寸步難行。",
            "advice": "💡 聽勸推薦平替：前往「北外灘親水平台」\n空間寬敞開闊、遊客相對稀少，能輕鬆以乾淨無遮擋的背景拍出陸家嘴三件套與東方明珠神級大片！"
        },
        {
            "num": "5",
            "title": "老街風情與海派慢步街區",
            "trap": "❌ 減少「田子坊」行程時間：商業化較為嚴重，店舖同質性過高。",
            "advice": "💡 聽勸推薦平替：漫步「武康路 / 安福路梧桐區」\n漫步於浪漫梧桐樹蔭下，打卡經典傳奇「武康大樓」，品嚐質感精品咖啡，感受最道地的海派慢生活。"
        }
    ]
    
    for item in traps:
        with st.container(border=True):
            st.markdown(f"#### {item['num']}. {item['title']}")
            c_trap, c_adv = st.columns(2)
            with c_trap:
                st.error(f"**🚫 不聽勸踩雷點**\n\n{item['trap']}")
            with c_adv:
                st.success(f"**✅ 聽勸平替神招**\n\n{item['advice']}")

# ----------------------------------------------------
# TAB 4: 交通轉乘樞紐 (原生 Table & Container)
# ----------------------------------------------------
with tabs[3]:
    st.markdown("### 🚇 交通導航樞紐與寄存攻略")
    
    t_c1, t_c2 = st.columns(2)
    with t_c1:
        with st.container(border=True):
            st.markdown("#### 🧳 核心樞紐：龍陽路站寄存秘訣")
            st.write("• **磁浮列車直達：** 浦東機場 T2 搭乘磁浮，7分20秒直達龍陽路，出示機票僅 40 RMB。")
            st.write("• **省時 2 小時：** 大行李寄存龍陽路（支付寶搜尋「途簡單」或「小鐵寄存」），輕裝逛豫園外灘。")
            st.write("• **順方向下臨港：** 取行李後搭 16 號線直達臨港（龍陽路為起點站必有座），避開市區塞車！")
    with t_c2:
        with st.container(border=True):
            st.markdown("#### 🚕 路線車資估算參考表")
            st.write("• **浦東機場 ➔ 龍陽路：** 磁浮 40 RMB / 滴滴約 80-100 RMB")
            st.write("• **龍陽路 ➔ 豫園站：** 地鐵 2號線轉10號線 (約18分鐘，車資 4 RMB)")
            st.write("• **豫園 ➔ 金陵東路渡口：** 步行約 10 分鐘，浦江輪渡 2 RMB")
            st.write("• **龍陽路 ➔ 臨港明城：** 地鐵 16 號線 (約 50 分鐘，車資 8 RMB) / 滴滴約 130 RMB")
            st.write("• **靜安宮宴 ➔ 武康大樓：** 滴滴打車約 18 RMB (約 12 分鐘)")
    
    st.markdown("#### 📍 核心景點標準中文地址（供叫車或高德貼上）")
    addresses = [
        ("臨港冰雪明城酒店 (耀雪店)", "上海市浦東新區自由貿易試驗區臨港新片區杞青路888弄1-3號"),
        ("上海漫庭酒店 (國際旅遊度假區店)", "上海市浦東新區陳橋村957號"),
        ("裕蓮茶樓 (豫園華寶樓店)", "上海市黃浦區方浜中路265號華寶樓1樓"),
        ("宮宴 (上海店・沉浸式漢服御宴)", "上海市靜安區北京西路1485號一幢1-2層 (近地鐵靜安寺站)"),
        ("武康大樓 (梧桐區)", "上海市徐匯區淮海中路1850號")
    ]
    st.table(pd.DataFrame(addresses, columns=["地標名稱", "中文詳細地址"]))

# ----------------------------------------------------
# TAB 5: 行前必備清單 (原生 Checkbox)
# ----------------------------------------------------
with tabs[4]:
    st.markdown("### 🎒 出發前必備 App 與證件核對清單")
    st.caption("勾選狀態將自動同步儲存至 SQLite 資料庫，關閉網頁絕不遺失！")
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM checklist ORDER BY id ASC")
    items = c.fetchall()
    conn.close()
    
    for item in items:
        checked = bool(item['is_checked'])
        new_val = st.checkbox(item['item_name'], value=checked, key=f"chk_{item['id']}")
        if new_val != checked:
            db = get_db()
            db.execute("UPDATE checklist SET is_checked = ? WHERE id = ?", (1 if new_val else 0, item['id']))
            db.commit()
            db.close()
            st.rerun()

st.divider()
st.caption("上海 4 天 3 夜夢幻之旅 ｜ SQLite travel.db 即時驅動 ｜ 響應式 Mobile Friendly 原生架構")
