# LangChain 情绪陪伴 AI 项目完整解析

本文说明这个项目中 Prompt、Tool、Agent、Memory、RAG 等模块的职责、调用关系和一次对话的完整流程。

## 1. 项目定位与总体架构

这是一个 AI 陪伴应用，提供命令行和 Web 两种入口：使用 DeepSeek 作为聊天模型，用 LangChain 组织 Agent；用 SQLite 保存用户长期信息；用 Milvus 加载本地知识库；用和风天气 API 提供实时天气。Web 层由 FastAPI 提供接口，前端是无需构建步骤的静态 HTML。

| 模块 | 主要职责 | 文件 |
|---|---|---|
| 模型配置 | 读取环境变量，初始化 DeepSeek | config.py |
| Prompt | 规定人设、语气、工具规则、记忆提取格式 | prompts.py |
| Tool | 连接天气等外部服务 | tools.py |
| Memory | 提取、保存、读取用户长期信息 | memory_system.py |
| RAG | 文档切分、向量化、相似度检索 | rag.py |
| 编排 | 串联输入、记忆、RAG、工具和输出 | main.py |
| Web API | 为浏览器提供聊天和健康检查接口 | api_server.py |
| Web UI | 提供陪伴式聊天界面 | frontend/index.html |

整体数据流：

    用户输入
       ├─ 加入短期聊天历史
       ├─ LLM 抽取长期记忆 → SQLite
       ├─ 判断天气 → 和风天气 API
       ├─ 判断学习问题 → Embedding → Milvus
       ├─ 注入长期记忆和时间信息
       └─ LangChain Agent → DeepSeek → 流式输出

## 2. 文件职责

- main.py：程序入口、命令行循环、消息组装、流式回复。
- api_server.py：FastAPI Web 服务入口，调用现有模型、记忆、天气和 RAG 模块。
- frontend/index.html：单页聊天界面，通过 `/api/chat` 与 Web API 通信。
- PROJECT_GUIDE.md：项目架构、模块职责和数据流说明。
- config.py：读取 .env，初始化聊天模型。
- prompts.py：定义 system_prompt 和记忆抽取模板。
- tools.py：天气 Tool、城市识别和时间上下文。
- memory_system.py：SQLite 建表、记忆抽取、合并和读取。
- rag.py：知识文件切分、Embedding、Milvus 建库和搜索。
- knowledge/数据结构学习.md：当前 RAG 实际使用的知识文件。
- knowledge/数学建模模型.txt：文件存在，但目前没有接入 rag.py。
- long_term_memory.db：运行后保存长期记忆。

## 3. config.py：模型层

代码使用 init_chat_model 初始化 DeepSeek：

    llm = init_chat_model(
        model="deepseek-v4-flash",
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.65,
        streaming=True,
    )

load_dotenv(override=True) 会读取 .env。主要变量有：

- DEEPSEEK_API_KEY：聊天模型密钥。
- DEEPSEEK_BASE_URL：兼容 OpenAI 接口的地址。
- SILICONFLOW_API_KEY、SILICONFLOW_BASE_URL：Embedding 服务配置。
- HEFENG_WEATHER_API_KEY：和风天气密钥。
- QWEATHER_API_HOST：和风天气专属 Host。

temperature=0.65 控制输出随机性。streaming=True 允许模型逐块返回内容，main.py 再把内容实时打印出来。

同一个 llm 被两处使用：正常聊天，以及把一轮用户输入提取成长期记忆 JSON。

## 4. prompts.py：Prompt 逻辑

### 4.1 system_prompt

system_prompt 是最高层的行为说明，决定模型“是谁、如何说话、应该遵守什么规则”。当前规则包括：

1. AI 是细腻、温柔、共情力强的长期聊天伙伴。
2. 先理解用户情绪，再回答表面问题。
3. 使用自然口语，少说教、少机械套话。
4. 自然使用历史对话和长期记忆。
5. 说明自己是虚拟男友，只能提供精神和情绪陪伴。
6. 遇到天气、温度、下雨、穿衣、出行问题时调用 get_weather。
7. 用户很久没联系时，可以先轻微抱怨。

在 LangChain 消息体系中，SystemMessage 表示系统规则，HumanMessage 表示用户，AIMessage 表示模型回答。

### 4.2 extract_template

extract_template 是另一条 Prompt，不负责回复用户，而是让 LLM 从当前输入中抽取长期稳定信息，并严格输出固定 JSON：

    {
      "name": "",
      "city": "",
      "preferences": "",
      "schedule": "",
      "other": "",
      "your_name": ""
    }

例如“我住在上海”“我喜欢跑步”适合记住；“我今天有点累”通常只是一次性事件。

Prompt 只是软约束，模型可能输出非法 JSON 或错误分类，所以 memory_system.py 仍然做 JSON 解析异常处理和字段兜底。

## 5. tools.py：Tool 逻辑

### 5.1 @tool 和 Agent

get_weather 函数通过 @tool 装饰器变成 LangChain Tool。函数名、参数类型和文档字符串会作为工具描述提供给模型。

main.py 中：

    tools = [get_weather]
    agent = create_agent(model=llm, tools=tools, system_prompt=system_prompt)

因此 Agent 有能力在需要时调用天气工具，再根据结果生成最终答案。

### 5.2 天气 API 流程

get_weather 分两步请求和风天气：

1. 调用 geo/v2/city/lookup，把中文城市换成 location_id。
2. 调用 v7/weather/3d，根据 location_id 查询天气。
3. 取 daily[0]，返回城市、天气现象和最低/最高温。

它会处理缺少 Key、网络失败、非法 Host、无效 JSON、无法识别城市和接口错误码。

### 5.3 城市识别

extract_weather_city 是应用层规则解析器，不是模型 Tool。它先检查天气关键词，再用正则或字符串清理提取城市。

优点是速度快、不消耗模型调用；缺点是难以处理“我这里”“家附近”这类依赖上下文的表达。

### 5.4 时间上下文

get_time_context 根据本机小时生成早上、中午、下午、晚上或深夜的提示，让模型自然提到早餐、午休、喝水、回家或休息，而不是每次机械报出具体时间。

## 6. memory_system.py：长期记忆

### 6.1 SQLite 数据

表 long_term_memory 包含：

| 字段 | 含义 |
|---|---|
| name | 用户姓名 |
| city | 常住城市 |
| birthday | 生日 |
| preferences | 偏好 |
| schedule | 作息 |
| other | 其他长期信息 |
| create_time | 最近联系时间 |
| first_chat_time | 首次聊天时间 |
| your_name | AI 的名字 |

MEMORY_ID=1 表示当前程序只维护一条用户记录，属于单用户设计。

### 6.2 建表与迁移

模块导入时创建数据库表，并用 PRAGMA table_info 检查旧表是否缺少 first_chat_time 或 your_name；缺少时用 ALTER TABLE 补列。

### 6.3 记忆提取和合并

每次用户输入后调用 extract_and_save_memory：

1. 把输入填入 extract_template。
2. 调用 LLM。
3. 解析 JSON。
4. 查询旧记录。
5. 新值非空就覆盖，空值保留旧值。
6. 执行 INSERT 或 UPDATE。

这是一种“非空覆盖”策略，能避免用户本轮未提及姓名时把旧姓名清空。

### 6.4 联系时间

save_last_visit_time 只在用户输入 exit 或 quit 时更新 create_time。load_all_memory 计算距上次联系的天数：

- 少于 3 天：提示语气自然。
- 至少 3 天：生成“太久没来”的轻微抱怨提示。

因此程序异常关闭时，最近联系时间可能不会更新。

### 6.5 记忆注入

load_all_memory 将数据库字段拼成自然语言，main.py 再包装成一条 SystemMessage 传给模型。这是显式记忆注入：模型不直接查数据库，应用先读取再注入。

## 7. rag.py：RAG 逻辑

RAG 是 Retrieval-Augmented Generation，即检索增强生成。它不是重新训练模型，而是回答前从外部资料检索相关片段，再让模型基于这些片段回答。

当前 FILE_PATH 固定为 knowledge/数据结构学习.md，数学建模模型.txt 没有接入。

### 7.1 文档切分

build_chunks 的步骤：

1. 检查文件。
2. 用 UnstructuredMarkdownLoader 加载。
3. 用 MarkdownHeaderTextSplitter 按 # 和 ## 标题切分。
4. 用 RecursiveCharacterTextSplitter 继续细分。
5. chunk_size=2000，chunk_overlap=200。

标题切分保留章节结构，重叠区域减少知识在边界处丢失。

### 7.2 Embedding

项目通过 OpenAIEmbeddings 调用 SiliconFlow 上的 BAAI/bge-m3。Embedding 把文本转换为 1024 维向量，语义相似的文本在向量空间中更接近。

- DeepSeek：理解、决策、生成。
- BGE-M3：把文档和用户查询向量化。

### 7.3 Milvus

程序连接 http://localhost:19530，使用 data_structures 数据库和 data_structures_collection 集合，距离度量为 COSINE。

每条记录包含 id、vector、text、source 和 chunk_id。

### 7.4 建立索引

build_index 会删除同名旧集合，重新创建集合，切分文档，生成所有向量，再通过 upsert 写入 Milvus。这是重建式索引，适合学习项目，不适合频繁更新的大型知识库。

### 7.5 检索

search_context(query, top_k=3) 会：

1. 空查询直接返回。
2. 集合不存在时自动建库。
3. 用 embed_query 将问题向量化。
4. 从 Milvus 取最相似的 3 个 chunk。
5. 拼接成带 [1]、[2]、[3] 的文本。

当前没有相似度阈值，低相关结果也可能被注入上下文。

## 8. main.py：一轮请求如何执行

### 8.1 Agent

create_agent 接收 llm、get_weather 和 system_prompt。Agent 可以在模型和工具之间循环：模型提出工具调用，工具执行，模型读取工具结果后生成回答。

### 8.2 短期聊天历史

chat_history 初始放入系统消息。每轮追加 HumanMessage 和 AIMessage。超过 MAX_HISTORY_LENGTH=10 后，保留系统消息和最近 10 轮。

短期历史只存在内存，程序关闭后消失；长期稳定信息由 SQLite 保存。

### 8.3 RAG 路由

should_use_rag 使用关键词而不是模型判断：

- 出现数据结构、算法、复杂度、数组、链表、树、图、DP、BFS、DFS 等主题词，直接触发。
- 或同时出现“是什么、原理、讲解”等意图词和“学习、复习、面试、作业”等学习词，触发。

build_rag_prompt 检索 top 3，再构造 SystemMessage，内容是“RAG知识上下文：”加检索结果。

### 8.4 每轮执行顺序

1. 读取用户输入。
2. exit 或 quit 时保存最近联系时间并结束。
3. 把用户输入加入 chat_history。
4. 抽取并保存长期记忆。
5. 判断天气并尝试提取城市。
6. 读取长期记忆。
7. 判断并执行 RAG。
8. 生成当前时间上下文。
9. 组合 prompt_messages。
10. 调用 Agent 流式输出。
11. 把完整回答加入历史。
12. 裁剪过长历史。

普通问题的消息大致是：系统人设、最近对话、长期记忆、时间感知、可选 RAG。

### 8.5 天气的两条路径

当前有两套天气机制：

1. system_prompt 允许 Agent 自主调用 get_weather。
2. main.py 先用 extract_weather_city 识别城市，再执行 get_weather.invoke，把结果作为天气查询结果消息交给 Agent。

所以天气可能被调用两次。更清晰的设计应该统一成“完全由 Agent 调用”或“由应用层预调用”。

### 8.6 流式输出

stream_agent_reply 遍历 agent.stream(..., stream_mode="messages")，收到 chunk 后立即打印，同时拼出完整文本，最后保存为 AIMessage。delay=0.04 只是终端打字效果。

## 9. 概念对照

| 概念 | 作用 | 本项目 |
|---|---|---|
| Prompt | 规定模型身份和行为 | system_prompt、extract_template |
| Tool | 提供外部实时能力 | get_weather |
| Memory | 保存跨会话事实 | SQLite |
| RAG | 引入外部知识 | Embedding + Milvus |
| Agent | 决策并调用工具 | create_agent |
| Chat History | 保持当前会话连贯 | chat_history |
| LLM | 理解和生成 | DeepSeek |

不要混淆三类上下文：Chat History 是近期原始对话；Memory 是提炼后的稳定用户信息；RAG 是外部知识资料。

## 10. 示例：多个能力协作

用户输入“上海今天下雨吗？我最近在复习二叉树。”时：

1. 输入加入短期历史。
2. LLM 检查是否有长期个人信息。
3. 城市规则得到上海并查询天气。
4. “复习、二叉树”触发 RAG。
5. Milvus 返回二叉树相关片段。
6. 读取长期记忆和当前时间。
7. 将天气、RAG、记忆、历史交给 Agent。
8. DeepSeek 生成陪伴式回答。
9. 流式打印并保存新回复。

## 11. 配置和运行

安装：

    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt

至少配置：

    DEEPSEEK_API_KEY=你的密钥
    DEEPSEEK_BASE_URL=你的BaseURL

天气需要 HEFENG_WEATHER_API_KEY 和 QWEATHER_API_HOST。RAG 需要 SILICONFLOW_API_KEY、SILICONFLOW_BASE_URL，以及可访问的 Milvus。

运行：

    python main.py

单独构建索引：

    python rag.py

## 12. 当前实现的注意点

1. 数学建模文件未接入 RAG。
2. 天气可能重复调用。
3. 每轮都会调用 LLM 做记忆抽取，成本较高。
4. 固定 MEMORY_ID=1，不支持多用户。
5. 全局 SQLite 连接适合单线程命令行，不适合直接用于高并发服务。
6. FIRST_CHAT_TIME 是硬编码，不是首次运行时间。
7. 最近联系时间只在正常退出时保存。
8. RAG 没有相似度阈值和来源引用。
9. 短期历史裁剪后，旧信息依赖记忆抽取才能保留。
10. Agent 初始化时传入 system_prompt，chat_history 又保存了一次系统消息，可能造成重复系统指令。
11. 记忆抽取依赖模型自觉输出 JSON，尚未使用 Pydantic 或 JSON Schema。

## 13. 推荐改造路线

1. 掌握 SystemMessage、HumanMessage、AIMessage 和工具消息。
2. 用 Pydantic/JSON Schema 约束记忆抽取。
3. 统一天气调用策略。
4. 为 RAG 增加相似度阈值、去重、重排序和来源引用。
5. 接入 knowledge 目录下的多个 Markdown、TXT 或 PDF。
6. 将 Milvus 地址、Embedding 模型等改为配置项。
7. 加入 user_id 和 session_id，支持多用户。
8. 区分用户画像、近期事件、关系事件和摘要记忆。
9. 为城市识别、RAG 路由、记忆合并和历史裁剪补测试。
10. 记录模型耗时、工具耗时、token、检索分数和错误率。

## 14. 总结

config.py 是模型入口，prompts.py 是行为规范，tools.py 是外部实时能力，memory_system.py 是用户长期状态，rag.py 是外部知识，main.py 是总编排器。

理解用户输入如何经过记忆抽取、意图路由、工具调用、知识检索、消息组装和模型生成，就理解了这个项目中 Prompt、Tool、Memory、RAG 和 Agent 的实际分工。
