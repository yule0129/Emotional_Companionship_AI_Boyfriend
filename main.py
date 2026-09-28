import sys
import time

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config import llm
from rag import search_context
from memory_system import extract_and_save_memory, load_all_memory, save_last_visit_time
from prompts import system_prompt
from tools import extract_weather_city, get_time_context, get_weather


tools = [get_weather]

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=system_prompt,
)


def typewriter_print(text: str, prefix: str = "他：", delay: float = 0.04):
    sys.stdout.write(prefix)
    sys.stdout.flush()
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def stream_agent_reply(messages, delay: float = 0.04):
    sys.stdout.write("他：")
    sys.stdout.flush()
    final_text = []
    for chunk, _ in agent.stream({"messages": messages}, stream_mode="messages"):
        content = getattr(chunk, "content", "")
        if content:
            final_text.append(content)
            for char in content:
                sys.stdout.write(char)
                sys.stdout.flush()
                if delay:
                    time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return "".join(final_text)

def should_use_rag(user_input:str)->bool:
    text = user_input.strip()
    if not text:
        return False

    topic_keywords = [
        "数据结构",
        "算法",
        "复杂度",
        "时间复杂度",
        "空间复杂度",
        "递归",
        "排序",
        "数组",
        "链表",
        "栈",
        "队列",
        "树",
        "二叉树",
        "堆",
        "哈希表",
        "图",
        "动态规划",
        "贪心",
        "bfs",
        "dfs",
    ]
    intent_keywords = [
        "是什么",
        "怎么",
        "如何",
        "区别",
        "原理",
        "实现",
        "分析",
        "总结",
        "复习",
        "举例",
        "题目",
        "练习",
        "讲解",
        "面试",
        "考点",
        "笔记",
        "教程",
    ]

    lowered = text.lower()
    if any(keyword in lowered for keyword in [k.lower() for k in topic_keywords]):
        return True

    if not any(keyword in text for keyword in intent_keywords):
        return False

    study_context_keywords = [
        "学习",
        "掌握",
        "理解",
        "入门",
        "提升",
        "刷题",
        "复习",
        "总结",
        "面试",
        "考试",
        "作业",
        "题",
    ]
    return any(keyword in text for keyword in study_context_keywords)


def build_rag_prompt(user_input: str) -> SystemMessage | None:
    if not should_use_rag(user_input):
        return None

    if len(user_input.strip()) < 2:
        return None

    context = search_context(user_input, top_k=3)
    if not context:
        return None

    return SystemMessage(content=f"RAG知识上下文：\n{context}")



chat_history = [
    SystemMessage(content=system_prompt)
]
MAX_HISTORY_LENGTH = 10


#-----------------------------------------------------------------------



print("你可以开始和他聊天了，输入 'exit' 或 'quit' 来结束对话。")
while True:

    try:
        user_input = input("你:")
    except EOFError:
        print("他：先到这。")
        break

    print("\n")

    if user_input.lower() in ["exit", "quit"]:
        save_last_visit_time()
        print("他：再见了，别忘了照顾好自己。")
        break

    chat_history.append(HumanMessage(content=user_input))
    extract_and_save_memory(user_input)

    fallback_city = extract_weather_city(user_input)
    memory_context = load_all_memory()
    rag_prompt = build_rag_prompt(user_input)
    current_time_context = SystemMessage(
        content=f"时间感知信息：{get_time_context()}"
    )
    memory_prompt = SystemMessage(
        content=f"长期记忆信息：{memory_context}"
    )

    if fallback_city:
        tool_response = get_weather.invoke({"city": fallback_city})
        weather_prompt = HumanMessage(
            content=f"天气查询结果：{tool_response}\n请根据这个结果，回答用户刚才的天气问题。"
        )
        prompt_messages = chat_history + [memory_prompt, current_time_context, weather_prompt]
        if rag_prompt:
            prompt_messages.insert(-1, rag_prompt)
        final_reply_text = stream_agent_reply(prompt_messages)
        final_reply = AIMessage(content=final_reply_text)
        chat_history.append(final_reply)
    else:
        prompt_messages = chat_history + [memory_prompt, current_time_context]
        if rag_prompt:
            prompt_messages.append(rag_prompt)
        final_reply_text = stream_agent_reply(prompt_messages)
        final_reply = AIMessage(content=final_reply_text)
        chat_history.append(final_reply)

    print("\n")

    if len(chat_history) > 1 + MAX_HISTORY_LENGTH * 2:
        chat_history = [chat_history[0]] + chat_history[-MAX_HISTORY_LENGTH * 2:]
