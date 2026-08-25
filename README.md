# AI Practice

一个基于 LangChain 和 DeepSeek 的 AI 男友聊天陪伴项目。它的核心不是冷冰冰地回答问题，而是通过稳定人设、长期记忆、时间感知和细腻回应，提供持续的情绪陪伴与情绪价值。

项目中的 AI 男友拥有克制、高冷、嘴硬但体贴的人设：表面话少，内里会关注用户的身体、情绪、作息和近况。它会记住用户长期稳定的信息，并在后续聊天中自然带入，让对话更像一段持续的关系，而不是一次性的问答。

## 功能特性

- AI 男友陪伴：围绕长期聊天、情绪安抚、日常关心和关系感设计，而不是单纯知识问答。
- 角色化回复：通过 `prompts.py` 配置高冷、嘴硬、克制但体贴的人设风格。
- 情绪价值回应：优先捕捉用户话语背后的委屈、不安、疲惫和孤独感，先共情，再回应。
- 长期记忆：自动提取姓名、城市、偏好、作息等稳定信息，并保存到 SQLite 数据库。
- 关系延续感：记录首次聊天时间和最近联系时间，久未联系时会自然表现出轻微不满和在意。
- 时间感知：根据当前时间生成更自然的关怀，例如早餐、午休、下班、早点睡等。
- 天气关心：识别天气、气温、出门穿搭等问题后，调用和风天气接口，给出更贴近日常生活的提醒。
- 学习陪伴：当用户提问数据结构、算法、复杂度等学习问题时，会从 `knowledge/数据结构学习.md` 中检索相关上下文辅助讲解。

## 项目结构

```text
.
├── main.py                  # 程序入口，负责聊天循环、陪伴上下文、工具调用、记忆和 RAG 拼接
├── config.py                # 模型配置，读取环境变量并初始化 LLM
├── prompts.py               # AI 男友人设提示词和长期记忆提取提示词
├── memory_system.py         # 长期记忆的提取、保存和读取
├── tools.py                 # 天气工具、城市识别和时间上下文
├── rag.py                   # 数据结构知识库切分、向量索引和检索
├── knowledge/               # 本地知识资料
│   ├── 数据结构学习.md
│   └── 数学建模模型.txt
├── requirements.txt         # Python 依赖
└── long_term_memory.db      # SQLite 长期记忆数据库，运行后生成或更新
```

## 环境要求

- Python 3.11 或更高版本
- DeepSeek 兼容的 OpenAI API 接口
- 可选：和风天气 API Key
- 可选：Milvus 服务，用于 RAG 向量检索

## 安装依赖

建议先创建并启用虚拟环境：

```bash
python -m venv venv
```

Windows PowerShell：

```powershell
.\venv\Scripts\Activate.ps1
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 环境变量

在项目根目录创建 `.env` 文件，并按需配置：

```env
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=你的 DeepSeek Base URL

HEFENG_WEATHER_API_KEY=你的和风天气 API Key
QWEATHER_API_HOST=你的和风天气专属 API Host

SILICONFLOW_API_KEY=你的 SiliconFlow API Key
SILICONFLOW_BASE_URL=你的 SiliconFlow Base URL
```

说明：

- `DEEPSEEK_API_KEY` 和 `DEEPSEEK_BASE_URL` 是主聊天模型必需配置。
- `HEFENG_WEATHER_API_KEY` 用于天气查询；不配置时，天气工具会返回配置提示。
- `QWEATHER_API_HOST` 建议填写和风天气控制台提供的专属 Host。
- `SILICONFLOW_API_KEY` 和 `SILICONFLOW_BASE_URL` 用于 `BAAI/bge-m3` Embedding。

## 运行项目

```bash
python main.py
```

启动后会进入命令行聊天。你可以像和一个长期陪伴对象聊天一样输入日常想法、情绪、问题或近况：

```text
你可以开始和他聊天了，输入 'exit' 或 'quit' 来结束对话。
```

输入 `exit` 或 `quit` 会结束聊天，并保存最近联系时间。

适合输入的内容示例：

```text
我今天有点累
你还记得我住在哪吗
上海今天冷不冷，出门穿什么
好几天没来找你了
给我讲讲二叉树
```

## RAG 知识库

当前 RAG 默认读取：

```text
knowledge/数据结构学习.md
```

首次检索时，如果 Milvus 中还没有集合，程序会自动构建索引。也可以手动构建：

```bash
python rag.py
```

默认 Milvus 地址为：

```text
http://localhost:19530
```

如果需要修改数据库名、集合名、Embedding 模型或知识文件路径，可以在 `rag.py` 中调整：

- `MILVUS_URL`
- `DB_NAME`
- `COLLECTION_NAME`
- `EMBEDDING_MODEL_NAME`
- `FILE_PATH`

## 长期记忆

长期记忆是这个 AI 男友项目的重要部分。它让聊天不只是一次性回复，而是能逐渐积累用户画像和相处细节。

记忆保存在项目根目录的 `long_term_memory.db` 中。程序会维护一条固定用户记忆记录，包含：

- 姓名
- 常住城市
- 生日
- 偏好
- 作息习惯
- 其他长期偏好
- 首次聊天时间
- 最近联系时间

如果不想保留历史记忆，可以在停止程序后删除 `long_term_memory.db`，下次运行时会重新创建。

## 测试

项目已安装 `pytest`，可以运行：

```bash
pytest
```

当前 `tests/` 目录下暂未包含实际测试文件，因此可能不会执行任何测试用例。

## 注意事项

- `.env` 中包含 API Key，不要提交到公开仓库。
- `long_term_memory.db` 包含聊天记忆数据，如涉及隐私，也不建议提交。
- 天气查询依赖网络和和风天气配置。
- RAG 检索依赖 Milvus 和 Embedding 服务配置；如果只使用普通聊天和天气功能，可以暂时不启动 Milvus。
