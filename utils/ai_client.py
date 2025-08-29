import asyncio
from pathlib import Path
from typing import List, Optional, Dict

from langchain_openai.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

from chatchat.configs.setting import get_config
from chatchat.dataset.db_crud import DB

# 数据库路径统一
DB_PATH = "./dataset/history"
db = DB(DB_PATH)

# 读取默认配置用于首次初始化
_prompt_init: Dict[str, str] = {}
_model_init: Dict[str, str] = {}
if Path("./configs/Prompt_Config.yaml").exists():
    _prompt_init = get_config("./configs/Prompt_Config.yaml")
if Path("./configs/Model_Config.yaml").exists():
    _model_init = get_config("./configs/Model_Config.yaml")


def _ensure_tables() -> None:
    """初始化所有需要的表，并在第一次启动时写入默认配置"""
    if not Path(f"{DB_PATH}/session_table.db").exists():
        db.create_session_table("session_table")
    if not Path(f"{DB_PATH}/history.db").exists():
        db.create_chat_history_table("history")
    if not Path(f"{DB_PATH}/prompt.db").exists():
        db.create_prompt_table("prompt")
    if not Path(f"{DB_PATH}/model_config.db").exists():
        db.create_model_config_table("model_config")

    # 初始化提示词
    if not db.get_prompts("prompt") and _prompt_init:
        for name, content in _prompt_init.items():
            db.add_prompt("prompt", name, content)
    # 初始化模型配置
    if not db.get_model_configs("model_config") and _model_init:
        db.add_model_config(
            "model_config",
            name="default",
            base_url=_model_init.get("OPENAI_BASE_URL", ""),
            model_name=_model_init.get("OPENAI_MODEL_NAME", ""),
            api_key=_model_init.get("OPENAI_API_KEY", ""),
            max_chunk_len=_model_init.get("TRANSLATE_CHUNK_LEN", 1000),
        )


def _get_prompt(prompt_name: str) -> str:
    prompt = db.get_prompt("prompt", prompt_name)
    return prompt or ""


def _get_model_args(model_name: str) -> Dict[str, str]:
    args = db.get_model_config("model_config", model_name)
    if not args:
        raise ValueError(f"model config {model_name} not found")
    return args


def _split_markdown(text: str, max_len: int) -> List[str]:
    paragraphs = text.split("\n\n")
    chunks: List[str] = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 2 <= max_len:
            current += p + "\n\n"
        else:
            if current:
                chunks.append(current)
            current = p + "\n\n"
    if current:
        chunks.append(current)
    return chunks


async def OpenAIChat_Stream(query: str, user_id: int, session_id: Optional[int] = None,
                            message: bool = True, prompt_name: str = "default", model_name: str = "default"):
    _ensure_tables()
    if not session_id:
        session_id = db.add_session("session_table", user_id, query)
    messages = []
    if message:
        try:
            messages = db.get_chat_messages("history", user_id, session_id)
        except Exception:
            messages = []
    args = _get_model_args(model_name)
    prompt_text = _get_prompt(prompt_name)
    chat = ChatOpenAI(model_name=args["model_name"], base_url=args["base_url"], api_key=args["api_key"])
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_text),
    ] + messages + [("user", "{query}")])
    chain = chat_prompt | chat
    contents = ""
    answer = chain.astream({"query": query})
    async for chunk in answer:
        if chunk.content:
            yield {"answer": chunk.content.replace("\u202f", " "), "session_id": session_id}
            contents += chunk.content
    db.add_chat_message("history", user_id, session_id, "user", query, "assistant", contents)


async def OpenAIChat_Invoke(query: str, user_id: int, session_id: Optional[int] = None,
                            message: bool = True, prompt_name: str = "default", model_name: str = "default"):
    _ensure_tables()
    if not session_id:
        session_id = db.add_session("session_table", user_id, query)
    messages = []
    if message:
        try:
            messages = db.get_chat_messages("history", user_id, session_id)
        except Exception:
            messages = []
    args = _get_model_args(model_name)
    prompt_text = _get_prompt(prompt_name)
    chat = ChatOpenAI(model_name=args["model_name"], base_url=args["base_url"], api_key=args["api_key"])
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_text),
    ] + messages + [("user", "{query}")])
    chain = chat_prompt | chat
    answer = await chain.ainvoke({"query": query})
    contents = answer.content.replace("\u202f", " ")
    db.add_chat_message("history", user_id, session_id, "user", query, "assistant", contents)
    return {"answer": contents, "session_id": session_id}


async def TranslateChat_Stream(query: str, model_name: str = "default", prompt_name: str = "Translate"):
    _ensure_tables()
    args = _get_model_args(model_name)
    prompt_text = _get_prompt(prompt_name)
    chat = ChatOpenAI(model_name=args["model_name"], base_url=args["base_url"], api_key=args["api_key"], temperature=0.4)
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_text),
        ("user", "{query}")
    ])
    chain = chat_prompt | chat
    answer = chain.astream({"query": query})
    async for chunk in answer:
        if chunk.content:
            yield {"answer": chunk.content.replace("\u202f", " ")}


async def TranslateChat_Invoke(query: str, model_name: str = "default", prompt_name: str = "Translate"):
    _ensure_tables()
    args = _get_model_args(model_name)
    prompt_text = _get_prompt(prompt_name)
    chat = ChatOpenAI(model_name=args["model_name"], base_url=args["base_url"], api_key=args["api_key"])
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_text),
        ("user", "{query}")
    ])
    chain = chat_prompt | chat
    answer = await chain.ainvoke({"query": query})
    return {"answer": answer.content.replace("\u202f", " ")}


async def translate_markdown_text(md_text: str, initial_language: str, target_language: str,
                                  model_name: str = "default", prompt_name: str = "Translate") -> str:
    """将 Markdown 文本按配置分段并并发翻译"""
    _ensure_tables()
    args = _get_model_args(model_name)
    chunk_size = args.get("max_chunk_len", 1000)
    chunks = _split_markdown(md_text, chunk_size)
    tasks = []
    for chunk in chunks:
        query = f"请帮我将以下{initial_language}翻译成{target_language},需要翻译的内容如下：\n{chunk}"
        tasks.append(TranslateChat_Invoke(query=query, model_name=model_name, prompt_name=prompt_name))
    results = await asyncio.gather(*tasks)
    return "".join(r["answer"] for r in results)
