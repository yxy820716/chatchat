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

args = get_config("./configs/Model_Config.yaml")["OPENAI_MODEL_NAME"]
prompts=get_config("./configs/Prompt_Config.yaml")

from langchain_openai.chat_models import ChatOpenAI
MessageDB = DB("./dataset/history")
from langchain.prompts import ChatPromptTemplate,PromptTemplate
from langchain_core.messages import HumanMessage,AIMessage
from pathlib import Path
async def OpenAIChat_Stream(model_name,query,session_id=None,message=True,prompt_name="default"):
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
            for i in MessageDB.get_chat_messages("history", session_id,get_id=True):
                messages.append(HumanMessage(i["user"]))
                messages.append(AIMessage(i["assistant"]))
        except Exception as e:
            pass
        
    """OpenAI 模型"""
    chat = ChatOpenAI(model_name=model_name, base_url=args[model_name]["OPENAI_BASE_URL"],api_key=args[model_name]["OPENAI_API_KEY"])
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system",prompts[prompt_name])
        
    ]+messages+[("user", "{query}")])
    chain = chat_prompt | chat
    contents=""
    answer= chain.astream({"query": query})
    async for chunk in answer:
        if chunk.content:
            yield {"answer":chunk.content.replace("\u202f"," "),"session_id":session_id}
            contents+=chunk.content
    message_id=MessageDB.add_chat_message(
        db_name="history",
        session_id=session_id,
        user="user",
        user_content=query.split("用户问题如下:\n")[-1],
        assistant="assistant",
        assistant_content=contents
    )
    yield {"answer":"","session_id":session_id,"message_id":message_id}



async def OpenAIChat_Invoke(model_name,query,session_id=None,stream=True,message=True,prompt_name="default"):
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
           for i in MessageDB.get_chat_messages("history", session_id,get_id=True):
                messages.append(HumanMessage(i["user"]))
                messages.append(AIMessage(i["assistant"]))
        except Exception as e:
            pass
        
    """OpenAI 模型"""
    chat = ChatOpenAI(model_name=model_name, base_url=args[model_name]["OPENAI_BASE_URL"],api_key=args[model_name]["OPENAI_API_KEY"])
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system",prompts[prompt_name])
    ]+messages+[("user", "{query}")])
    chain = chat_prompt | chat
        # contents=""
    answer= await chain.ainvoke({"query": query})
    contents=answer.content.replace("\u202f"," ")
    message_id=MessageDB.add_chat_message(
        db_name="history",
        session_id=session_id,
        user="user",
        user_content=query,
        assistant="assistant",
        assistant_content=contents
        )
    return {"answer":contents,"session_id":session_id,"message_id":message_id}



async def TranslateChat_Stream(model_name,query,session_id=None,message=True,prompt_name="default"):
    # 查看是否初始化会话表
    """OpenAI 模型"""
    chat = ChatOpenAI(model_name=model_name, base_url=args[model_name]["OPENAI_BASE_URL"],api_key=args[model_name]["OPENAI_API_KEY"])
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system",prompts[prompt_name]),
    ]+[("user", "{query}")])
    chain = chat_prompt | chat
    answer= chain.astream({"query": query})
    async for chunk in answer:
        if chunk.content:
            yield {"answer":chunk.content.replace("\u202f"," "),"session_id":session_id}



async def TranslateChat_Invoke(model_name,query,session_id=None,stream=True,message=True,prompt_name="default"):

    """OpenAI 模型"""
    chat = ChatOpenAI(model_name=model_name, base_url=args[model_name]["OPENAI_BASE_URL"],api_key=args[model_name]["OPENAI_API_KEY"])
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system",prompts[prompt_name]),
    ]+[("user", "{query}")])
    chain = chat_prompt | chat
    answer= await chain.ainvoke({"query": query})
    contents=answer.content.replace("\u202f"," ")
    return {"answer":contents}


# async def chat_cs():
#     answer = OpenAIChat_Stream("你好",session_id=12)
#     async for i in answer:
#         print(i)
#     # answer = await OpenAIChat_Invoke("上一次答案再+1=？",session_id=18)
#     # print(answer)

# if __name__ == "__main__":
#     asyncio.run(chat_cs())