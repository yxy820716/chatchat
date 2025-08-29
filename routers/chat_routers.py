import os
import json
import uuid
import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from chatchat.utils.ai_client import (
    OpenAIChat_Stream,
    OpenAIChat_Invoke,
    TranslateChat_Stream,
    TranslateChat_Invoke,
    translate_markdown_text,
)
from chatchat.dataset.db_crud import DB
from chatchat.utils.faiss_crud import FAISS_CURD
from chatchat.routers.kb_routers import parser, _save_upload

router = APIRouter(prefix="/chat", tags=["LLM-CHAT"])

db = DB("./dataset/history")
vector = FAISS_CURD()


class ChatReq(BaseModel):
    query: str | None = None
    user_id: int
    session_id: int | None = None
    model_name: str = "default"
    message: bool = True
    prompt_name: str = "default"
    faiss_name: str | None = None
    file_id: list | None = None


class TranslateReq(ChatReq):
    initial_language: str = "中文"
    target_language: str = "英文"
    doc_id: str | None = None


@router.post("/chat")
async def chat(req: ChatReq):
    if req.file_id:
        texts = ""
        for num, fid in enumerate(req.file_id, start=1):
            texts += f"文档{num}:\n" + DOCUMENT_TEXT[fid] + "\n\n"
            DOCUMENT_TEXT.pop(fid, None)
        query = "文档内容如下:\n" + texts + "文档内容如上；\n\n用户问题如下\n" + req.query
    else:
        query = req.query
    answer = OpenAIChat_Stream(
        query=query,
        user_id=req.user_id,
        session_id=req.session_id,
        message=req.message,
        prompt_name=req.prompt_name,
        model_name=req.model_name,
    )

    async def _event_stream():
        async for chunk in answer:
            yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        content=_event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/rag")
async def rag_chat(req: ChatReq):
    reference_documents = (
        "参考文档信息如下：\n"
        + json.dumps(vector.search_vector(req.faiss_name, req.query), indent=2, ensure_ascii=False)
        + "参考文档信息如上；\n\n"
    )
    query = reference_documents + "用户问题如下：\n" + req.query + "用户问题如上；"
    answer = OpenAIChat_Stream(
        query=query,
        user_id=req.user_id,
        session_id=req.session_id,
        message=req.message,
        prompt_name=req.prompt_name,
        model_name=req.model_name,
    )

    async def _event_stream():
        async for chunk in answer:
            yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        content=_event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/session-list")
async def get_session(user_id: int):
    session_list = db.get_sessions("session_table", user_id)
    return {"session_list": session_list, "code": 200, "msg": "查询成功"}


@router.delete("/remove-session")
async def remove_session(session_id: int):
    try:
        db.delete_session(db_name="session_table", session_id=session_id)
        return {"code": 200, "msg": "删除会话成功"}
    except Exception as e:
        return {"code": 500, "msg": str(e)}


@router.get("/chat-history")
async def get_chat_history(user_id: int, session_id: int, limit: int):
    try:
        chat_history = db.get_chat_messages("history", user_id=user_id, session_id=session_id, limit=limit)
        return {"chat_history": chat_history, "code": 200, "msg": "查询成功"}
    except Exception as e:
        return {"code": 500, "msg": str(e)}


@router.post("/prompt")
async def add_prompt(name: str = Form(...), content: str = Form(...)):
    try:
        db.add_prompt("prompt", name, content)
        return {"code": 200, "msg": "添加成功"}
    except Exception as e:
        return {"code": 500, "msg": str(e)}


@router.get("/prompt")
async def list_prompt():
    prompts = db.get_prompts("prompt")
    return {"prompts": prompts, "code": 200, "msg": "查询成功"}


@router.delete("/prompt")
async def delete_prompt(name: str):
    try:
        db.delete_prompt("prompt", name)
        return {"code": 200, "msg": "删除成功"}
    except Exception as e:
        return {"code": 500, "msg": str(e)}


@router.post("/model-config")
async def add_model_config(
    name: str = Form(...),
    base_url: str = Form(...),
    model_name: str = Form(...),
    api_key: str = Form(...),
    max_chunk_len: int = Form(1000),
):
    try:
        db.add_model_config("model_config", name, base_url, model_name, api_key, max_chunk_len)
        return {"code": 200, "msg": "添加成功"}
    except Exception as e:
        return {"code": 500, "msg": str(e)}


@router.get("/model-config")
async def list_model_config():
    configs = db.get_model_configs("model_config")
    return {"configs": configs, "code": 200, "msg": "查询成功"}


@router.delete("/model-config")
async def delete_model_config(name: str):
    try:
        db.delete_model_config("model_config", name)
        return {"code": 200, "msg": "删除成功"}
    except Exception as e:
        return {"code": 500, "msg": str(e)}


@router.post("/chat-translate")
async def chat_translate(req: TranslateReq):
    if not req.query and req.doc_id:
        file_name = Translate_DOCUMENT_TEXT[req.doc_id]["file_name"]
        md_text = Translate_DOCUMENT_TEXT[req.doc_id]["md_text"]
        translated = await translate_markdown_text(
            md_text,
            req.initial_language,
            req.target_language,
            model_name=req.model_name,
            prompt_name=req.prompt_name,
        )
        target_path = f"./dataset/knowbase/Translate/target/{file_name}.md"
        initial_path = f"./dataset/knowbase/Translate/initial/{file_name}.md"
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(translated)
        with open(initial_path, "w", encoding="utf-8") as f:
            f.write(md_text)
        target_file_url = os.path.join("/chat/download-target/", os.path.basename(target_path))
        initial_file_url = os.path.join("/chat/download-initial/", os.path.basename(initial_path))
        Translate_DOCUMENT_TEXT.pop(req.doc_id, None)
        return {
            "target_file_url": target_file_url,
            "initial_file_url": initial_file_url,
            "code": 200,
            "msg": "翻译成功",
        }

    query = f"请帮我将以下{req.initial_language}翻译成{req.target_language},需要翻译的内容如下：\n{req.query}"
    answer = TranslateChat_Stream(query=query, model_name=req.model_name, prompt_name=req.prompt_name)

    async def _event_stream():
        async for chunk in answer:
            yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        content=_event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/download-target/{file_name}")
def download_target(file_name: str):
    file_path = "./dataset/knowbase/Translate/target/" + file_name
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=os.path.basename(file_path))


@router.get("/download-initial/{file_name}")
def download_initial(file_name: str):
    file_path = "./dataset/knowbase/Translate/initial/" + file_name
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=os.path.basename(file_path))


DOCUMENT_TEXT: dict[str, str] = {}
Translate_DOCUMENT_TEXT: dict[str, dict[str, str]] = {}


@router.post("/doc-parser")
async def doc_parser(file: UploadFile = File(...)):
    file_path = _save_upload(file)
    md_text = parser.to_markdown(str(file_path))["markdown"]
    doc_id = str(uuid.uuid4())
    DOCUMENT_TEXT[doc_id] = md_text
    return {"id": doc_id, "code": 200, "msg": "文件内容提取完成"}


@router.post("/get-doc")
async def get_doc(doc_id: str):
    return {"text": DOCUMENT_TEXT[doc_id], "code": 200, "msg": "获取成功"}


@router.post("/translate-doc-parser")
async def translate_doc_parser(file: UploadFile = File(...)):
    file_path = _save_upload(file)
    md_text = parser.to_markdown(str(file_path))["markdown"]
    doc_id = str(uuid.uuid4())
    Translate_DOCUMENT_TEXT[doc_id] = {"file_name": os.path.basename(file_path), "md_text": md_text}
    return {"id": doc_id, "code": 200, "msg": "文件内容提取完成"}


@router.post("/translate-get-doc")
async def translate_get_doc(doc_id: str):
    return {"text": Translate_DOCUMENT_TEXT[doc_id], "code": 200, "msg": "获取成功"}
