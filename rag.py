import os

from dotenv import load_dotenv
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from pymilvus import MilvusClient


MILVUS_URL = "http://localhost:19530"
DB_NAME = "data_structures"
COLLECTION_NAME = "data_structures_collection"
EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
EMBED_DIMENSION = 1024
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_PATH = os.path.join(BASE_DIR, "knowledge", "数据结构学习.md")


load_dotenv(override=True)


def get_embed_model():
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL_NAME,
        api_key=os.getenv("SILICONFLOW_API_KEY"),
        base_url=os.getenv("SILICONFLOW_BASE_URL"),
    )


def get_client():
    client = MilvusClient(MILVUS_URL)
    existed_databases = client.list_databases()
    if DB_NAME not in existed_databases:
        client.create_database(DB_NAME)
    client.using_database(DB_NAME)
    return client


def build_chunks(file_path: str = FILE_PATH):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"知识文件不存在：{file_path}")

    loader = UnstructuredMarkdownLoader(
        file_path=file_path,
        mode="single",
        strategy="fast",
    )
    loader.load()

    with open(file_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    headers_to_split_on = [
        ("#", "h1"),
        ("##", "h2"),
    ]

    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False,
    )
    docs = markdown_splitter.split_text(markdown_text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    )
    return splitter.split_documents(docs)


def ensure_collection(client: MilvusClient):
    existed_collections = client.list_collections()
    if COLLECTION_NAME in existed_collections:
        client.drop_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        dimension=EMBED_DIMENSION,
        metric_type="COSINE",
    )


def build_index(file_path: str = FILE_PATH):
    client = get_client()
    ensure_collection(client)

    chunks = build_chunks(file_path)
    texts = [chunk.page_content for chunk in chunks]
    embed_model = get_embed_model()
    vectors = embed_model.embed_documents(texts)

    data = [
        {
            "id": i,
            "vector": vectors[i],
            "text": texts[i],
            "source": file_path,
            "chunk_id": i,
        }
        for i in range(len(texts))
    ]

    client.upsert(
        collection_name=COLLECTION_NAME,
        data=data,
    )


def search_context(query: str, top_k: int = 3):
    if not query.strip():
        return ""

    client = get_client()
    if COLLECTION_NAME not in client.list_collections():
        build_index()

    embed_model = get_embed_model()
    query_vector = embed_model.embed_query(query)

    results = client.search(
        collection_name=COLLECTION_NAME,
        data=[query_vector],
        limit=top_k,
        output_fields=["text", "source", "chunk_id"],
    )

    if not results:
        return ""

    items = []
    for rank, hit in enumerate(results[0], start=1):
        entity = hit.get("entity", {})
        text = entity.get("text", "")
        if text:
            items.append(f"[{rank}] {text}")

    return "\n\n".join(items)


if __name__ == "__main__":
    build_index()
