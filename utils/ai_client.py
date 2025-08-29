from email import message
from sre_constants import CH_LOCALE
from click import prompt
from ollama import Message
import yaml
import asyncio
import sys
import os
import json
import uuid
import asyncio
sys.path.insert(0, r"../../")
from chatchat.configs.setting import get_config
from chatchat.dataset.db_crud import DB

args = get_config("./configs/Model_Config.yaml")
prompts=get_config("./configs/Prompt_Config.yaml")

from langchain_openai.chat_models import ChatOpenAI
MessageDB = DB("./dataset/history")
from langchain.prompts import ChatPromptTemplate,PromptTemplate
from pathlib import Path
async def OpenAIChat_Stream(query,session_id=None,message=True,prompt_name="default"):
    # 查看是否初始化会话表
    session_path = Path("../dataset/history/session_table.db")
    if not session_path.exists():
        MessageDB.create_session_table("session_table")
    
    # 查看是否初始化历史记录表
    history_path = Path("../dataset/history/history.db")
    if not history_path.exists():
        MessageDB.create_chat_history_table("history")
        
    messages=[]
    if not session_id:
        session_id = MessageDB.add_session("session_table", query)
    
    if message:
        try:
            messages = MessageDB.get_chat_messages("history", session_id)
        except Exception as e:
            pass
        
    """OpenAI 模型"""
    chat = ChatOpenAI(model_name=args["OPENAI_MODEL_NAME"], base_url=args["OPENAI_BASE_URL"],api_key=args["OPENAI_API_KEY"])
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system",prompts[prompt_name]),
    ]+messages+[("user", "{query}")])
    chain = chat_prompt | chat
    contents=""
    answer= chain.astream({"query": query})
    async for chunk in answer:
        if chunk.content:
            yield {"answer":chunk.content.replace("\u202f"," "),"session_id":session_id}
            contents+=chunk.content
    MessageDB.add_chat_message(
        db_name="history",
        session_id=session_id,
        user="user",
        user_content=query,
        assistant="assistant",
        assistant_content=contents
    )






async def OpenAIChat_Invoke(query,session_id=None,stream=True,message=True,prompt_name="default"):
    # 查看是否初始化会话表
    session_path = Path("../dataset/history/session_table.db")
    if not session_path.exists():
        MessageDB.create_session_table("session_table")
    
    # 查看是否初始化历史记录表
    history_path = Path("../dataset/history/history.db")
    if not history_path.exists():
        MessageDB.create_chat_history_table("history")
        
    messages=[]
    if not session_id:
        session_id = MessageDB.add_session("session_table", query)
    
    if message:
        try:
            messages = MessageDB.get_chat_messages("history", session_id)
        except Exception as e:
            pass
        
    """OpenAI 模型"""
    chat = ChatOpenAI(model_name=args["OPENAI_MODEL_NAME"], base_url=args["OPENAI_BASE_URL"],api_key=args["OPENAI_API_KEY"])
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system",prompts[prompt_name]),
    ]+messages+[("user", "{query}")])
    chain = chat_prompt | chat
        # contents=""
    answer= await chain.ainvoke({"query": query})
    contents=answer.content.replace("\u202f"," ")
    MessageDB.add_chat_message(
        db_name="history",
        session_id=session_id,
        user="user",
        user_content=query,
        assistant="assistant",
        assistant_content=contents
        )
    return {"answer":contents,"session_id":session_id}



async def TranslateChat_Stream(query,session_id=None,message=True,prompt_name="default"):
    # 查看是否初始化会话表
    """OpenAI 模型"""
    chat = ChatOpenAI(model_name=args["OPENAI_MODEL_NAME"], base_url=args["OPENAI_BASE_URL"],api_key=args["OPENAI_API_KEY"],temperature=0.4)
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system",prompts[prompt_name]),
    ]+[("user", "{query}")])
    chain = chat_prompt | chat
    answer= chain.astream({"query": query})
    async for chunk in answer:
        if chunk.content:
            yield {"answer":chunk.content.replace("\u202f"," "),"session_id":session_id}



async def TranslateChat_Invoke(query,session_id=None,stream=True,message=True,prompt_name="default"):

    """OpenAI 模型"""
    chat = ChatOpenAI(model_name=args["OPENAI_MODEL_NAME"], base_url=args["OPENAI_BASE_URL"],api_key=args["OPENAI_API_KEY"])
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system",prompts[prompt_name]),
    ]+[("user", "{query}")])
    chain = chat_prompt | chat
    answer= await chain.ainvoke({"query": query})
    contents=answer.content.replace("\u202f"," ")
    return {"answer":contents}


async def chat_cs():
    answer = OpenAIChat_Stream("你好",session_id=12)
    async for i in answer:
        print(i)
    # answer = await OpenAIChat_Invoke("上一次答案再+1=？",session_id=18)
    # print(answer)

if __name__ == "__main__":
    asyncio.run(chat_cs())