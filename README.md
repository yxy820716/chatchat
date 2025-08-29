# ChatChat 项目

## 简介
基于 **FastAPI** 的多用户聊天与知识库系统，所有数据均存储在本地 **SQLite**。主要功能包括：

- 多用户会话管理与聊天历史记录。
- 提示词和模型配置的增删查。
- 知识库文档解析、向量化与检索。
- 支持按标题层级切分并并发翻译 Markdown 文档的大模型翻译接口。

## 安装与运行
```bash
pip install -r requirements.txt
python main.py  # 默认启动在 http://0.0.0.0:8888
```

## 数据存储
- `./dataset/history`：会话、聊天记录、提示词、模型配置等 SQLite 文件。
- `./dataset/knowbase`：知识库向量及上传的原始文件。

## 接口说明
### 聊天相关 `/chat`
| 方法 | 路径 | 说明 |
|---|---|---|
|POST|`/chat/chat`|普通聊天，支持 `ChatReq` 字段：`query`、`user_id`、`session_id`、`model_name`、`prompt_name` 等。|
|POST|`/chat/rag`|检索增强聊天，会将知识库检索结果追加到问题前。|
|GET|`/chat/session-list`|`?user_id=` 获取用户的会话列表。|
|DELETE|`/chat/remove-session`|`?session_id=` 删除会话及其历史。|
|GET|`/chat/chat-history`|`?user_id=&session_id=&limit=` 查询会话历史。|
|POST|`/chat/prompt`|表单 `name`、`content` 添加提示词。|
|GET|`/chat/prompt`|列出所有提示词。|
|DELETE|`/chat/prompt`|`?name=` 删除指定提示词。|
|POST|`/chat/model-config`|表单 `name`、`base_url`、`model_name`、`api_key`、`max_chunk_len` 添加模型配置。|
|GET|`/chat/model-config`|列出所有模型配置。|
|DELETE|`/chat/model-config`|`?name=` 删除指定模型配置。|
|POST|`/chat/chat-translate`|翻译接口。可传 `query` 直接翻译文本，或传 `doc_id` 翻译上传的 Markdown 文件，按模型配置中的 `max_chunk_len` 分块并发翻译。|
|POST|`/chat/doc-parser`|上传文件并返回提取的 Markdown 文本 `doc_id`。|
|POST|`/chat/get-doc`|根据 `doc_id` 获取解析出的 Markdown。|
|POST|`/chat/translate-doc-parser`|上传文件等待翻译，返回 `doc_id`。|
|POST|`/chat/translate-get-doc`|根据 `doc_id` 获取待翻译文件信息。|
|GET|`/chat/download-target/{file}`|下载翻译后的文件。|
|GET|`/chat/download-initial/{file}`|下载原始文件。|

### 知识库相关 `/kb`
| 方法 | 路径 | 说明 |
|---|---|---|
|POST|`/kb/create`|创建空知识库（Faiss 向量库）。|
|POST|`/kb/create/temporary`|上传文件并创建临时知识库。|
|POST|`/kb/add`|向指定知识库添加文档，自动解析为 Markdown 并切分向量入库。|
|GET|`/kb/search`|`?db_name=&query=&size=` 检索知识库，可限制返回文本长度。|
|DELETE|`/kb/remove-kb`|删除整个知识库。|
|DELETE|`/kb/remove-vector`|按 `ids` 删除指定向量。|
|GET|`/kb/vector-list`|分页查看向量库内容。|
|GET|`/kb/knowledg-list`|列出所有知识库名称。|
|GET|`/kb/download/{file}`|下载上传的原始文件。|

## 接口关联关系
- 聊天接口依赖提示词和模型配置表：调用 `/chat/chat`、`/chat/rag` 或 `/chat/chat-translate` 时会自动从数据库读取对应的提示词与模型参数。
- `/chat/chat-translate` 使用模型配置表中的 `max_chunk_len` 控制 Markdown 分块长度。
- `/kb/add` 与 `/kb/create/temporary` 在解析 Markdown 后也使用相同的切分策略，以便检索时 `/kb/search` 可按需要二分切分长文本。

## 示例
### 普通聊天
```http
POST /chat/chat
{
  "query": "你好",
  "user_id": 1,
  "session_id": null,
  "model_name": "default",
  "prompt_name": "default"
}
```
返回流式 SSE，最终写入 `session_table` 与 `chat_history`。

### 文档翻译流程
1. `POST /chat/translate-doc-parser` 上传文件获取 `doc_id`。
2. `POST /chat/chat-translate` 提交 `{ "doc_id": "上一步返回的 id", "initial_language": "中文", "target_language": "英文" }`。
3. 响应返回翻译前后文件的下载地址。

## 配置文件
- `configs/Prompt_Config.yaml`：初始化默认提示词。
- `configs/Model_Config.yaml`：初始化模型配置及 `TRANSLATE_CHUNK_LEN`，用于控制翻译分块大小。

更多细节可参考源码中的注释。欢迎根据需求扩展。
