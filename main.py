from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import sys

sys.path.insert(0, r"../")
from chatchat.routers.kb_routers import router as kb_router
from chatchat.routers.chat_routers import router as chat_router

app = FastAPI()

# 静态文件目录（js, css, images）
app.mount("/static", StaticFiles(directory="dist/static"), name="static")

# 模板目录（放 index.html）
templates = Jinja2Templates(directory="dist")

@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 注册后端 API 路由
app.include_router(kb_router)
app.include_router(chat_router)

# 兜底路由：把所有未匹配到的路由交给前端路由处理
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(request: Request, full_path: str):
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    uvicorn.run(app=app, host="0.0.0.0", port=8888)
