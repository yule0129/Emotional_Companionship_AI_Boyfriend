import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model


load_dotenv(override=True)

# LangSmith tracing is optional. Leaving it enabled makes every local chat try
# to contact api.smith.langchain.com and can break or delay replies on networks
# where that service is unavailable.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL")

llm = init_chat_model(
    model="deepseek-v4-flash",
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0.65,
    streaming=True,
)
