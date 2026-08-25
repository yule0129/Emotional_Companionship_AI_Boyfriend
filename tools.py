from datetime import datetime
import os
import re

import requests
from langchain_core.tools import tool


@tool
def get_weather(city: str):
    """
    获取城市天气信息，用来提供给AI男友在聊天中关心对方，例如提醒穿搭、出行等。
    Args:
        city (str): 城市中文名称
    """
    HEFENG_WEATHER_API_KEY = os.getenv("HEFENG_WEATHER_API_KEY")
    QWEATHER_API_HOST = os.getenv("QWEATHER_API_HOST", "devapi.qweather.com").replace("https://", "").replace("http://", "").strip("/")

    if not HEFENG_WEATHER_API_KEY:
        return "未配置和风天气API Key，请在.env文件中配置HEFENG_WEATHER_API_KEY。"

    headers = {"X-QW-Api-Key": HEFENG_WEATHER_API_KEY}
    geo_url = f"https://{QWEATHER_API_HOST}/geo/v2/city/lookup"
    try:
        geo_resp = requests.get(
            geo_url,
            params={"location": city, "range": "cn", "number": 1},
            headers=headers,
            timeout=10,
        )
        geo_res = geo_resp.json()
    except requests.RequestException:
        return f"{city}天气接口连接失败"
    except ValueError:
        return "天气接口没有返回有效数据，请检查.env里的QWEATHER_API_HOST是否是和风天气控制台提供的专属API Host。"

    if geo_res.get("code") != "200" or len(geo_res.get("location", [])) == 0:
        if geo_res.get("error", {}).get("title") == "Invalid Host":
            return "和风天气API Host无效，请在.env里添加QWEATHER_API_HOST，值填和风天气控制台显示的专属API Host。"
        if geo_res.get("error"):
            return f"天气接口请求失败：{geo_res['error'].get('title', '未知错误')}"
        return f"无法识别「{city}」，暂未查到该城市天气"

    location_id = geo_res["location"][0]["id"]
    weather_url = f"https://{QWEATHER_API_HOST}/v7/weather/3d"
    try:
        weather_resp = requests.get(
            weather_url,
            params={"location": location_id},
            headers=headers,
            timeout=10,
        )
        weather_res = weather_resp.json()
    except requests.RequestException:
        return f"{city}天气接口连接失败"
    except ValueError:
        return "天气接口没有返回有效数据，请检查.env里的QWEATHER_API_HOST是否是和风天气控制台提供的专属API Host。"

    if weather_res.get("code") != "200":
        if weather_res.get("error", {}).get("title") == "Invalid Host":
            return "和风天气API Host无效，请在.env里添加QWEATHER_API_HOST，值填和风天气控制台显示的专属API Host。"
        if weather_res.get("error"):
            return f"天气接口请求失败：{weather_res['error'].get('title', '未知错误')}"
        return f"{city}天气接口请求失败"

    today = weather_res["daily"][0]
    return f"{city}今日{today['textDay']}，气温{today['tempMin']}~{today['tempMax']}℃"


def extract_weather_city(user_input: str):
    weather_words = ["天气", "气温", "温度", "下雨", "降雨", "穿什么", "出门"]
    if not any(word in user_input for word in weather_words):
        return None

    match = re.search(r"([\u4e00-\u9fff]{2,10})(?:今天|明天|后天|最近|这几天)?(?:的)?(?:天气|气温|温度|下雨|降雨)", user_input)
    if match:
        return match.group(1)

    city = user_input
    for word in ["今天", "明天", "后天", "最近", "这几天", "天气", "气温", "温度", "下雨", "降雨", "怎么样", "如何", "吗", "？", "?"]:
        city = city.replace(word, "")
    city = city.strip(" ，,。")
    return city or None


def get_time_context():
    now = datetime.now()
    hour = now.hour
    week_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
    week = week_map[now.weekday()]

    if 5 <= hour < 12:
        period = "早上"
        advice = "可以自然提到早起、早餐、出门节奏，语气克制但带一点照看。"
    elif 12 <= hour < 14:
        period = "中午"
        advice = "可以自然提到吃饭、午休、别硬撑。"
    elif 14 <= hour < 18:
        period = "下午"
        advice = "可以自然提到下午容易疲惫，提醒喝水或放慢一点。"
    elif 18 <= hour < 22:
        period = "晚上"
        advice = "可以自然提到晚饭、收尾、回家和休息。"
    else:
        period = "深夜"
        advice = "可以自然提醒别熬太狠、该睡就睡，语气不要说教。"

    time_format = now.strftime("%Y年%m月%d日 %H:%M")
    return (
        f"当前本机时间：{time_format} {week}，所处时段：{period}。"
        f"{advice} 不要每次都直接报出具体时间，除非用户问时间。"
    )
