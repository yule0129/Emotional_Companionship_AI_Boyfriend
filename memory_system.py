from datetime import datetime
import json
import sqlite3

from config import llm
from prompts import extract_template


conn = sqlite3.connect("long_term_memory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS long_term_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT DEFAULT "",
        city TEXT DEFAULT "",
        birthday TEXT DEFAULT "",
        preferences TEXT DEFAULT "",
        schedule TEXT DEFAULT "",
        other TEXT DEFAULT "",
        create_time TEXT DEFAULT "",
        first_chat_time TEXT DEFAULT "",
        your_name TEXT DEFAULT ""
    )
    """
)
conn.commit()

MEMORY_ID = 1
COMPLAINT_THRESHOLD_DAYS = 3
FIRST_CHAT_TIME = "2026-07-20 00:00:00"
YOUR_NAME = "小白"

cursor.execute("PRAGMA table_info(long_term_memory)")
columns = {row[1] for row in cursor.fetchall()}
if "first_chat_time" not in columns:
    cursor.execute("ALTER TABLE long_term_memory ADD COLUMN first_chat_time TEXT DEFAULT ''")
if "your_name" not in columns:
    cursor.execute("ALTER TABLE long_term_memory ADD COLUMN your_name TEXT DEFAULT ''")
conn.commit()


def extract_and_save_memory(round_content: str):
    prompt = extract_template.format(round_content=round_content)

    try:
        res = llm.invoke(prompt)
        profile = json.loads(res.content.strip())
        if not isinstance(profile, dict):
            profile = {}
    except json.JSONDecodeError:
        print("JSON解析错误，无法提取长期信息。")
        profile = {}
    except Exception as exc:
        print(f"长期记忆写入失败：{exc}")
        profile = {}

    name = profile.get("name", "")
    city = profile.get("city", "")
    birthday = profile.get("birthday", "")
    preferences = profile.get("preferences", profile.get("hobbies", ""))
    schedule = profile.get("schedule", "")
    other = profile.get("other", "")
    your_name = profile.get("your_name", "")

    cursor.execute(
        "SELECT name, city, birthday, preferences, schedule, other, first_chat_time ,your_name FROM long_term_memory WHERE id = ?",
        (MEMORY_ID,),
    )
    old_memory = cursor.fetchone()

    if old_memory:
        old_name, old_city, old_birthday, old_preferences, old_schedule, old_other, old_first_chat_time, old_your_name = old_memory
        name = name or old_name
        city = city or old_city
        birthday = birthday or old_birthday
        preferences = preferences or old_preferences
        schedule = schedule or old_schedule
        other = other or old_other
        first_chat_time = old_first_chat_time or FIRST_CHAT_TIME
        your_name = your_name or old_your_name or YOUR_NAME
        cursor.execute(
            """
            UPDATE long_term_memory
            SET name = ?, city = ?, birthday = ?, preferences = ?, schedule = ?, other = ?, first_chat_time = ?, your_name = ?
            WHERE id = ?
            """,
            (name, city, birthday, preferences, schedule, other, first_chat_time, your_name, MEMORY_ID),
        )
    else:
        first_chat_time = FIRST_CHAT_TIME
        your_name = your_name or YOUR_NAME
        cursor.execute(
            """
            INSERT INTO long_term_memory (id, name, city, birthday, preferences, schedule, other, first_chat_time, your_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (MEMORY_ID, name, city, birthday, preferences, schedule, other, first_chat_time, your_name),
        )

    conn.commit()


def save_last_visit_time():
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE long_term_memory SET create_time = ? WHERE id = ?",
        (now_time, MEMORY_ID),
    )
    conn.commit()


def load_all_memory() -> str:
    cursor.execute(
        "SELECT name,city,birthday,preferences,schedule,other,create_time,first_chat_time,your_name FROM long_term_memory WHERE id = ?",
        (MEMORY_ID,),
    )
    rows = cursor.fetchall()
    if not rows:
        return "无长期记忆信息。"

    memory_texts = []
    for row in rows:
        name, city, birthday, preferences, schedule, other, create_time, first_chat_time, your_name = row
        if not create_time:
            contact_status = "最近联系时间：未记录。"
        else:
            try:
                last_time = datetime.strptime(create_time, "%Y-%m-%d %H:%M:%S")
                gap_days = (datetime.now() - last_time).days
                if gap_days >= COMPLAINT_THRESHOLD_DAYS:
                    complaint = "太久没来了，自己说吧，忙到把我忘了？"
                else:
                    complaint = "刚见过，语气可以自然一点。"
                contact_status = f"最近联系时间：{create_time}，距离上次联系约 {gap_days} 天。{complaint}"
            except ValueError:
                contact_status = f"最近联系时间：{create_time}。"

        memory_texts.append(
            f"姓名: {name}, 常住城市: {city}, 生日: {birthday}, 偏好: {preferences}, 作息习惯: {schedule}, 其他长期偏好: {other}, 首次聊天时间：{first_chat_time or FIRST_CHAT_TIME}, AI自己的名字：{your_name or YOUR_NAME}, {contact_status}"
        )
    return "\n".join(memory_texts)
