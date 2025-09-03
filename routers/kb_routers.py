"""
FastAPI 知识库路由（kb_routers.py）
- 统一封装知识库相关 CRUD 接口
- 支持文件上传 -> 解析 -> 向量化入库
- 在 main.py 中用 app.include_router(router) 统一注册

依赖：fastapi, pydantic, python-multipart
"""
from __future__ import annotations

import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional
from chatchat.dataset.db_crud import DB
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi import status
from pydantic import BaseModel, Field

# === 业务依赖 ===
import sys
sys.path.insert(0, r"../../")
from utils.faiss_crud import FAISS_CURD
from utils.file_parser import PPOCRMarkdownParser

FILES_ROOT = Path(__file__).resolve().parent / "../dataset/knowbase/files"
FILES_ROOT.mkdir(parents=True, exist_ok=True)


# 初始化向量库 CRUD
faiss_curd = FAISS_CURD()

# OCR/解析器（按你工程需要调整参数）
parser = PPOCRMarkdownParser()

# -----------------------------
# Pydantic 模型
# -----------------------------
class BaseResp(BaseModel):
    code: int = Field(200)
    msg: str = Field("success")

class CreateKBReq(BaseModel):
    db_name: str = Field(..., description="向量库名称")

class RemoveKBReq(BaseModel):
    db_name: str = Field(..., description="向量库名称")

class RemoveVectorReq(BaseModel):
    db_name: str = Field(..., description="向量库名称")
    ids: List[str] = Field(..., description="要删除的向量 ID 列表")

class SearchResp(BaseResp):
    code: int = Field(200)
    msg: str = Field("success")
    answer: Optional[List[dict]] = None

class AddVectorResp(BaseResp):
    file_path: Optional[str] = None
    added: Optional[int] = None

class KnowledgListResp(BaseResp):
    kg_list: List
    page: int
    size: int
    Total : int

# -----------------------------
# 工具函数
# -----------------------------

def _safe_filename(name: str) -> str:
    stem = Path(name).stem[:80] or "file"
    suffix = Path(name).suffix
    return f"{stem}_{uuid.uuid4().hex}{suffix}"


def _save_upload(file: UploadFile, subdir: Optional[str] = None) -> Path:
    """保存上传文件到 FILES_ROOT/subdir 下，并返回绝对路径"""
    target_dir = FILES_ROOT if not subdir else FILES_ROOT / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(file.filename or "upload.bin")
    dst = target_dir / filename
    with dst.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return dst.resolve()


# -----------------------------
# Router 定义
# -----------------------------
router = APIRouter(prefix="/kb", tags=["KnowledgeBase"])

import shutil
@router.post("/create", response_model=BaseResp, status_code=status.HTTP_201_CREATED)
def create_kb(req: CreateKBReq):
    try:
        faiss_curd.mkdir_faiss(req.db_name)
        return BaseResp(code=200, msg=f"知识库 {req.db_name} 创建成功")
    except Exception as e:
        shutil.rmtree("./dataset/knowbase/" + req.db_name)
        raise HTTPException(status_code=500, detail=f"创建失败: {e}")

@router.post("/create/temporary", status_code=status.HTTP_201_CREATED)
def create_kb(
    db_name: str = Form("Temporary", description="向量库名称"),
    file: UploadFile = File(..., description="上传文档：pdf/docx/png/jpg 等")
):
    shutil.rmtree(f"./dataset/knowbase/{db_name}", ignore_errors=True)
    try:
        faiss_curd.mkdir_faiss(db_name)
        # 1) 保存文件
        file_path = _save_upload(file)

        # 2) 解析为 Markdown
        md_text = parser.to_markdown(str(file_path))
        
        md_text=md_text["markdown"]

        if not md_text or not md_text.strip():
            raise ValueError("解析结果为空")

        # 3) 切分成 chunk 列表
        #    若你的 parser 已带分段，可按需调整
        vector_list = [seg.strip() for seg in md_text.split("\n## ") if seg.strip()]
        if not vector_list:
            raise ValueError("未切分出有效段落")

        # 4) 入库
        faiss_curd.add_vector(db_name, vector_list, str(file_path))
        return {"code":200,"file_url":"/kb/download/" + os.path.basename(file_path)}

    except Exception as e:
        shutil.rmtree("./dataset/knowbase/" + db_name)
        raise HTTPException(status_code=500, detail=f"创建失败: {e}")


@router.post("/add", response_model=AddVectorResp)
def add_vector(
    db_name: str = Form(..., description="向量库名称"),
    file: UploadFile = File(..., description="上传文档：pdf/docx/png/jpg 等")
):
    """
    上传文件 -> 转 Markdown -> 切分 -> 写入向量库
    - 文件保存到 ../dataset/knowbase/{db_name}/files 下（若无自动创建）
    - Markdown 切分策略：以 '##' 作为章节块
    """
    try:
        # 1) 保存文件
        file_path = _save_upload(file)

        # 2) 解析为 Markdown
        md_text = parser.to_markdown(str(file_path))
        md_text=md_text["markdown"]
        if not md_text or not md_text.strip():
            raise ValueError("解析结果为空")

        # 3) 切分成 chunk 列表
        #    若你的 parser 已带分段，可按需调整
        vector_list = [seg.strip() for seg in md_text.split("\n## ") if seg.strip()]
        if not vector_list:
            raise ValueError("未切分出有效段落")

        # 4) 入库
        faiss_curd.add_vector(db_name, vector_list, str(file_path))
        return AddVectorResp(code=200, msg="向量化成功", file_path=str(file_path), added=len(vector_list))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"向量化失败: {e}")


@router.get("/search", response_model=SearchResp)
def search_vector(db_name: str = Query(...), query: str = Query(...),top_k: int = Query(...)):
    try:
        answer = faiss_curd.search_vector(db_name, query,top_k)
        return SearchResp(code=200, msg="ok", answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


@router.delete("/remove-kb", response_model=BaseResp)
def remove_kb(req: RemoveKBReq):
    try:
        # 你原函数是固定 "ce"，这里改为可传库名
        faiss_curd.revome_kb(req.db_name)
        return BaseResp(code=200, msg=f"知识库 {req.db_name} 已删除")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除知识库失败: {e}")


@router.delete("/remove-vector", response_model=BaseResp)
def remove_vector(req: RemoveVectorReq):
    try:
        # 你原函数固定库名 "cs"，这里统一为可传库名
        faiss_curd.revome_vector(req.db_name, req.ids)
        return BaseResp(code=200, msg=f"已从 {req.db_name} 删除 {len(req.ids)} 条向量")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除向量失败: {e}")


@router.get("/vector-list")
def vector_list(faiss_name: str= Query(...),page: int= Query(...),page_size :int= Query(...)):
    try:
        Vector_DB=DB("./dataset/knowbase/"+faiss_name)
        vector_list=Vector_DB.get_vector_data("knowledge_base",page=page,page_size=page_size)
        return  vector_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取向量列表: {e}")

@router.get("/knowledg-list", response_model=KnowledgListResp)
def Knowledg_List(page: int = 1, size: int = 10):
    base_path = "./dataset/knowbase"
    all_folders = []
    
    # 获取 knowbase 目录下的直接子文件夹
    try:
        with os.scandir(base_path) as entries:
            for entry in entries:
                if entry.is_dir() and entry.name not in ["files", "Translate", "Temporary"]:
                    all_folders.append(entry.name)
    except FileNotFoundError:
        # 如果目录不存在，返回空列表
        pass
    
    # 分页处理
    if page == 0:
        page = 1
    
    start_index = (page - 1) * size
    end_index = page * size
    
    return KnowledgListResp(
        code=200,
        msg="查询成功",
        kg_list=all_folders[start_index:end_index],
        page=page,
        size=size,
        Total=len(all_folders)
    )


@router.get("/download/{file_name}")
def download_file(file_name: str):
    file_path="./dataset/knowbase/files/"+file_name
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=os.path.basename(file_path))
