
import shutil
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
import sys
from fastapi.responses import StreamingResponse,FileResponse
from pydantic import BaseModel,Field
from regex import F
sys.path.insert(0, r"../../")
from chatchat.utils.ai_client import OpenAIChat_Stream,OpenAIChat_Invoke,TranslateChat_Stream,TranslateChat_Invoke
from chatchat.dataset.db_crud import DB
import json
from chatchat.utils.faiss_crud import FAISS_CURD
from chatchat.routers.kb_routers import parser
from chatchat.routers.kb_routers import _save_upload
router = APIRouter(prefix="/chat", tags=["LLM-CHAT"])
from chatchat.configs.setting import add_model_config,remove_model_config,get_config,add_default_model,remove_default_model
db=DB("./dataset/history")
voctor = FAISS_CURD()
class ChatReq(BaseModel):
    query: str = None
    session_id : int = None
    message : bool = True
    prompt_name : str = "default"
    faiss_name : str = None
    file_id : list = None
    model_name : str = "qwen-max"
class translateReq(ChatReq):
    initial_language :str = "中文"
    target_language :str = "英文"
    doc_id : str = None
    model_name : str = "qwen-max"
@router.post("/chat")
async def chat(req:ChatReq):
    if req.file_id == [] or not req.file_id :
        query = req.query
    else:
        texts = ""
        num = 0
        for i in req.file_id:
            num = num + 1
            texts = f"文档{num}:\n" + texts + DOCUMENT_TEXT[i] + "\n\n"
            DOCUMENT_TEXT.pop(i, None)
        query = "文档内容如下:\n"  + texts + "文档内容如上；\n\n" + "用户问题如下:\n" + req.query
    answer=OpenAIChat_Stream(model_name=req.model_name,query=query,session_id=req.session_id,message=req.message,prompt_name=req.prompt_name)
    async def _event_stream():
        async for chunk in answer:
            yield "data: "+json.dumps(chunk,ensure_ascii=False)+ "\n\n"
    
    return StreamingResponse(content=_event_stream(), media_type="text/event-stream",headers={"Cache-Control": "no-cache","Connection":"keep-alive"})

@router.post("/rag")
async def chat(req:ChatReq):
    reference_documents= "参考文档信息如下：\n" + json.dumps(voctor.search_vector(req.faiss_name,req.query),indent=2,ensure_ascii=False) + "参考文档信息如上；\n\n"
    # print(reference_documents)
    query=reference_documents + "用户问题如下:\n" + req.query
    answer=OpenAIChat_Stream(model_name=req.model_name,query=query,session_id=req.session_id,message=req.message,prompt_name=req.prompt_name)
    async def _event_stream():
        async for chunk in answer:
            yield "data: "+json.dumps(chunk,ensure_ascii=False)+ "\n\n"
    
    return StreamingResponse(content=_event_stream(), media_type="text/event-stream",headers={"Cache-Control": "no-cache","Connection":"keep-alive"})

@router.get("/session-list")
async def get_session():
    session_list=db.get_sessions("session_table")
    return {"session_list":session_list,"code":200,"msg":"查询成功"}

@router.delete("/remove-session")
async def get_session(session_id):
    try:
        if session_id == "all":
            db.delete_sessions(db_name="session_table")
        else:
            db.delete_session(db_name="session_table",session_id=session_id)
        return {"code":200,"msg":"删除会话成功"}
    except Exception as e:
        return {"code":500,"msg":str(e)}
    
@router.post("/update-session-name")
async def update_session_name(session_id: int,new_name: str):
    db.update_session_name(db_name="session_table",session_id=session_id,new_name=new_name)
    return True

@router.get("/chat-history")
async def get_chat_history(session_id:int,limit=int):
    try:
        chat_history=db.get_chat_messages(db_name="history",session_id=session_id,limit=limit,get_id=True)

        return {"chat_history":chat_history,"code":200,"msg":"查询成功"}
    except Exception as e:
        return {"code":500,"msg":str(e)}

@router.delete("/revome-message")
async def delete_chat_history(message_id:int):
    db.delete_chat_message(db_name="history",message_id=message_id)
    return {"code":200,"msg":"删除成功"}

@router.post("/chat-translate")
async def chat(req:translateReq):
    if not req.query and req.doc_id:
        file_name = Translate_DOCUMENT_TEXT[req.doc_id]["file_name"]
        query= f"请帮我将以下{req.initial_language}翻译成{req.target_language},需要翻译的内容如下：\n{Translate_DOCUMENT_TEXT[req.doc_id]["md_text"]}"
        answer=await TranslateChat_Invoke(model_name=req.model_name,query=query,session_id=req.session_id,message=req.message,prompt_name=req.prompt_name)
         # 写入到文件（注意 open 的参数顺序与模式）
        TargetOut_Path = f"./dataset/knowbase/Translate/target/{file_name}.md"
        InitialOut_Path = f"./dataset/knowbase/Translate/initial/{file_name}.md"
        # 确保目录存在（可选）
        import os
        os.makedirs(os.path.dirname(TargetOut_Path), exist_ok=True)
        os.makedirs(os.path.dirname(InitialOut_Path), exist_ok=True)

        with open(TargetOut_Path, "w", encoding="utf-8") as f:
            f.write(answer["answer"])
        with open(InitialOut_Path, "w", encoding="utf-8") as f:
            f.write(Translate_DOCUMENT_TEXT[req.doc_id]["md_text"])

        target_file_url=os.path.join("/chat/download-target/" , os.path.basename(TargetOut_Path))
        initial_file_url=os.path.join("/chat/download-initial/" , os.path.basename(InitialOut_Path))
        Translate_DOCUMENT_TEXT.pop(req.doc_id, None)
        return {"target_file_url": target_file_url,"initial_file_url":initial_file_url,"code":200,"msg":"翻译成功"}

    query= f"请帮我将以下{req.initial_language}翻译成{req.target_language},需要翻译的内容如下：\n{req.query}"
    answer=TranslateChat_Stream(model_name=req.model_name,query=query,session_id=req.session_id,message=req.message,prompt_name=req.prompt_name)
    async def _event_stream():
        async for chunk in answer:
            yield "data: "+json.dumps(chunk,ensure_ascii=False)+ "\n\n"
    
    return StreamingResponse(content=_event_stream(), media_type="text/event-stream",headers={"Cache-Control": "no-cache","Connection":"keep-alive"})




@router.get("/download-target/{file_name}")
def download_file(file_name: str):
    file_path="./dataset/knowbase/Translate/target/"+file_name
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=os.path.basename(file_path))


@router.get("/download-initial/{file_name}")
def download_file(file_name: str):
    file_path="./dataset/knowbase/Translate/initial/"+file_name
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=os.path.basename(file_path))


import uuid
DOCUMENT_TEXT={}

@router.post("/doc-parser")
async def doc_parser(file: UploadFile = File(...)):
    file_path = _save_upload(file)
    # 2) 解析为 Markdown
    md_text = parser.to_markdown(str(file_path))
    md_text=md_text["markdown"]
    id=str(uuid.uuid4())
    DOCUMENT_TEXT[id] = md_text
    return {"id": id,"code":200,"msg":"文件内容提取完成"}


@router.get("/get-doc")
async def get_doc():
    return {"text": DOCUMENT_TEXT,"code":200,"msg":"获取成功"}

@router.delete("/remove-doc")
async def delete_doc(id: str):
    DOCUMENT_TEXT.pop(id)
    return {"code":200,"msg":"删除成功"}

@router.delete("/remove-doc-list")
async def delete_doc():
    DOCUMENT_TEXT.clear()   # 清空原字典内容
    return {"code": 200, "msg": "清空成功"}


import os
Translate_DOCUMENT_TEXT = {}
@router.post("/translate-doc-parser")
async def doc_parser(file: UploadFile = File(...)):
    file_path = _save_upload(file)
    # 2) 解析为 Markdown
    md_text = parser.to_markdown(str(file_path))
    md_text=md_text["markdown"]
    id=str(uuid.uuid4())
    Translate_DOCUMENT_TEXT[id] = {"file_name":os.path.basename(file_path),"md_text":md_text}
    return {"id": id,"code":200,"msg":"文件内容提取完成"}


@router.post("/translate-get-doc")
async def get_doc(id: str):
    return {"text": Translate_DOCUMENT_TEXT[id],"code":200,"msg":"获取成功"}


yaml_path="./configs/Model_Config.yaml"

@router.post("/add-model")
async def get_doc(model_name: str, base_url: str, api_key: str):
    stauts=add_model_config(
        yaml_path=yaml_path,
        model_name=model_name,
        base_url=base_url,
        api_key=api_key
    )
    if stauts:
        return {"code":200,"msg":"添加成功"}
    else:
        return {"code":200,"msg":"添加失败"}

@router.delete("/remove-model")
async def get_doc( model_name: str):
    stauts=remove_model_config(yaml_path, model_name)
    if stauts:
        return {"code":200,"msg":"删除成功"}
    else:
        return {"code":200,"msg":"删除失败"}

@router.get("/get-model")
async def get_doc(page: int = 1, size: int = 10):
    cfg_all = get_config(yaml_path) or {}
    cfg = cfg_all.get("OPENAI_MODEL_NAME", {}) or {}
    DEFAULT_MODEL = cfg_all.get("DEFAULT_MODEL", "")

    data = [
        {
            "model_name": name,
            "url": info.get("OPENAI_BASE_URL", ""),
            "api_key": info.get("OPENAI_API_KEY", ""), 
            "default_model": (name == DEFAULT_MODEL),
        }
        for name, info in cfg.items()
    ]

    total = len(data)
    page = max(1, int(page))
    size = max(1, int(size))
    start = (page - 1) * size
    end = start + size

    return {
        "code": 200,
        "msg": "获取成功",
        "config": data[start:end],
        "total": total,
    }


@router.get("/get-default-model")
async def get_doc():
    config=get_config(yaml_path)

    return {"code":200,"msg":"获取成功","config":config["DEFAULT_MODEL"]}


@router.post("/add-default-model")
async def get_doc(model_name: str):
    stauts=add_default_model(
        model_name=model_name,
        yaml_path=yaml_path
    )
    if stauts:
        return {"code":200,"msg":"添加成功"}
    else:
        return {"code":200,"msg":"添加失败"}

@router.delete("/remove-default_model")
async def get_doc( model_name: str):
    stauts=remove_default_model(model_name,yaml_path=yaml_path)
    if stauts:
        return {"code":200,"msg":"删除成功"}
    else:
        return {"code":200,"msg":"删除失败"}

@router.get("/get-ip")
async def get_ip():
    ip=get_config(yaml_path)["DEFAULT_IP"]
    return {"ip":ip,"code":200,"msg":"获取成功"}



