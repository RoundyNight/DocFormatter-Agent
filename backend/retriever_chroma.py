import os
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates.txt")
CHROMA_DB_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")

# 全局加载一次模型和 Chroma 集合
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
client = chromadb.Client(Settings(persist_directory=CHROMA_DB_DIR))
collection = client.get_or_create_collection(name="docx_templates")

def load_and_chunk_templates():
    """
    解析 templates.txt，返回模板列表，每个元素 {'id':..., 'content':...}
    并同时将新模板加入 Chroma 集合（如果集合为空则初始化）
    """
    templates = []
    if not os.path.exists(TEMPLATES_PATH):
        return templates

    with open(TEMPLATES_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('# 模板类型：'):
            if current:
                templates.append(current)
            current = {'id': stripped.split('：', 1)[1].strip(), 'content': ''}
        elif current is not None:
            # 跳过关键词行或其他注释行，只保留核心内容
            if not stripped.startswith('#') or stripped.startswith('# 关键词'):
                pass
            current['content'] += line  # 保留所有行，包括标题等

    if current:
        templates.append(current)

    # 如果 Chroma 集合为空，则将模板入库
    if collection.count() == 0 and templates:
        texts = [t['content'] for t in templates]
        ids = [t['id'] for t in templates]
        embeddings = model.encode(texts).tolist()
        collection.add(embeddings=embeddings, documents=texts, ids=ids)

    return templates

def retrieve_template(user_message: str, top_k=1):
    """
    使用向量检索最相关的模板内容，返回最相关的 top_k 个模板的 content 拼接（或仅最佳）
    """
    if collection.count() == 0:
        return None  # 没有模板库

    query_embedding = model.encode([user_message]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=top_k)
    documents = results.get('documents', [[]])[0]
    if documents:
        # 将多个文档拼接（若 top_k>1 则用换行分隔）
        return "\n\n".join(documents)
    return None

# 首次导入时自动初始化
load_and_chunk_templates()