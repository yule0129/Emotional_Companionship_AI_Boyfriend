from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config import llm
from memory_system import extract_and_save_memory, load_all_memory, save_last_visit_time
from prompts import system_prompt
from rag import search_context
from tools import extract_weather_city, get_time_context, get_weather


ROOT = Path(__file__).parent
app = FastAPI(title="陪伴 AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    meta: dict[str, Any] = Field(default_factory=dict)


def should_use_rag(text: str) -> bool:
    topics = ("数据结构", "算法", "复杂度", "递归", "排序", "数组", "链表", "栈", "队列", "树", "堆", "哈希", "动态规划", "贪心", "bfs", "dfs")
    intents = ("是什么", "怎么", "如何", "区别", "原理", "实现", "分析", "总结", "复习", "举例", "题目", "练习", "讲解", "面试")
    study = ("学习", "掌握", "理解", "入门", "提升", "刷题", "复习", "总结", "面试", "考试", "作业")
    lowered = text.lower()
    return bool(text.strip()) and (any(k.lower() in lowered for k in topics) or (any(k in text for k in intents) and any(k in text for k in study)))


def build_messages(req: ChatRequest):
    messages = [SystemMessage(content=system_prompt)]
    history = req.history[-10:]
    if history and history[-1].get("role") == "user" and history[-1].get("content", "").strip() == req.message.strip():
        history = history[:-1]
    for item in history:
        if item.get("role") == "user":
            messages.append(HumanMessage(content=item.get("content", "")))
        elif item.get("role") == "assistant":
            messages.append(AIMessage(content=item.get("content", "")))
    messages.append(HumanMessage(content=req.message))
    messages.append(SystemMessage(content=f"长期记忆信息：{load_all_memory()}"))
    messages.append(SystemMessage(content=f"时间感知信息：{get_time_context()}"))
    if should_use_rag(req.message):
        try:
            context = search_context(req.message, top_k=3)
            if context:
                messages.append(SystemMessage(content=f"RAG知识上下文：\n{context}"))
        except Exception as exc:
            print(f"RAG 暂时不可用，继续普通聊天：{exc}")
    return messages


@app.get("/api/health")
def health():
    return {"ok": True, "time": datetime.now().isoformat(timespec="seconds")}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=422, detail="消息不能为空")
    try:
        weather_city = extract_weather_city(text)
        messages = build_messages(req)
        if weather_city:
            weather_result = get_weather.invoke({"city": weather_city})
            messages.append(HumanMessage(content=f"天气查询结果：{weather_result}\n请根据这个结果回答用户刚才的天气问题。"))
        result = llm.invoke(messages)
        reply = result.content if hasattr(result, "content") else str(result)
        background_tasks.add_task(extract_and_save_memory, text)
        return ChatResponse(reply=reply, meta={"weather": weather_city or None, "rag": should_use_rag(text)})
    except Exception as exc:
        message = str(exc)
        if "Connection error" in message:
            detail = "模型服务连接失败。请检查网络或代理后重试；网页与本地后端已经连接正常。"
        elif "401" in message or "authentication" in message.lower():
            detail = "模型密钥验证失败，请检查 .env 中的 DEEPSEEK_API_KEY。"
        else:
            detail = f"模型回复失败：{message}"
        raise HTTPException(status_code=502, detail=detail) from exc


@app.post("/api/session/close")
def close_session():
    save_last_visit_time()
    return {"ok": True}


@app.get("/{path:path}")
def frontend(path: str):
    target = ROOT / "frontend" / (path or "index.html")
    if target.is_file() and ROOT / "frontend" in target.parents:
        return FileResponse(target)
    return FileResponse(ROOT / "frontend" / "index.html")
