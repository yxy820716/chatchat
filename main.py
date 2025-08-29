from fastapi import FastAPI
import uvicorn
import sys
sys.path.insert(0, r"../")
from chatchat.routers.kb_routers import router as kb_router
from chatchat.routers.chat_routers import router as chat_router

app = FastAPI(title="Knowledge Base API", version="1.0.0")
app.include_router(kb_router)
app.include_router(chat_router)

if __name__ == "__main__":
    uvicorn.run(app=app,host="0.0.0.0",port=8888)