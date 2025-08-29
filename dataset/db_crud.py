import os
import sqlite3
from typing import Optional, Dict, Any
import math
from typing import List, Dict, Any
class DB:
    def __init__(self, db_path: str = "database"):
        """
        初始化数据库类（同步版）
        Args:
            db_path: 数据库文件存储目录
        """
        self.db_path = db_path
        if not os.path.exists(db_path):
            os.makedirs(db_path,exist_ok=True)

    def _get_db_file(self, db_name: str) -> str:
        """拼接数据库文件路径"""
        return os.path.join(self.db_path, f"{db_name}.db")

    def _connect(self, db_name: str) -> sqlite3.Connection:
        """
        获取同步 SQLite 连接
        - 设定 row_factory 方便以字典方式取值
        - 可按需设置 PRAGMA
        """
        db_file = self._get_db_file(db_name)
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        # 可选优化：WAL 提升并发读写能力
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    # ---------------- 向量数据表 ----------------
    def create_vector_db(self, db_name: str) -> None:
        """
        创建向量数据库表（vector_data）
        create_time 默认写入北京时间（UTC+8）
        """
        try:
            with self._connect(db_name) as db:
                db.execute('''
                    CREATE TABLE IF NOT EXISTS vector_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        vector_id TEXT NOT NULL,
                        texts TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        create_time TIMESTAMP DEFAULT (datetime('now', '+8 hours'))
                    )
                ''')
                db.commit()
        except Exception as e:
            print(f"创建向量数据库表失败: {e}")
            raise

    def add_vector_data(self, vector_id: str, db_name: str, texts: str, file_path: str) :
        """
        插入向量数据（同步）
        """
        try:
            with self._connect(db_name) as db:
                db.execute('''
                    INSERT INTO vector_data (vector_id, texts, file_path)
                    VALUES (?, ?, ?)
                ''', (vector_id, texts, file_path))
                db.commit()
            return True
        except Exception as e:
            print(f"插入向量数据失败: {e}")
            raise

    import math

    def get_vector_data(self, db_name: str, page: int = 1, page_size: int = 20):
        # 简单容错
        page = max(1, int(page))
        page_size = max(1, int(page_size))
        offset = (page - 1) * page_size

        with self._connect(db_name) as db:
            # 总数
            total = db.execute("SELECT COUNT(*) FROM vector_data").fetchone()[0]
            total_pages = math.ceil(total / page_size) if total > 0 else 0

            # 当前页
            cur = db.execute(
                """
                SELECT id, vector_id, texts, file_path, create_time
                FROM vector_data
                ORDER BY create_time DESC
                LIMIT ? OFFSET ?
                """,
                (page_size, offset),
            )
            rows = cur.fetchall()
            items = [dict(r) for r in rows]
            items = [
                {
                    "stauts": 0,
                    "file_name": os.path.basename(r["file_path"]),
                    "file_url" : "/kb/download/" + os.path.basename(r["file_path"]),
                    "id": r["id"],
                    "vector_id": r["vector_id"],
                    "texts": r["texts"],
                    "file_path": r["file_path"],
                    "create_time": r["create_time"]
                }
                for r in items
            ]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }


    def remove_vector_data(self, db_name: str, vector_id: str) -> int:
        """
        根据 vector_id 删除向量数据
        返回删除的行数
        """
        try:
            with self._connect(db_name) as db:
                cur = db.execute('DELETE FROM vector_data WHERE vector_id = ?', (vector_id,))
                db.commit()
                deleted = cur.rowcount
                print(f"已删除 vector_id={vector_id} 的记录数: {deleted}")
                return deleted
        except Exception as e:
            print(f"删除向量数据失败: {e}")
            raise


    # ---------------- 会话表 ----------------
    def create_session_table(self, db_name: str) -> None:
        """创建会话表，支持多用户"""
        with self._connect(db_name) as db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS session (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_name TEXT NOT NULL,
                    create_time TIMESTAMP DEFAULT (datetime('now', '+8 hours'))
                )
            ''')
            db.commit()

    def add_session(self, db_name: str, user_id: int, session_name: str) -> int:
        """为指定用户创建会话"""
        with self._connect(db_name) as db:
            cur = db.execute(
                "INSERT INTO session (user_id, session_name) VALUES (?, ?)",
                (user_id, session_name),
            )
            db.commit()
            return cur.lastrowid  # 返回自增 id

    def get_sessions(self, db_name: str, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的会话列表"""
        with self._connect(db_name) as db:
            cur = db.execute(
                "SELECT id, session_name, create_time FROM session WHERE user_id = ? ORDER BY create_time DESC",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def delete_session(self, db_name: str, session_id: int) -> int:
        with self._connect(db_name) as db:
            cur = db.execute("DELETE FROM session WHERE id = ?", (session_id,))
            db.commit()
            return cur.rowcount

    # ---------------- 历史对话表 ----------------
    def create_chat_history_table(self, db_name: str) -> None:
        with self._connect(db_name) as db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_id INTEGER NOT NULL,
                    user TEXT NOT NULL,
                    user_content TEXT NOT NULL,
                    assistant TEXT NOT NULL,
                    assistant_content TEXT NOT NULL,
                    create_time TIMESTAMP DEFAULT (datetime('now', '+8 hours')),
                    FOREIGN KEY(session_id) REFERENCES session(id) ON DELETE CASCADE
                )
            ''')
            db.commit()

    def add_chat_message(self, db_name: str, user_id: int, session_id: int, user: str, user_content: str, assistant: str, assistant_content: str) -> int:
        with self._connect(db_name) as db:
            cur = db.execute(
                "INSERT INTO chat_history (user_id, session_id, user, user_content, assistant, assistant_content) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, session_id, user, user_content, assistant, assistant_content)
            )
            db.commit()
            return cur.lastrowid

    def get_chat_messages(self, db_name: str, user_id: int, session_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取某个会话最新 limit 条消息（按时间正序返回，便于展示）"""
        with self._connect(db_name) as db:
            cur = db.execute(
                '''
                SELECT id, session_id, user, user_content, assistant, assistant_content, create_time
                FROM chat_history
                WHERE session_id = ? AND user_id = ?
                ORDER BY create_time DESC
                LIMIT ?
                ''',
                (session_id, user_id, limit)
            )
            rows = [dict(r) for r in cur.fetchall()]
            rows.sort(key=lambda x: x["create_time"])
        messages = []
        for row in rows:
            messages.append((row["user"], row["user_content"]))
            if row["assistant_content"]:
                messages.append((row["assistant"], row["assistant_content"]))
            else:
                messages.append((row["assistant"], "回答出现错误，并没有成功回答用户"))
        return messages

    def delete_chat_message(self, db_name: str, message_id: int) -> int:
        with self._connect(db_name) as db:
            cur = db.execute("DELETE FROM chat_history WHERE id = ?", (message_id,))
            db.commit()
            return cur.rowcount

    # ---------------- 提示词表 ----------------
    def create_prompt_table(self, db_name: str) -> None:
        with self._connect(db_name) as db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS prompt (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    create_time TIMESTAMP DEFAULT (datetime('now', '+8 hours'))
                )
            ''')
            db.commit()

    def add_prompt(self, db_name: str, name: str, content: str) -> int:
        with self._connect(db_name) as db:
            cur = db.execute(
                "INSERT INTO prompt (name, content) VALUES (?, ?)",
                (name, content),
            )
            db.commit()
            return cur.lastrowid

    def get_prompts(self, db_name: str) -> List[Dict[str, Any]]:
        with self._connect(db_name) as db:
            cur = db.execute("SELECT id, name, content, create_time FROM prompt ORDER BY create_time DESC")
            return [dict(r) for r in cur.fetchall()]

    def get_prompt(self, db_name: str, name: str) -> Optional[str]:
        with self._connect(db_name) as db:
            cur = db.execute("SELECT content FROM prompt WHERE name = ?", (name,))
            row = cur.fetchone()
            return row["content"] if row else None

    def delete_prompt(self, db_name: str, name: str) -> int:
        with self._connect(db_name) as db:
            cur = db.execute("DELETE FROM prompt WHERE name = ?", (name,))
            db.commit()
            return cur.rowcount

    # ---------------- 模型配置表 ----------------
    def create_model_config_table(self, db_name: str) -> None:
        with self._connect(db_name) as db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS model_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    base_url TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    max_chunk_len INTEGER DEFAULT 1000,
                    create_time TIMESTAMP DEFAULT (datetime('now', '+8 hours'))
                )
            ''')
            db.commit()

    def add_model_config(self, db_name: str, name: str, base_url: str, model_name: str, api_key: str, max_chunk_len: int = 1000) -> int:
        with self._connect(db_name) as db:
            cur = db.execute(
                "INSERT INTO model_config (name, base_url, model_name, api_key, max_chunk_len) VALUES (?, ?, ?, ?, ?)",
                (name, base_url, model_name, api_key, max_chunk_len),
            )
            db.commit()
            return cur.lastrowid

    def get_model_configs(self, db_name: str) -> List[Dict[str, Any]]:
        with self._connect(db_name) as db:
            cur = db.execute("SELECT id, name, base_url, model_name, api_key, max_chunk_len, create_time FROM model_config ORDER BY create_time DESC")
            return [dict(r) for r in cur.fetchall()]

    def get_model_config(self, db_name: str, name: str) -> Optional[Dict[str, Any]]:
        with self._connect(db_name) as db:
            cur = db.execute("SELECT base_url, model_name, api_key, max_chunk_len FROM model_config WHERE name = ?", (name,))
            row = cur.fetchone()
            return dict(row) if row else None

    def delete_model_config(self, db_name: str, name: str) -> int:
        with self._connect(db_name) as db:
            cur = db.execute("DELETE FROM model_config WHERE name = ?", (name,))
            db.commit()
            return cur.rowcount

# ========== 使用示例（同步版，可直接运行） ==========
def main():
    db = DB("./history")  # 指定数据库目录

    # # 创建向量库副本表
    # db.create_vector_db("knowledge_base")

    # # 插入向量数据
    # db.add_vector_data(
    #     vector_id="id5",
    #     db_name="knowledge_base",
    #     texts="这是一条向量数据",
    #     file_path="file.txt"
    # )

    # # 查询一条
    # item = db.get_vector_data("knowledge_base")
    # print("查询结果：", item)

    # # 删除
    # db.remove_vector_data("knowledge_base", "id2")

    # # 初始化大模型会话表
    # db.create_session_table("session_table")
    # # 初始化大模型历史记录表
    # db.create_chat_history_table("history")

    # # 新建会话
    # sid = db.add_session("session_table", "第三个会话")
    # print("新建会话 id:", sid)
    # sid=1

    # # 插入消息
    # db.add_chat_message(
    # db_name="history",
    # session_id=sid,
    # user="user",
    # user_content="你好",
    # assistant="assistant",
    # assistant_content="你好！我能帮你做点什么？"
    # )
    # db.add_chat_message(db_name="history", session_id=sid, role="assistant", content="你好呀，我能帮你什么？")

    # 获取最新 20 条消息
    msgs = db.get_chat_messages("history", user_id=1, session_id=2, limit=20)
    print("历史消息：", msgs)

#     # 获取所有会话
#     sessions = db.get_sessions("session_table", user_id=1)
#     print("会话列表：", sessions)

if __name__ == "__main__":
    main()
