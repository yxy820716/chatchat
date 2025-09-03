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
        with self._connect(db_name) as db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS session (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_name TEXT NOT NULL,
                    create_time TIMESTAMP DEFAULT (datetime('now', '+8 hours'))
                )
            ''')
            db.commit()

    def add_session(self, db_name: str, session_name: str) -> int:
        with self._connect(db_name) as db:
            cur = db.execute(
                "INSERT INTO session (session_name) VALUES (?)",
                (session_name,)
            )
            db.commit()
            return cur.lastrowid  # 返回自增 id

    def get_sessions(self, db_name: str) -> List[Dict[str, Any]]:
        with self._connect(db_name) as db:
            cur = db.execute(
                "SELECT id, session_name, create_time FROM session ORDER BY create_time DESC"
            )
            return [dict(r) for r in cur.fetchall()]
    
    def update_session_name(self, db_name: str, session_id: int, new_name: str) -> bool:
        """
        根据 id 更新 session 表里的 session_name。
        返回 True 表示确实更新了行，False 表示未更新（可能 id 不存在或新旧名称相同）。
        """
        with self._connect(db_name) as db:
            cur = db.execute(
                "UPDATE session SET session_name = ? WHERE id = ?",
                (new_name, session_id)
            )
            db.commit()
            return cur.rowcount > 0

    def delete_session(self, db_name: str, session_id: int) -> int:
        with self._connect(db_name) as db:
            cur = db.execute("DELETE FROM session WHERE id = ?", (session_id,))
            db.commit()
            return cur.rowcount
        
    def delete_sessions(self, db_name: str) -> int:
        with self._connect(db_name) as db:
            cur = db.execute("DELETE FROM session")
            db.commit()
            return True

    # ---------------- 历史对话表 ----------------
    def create_chat_history_table(self, db_name: str) -> None:
        with self._connect(db_name) as db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    def add_chat_message(self, db_name: str, session_id: int, user: str, user_content: str, assistant: str, assistant_content: str) -> int:
        with self._connect(db_name) as db:
            cur = db.execute(
                "INSERT INTO chat_history (session_id, user, user_content, assistant, assistant_content) VALUES (?, ?, ?, ?, ?)",
                (session_id, user, user_content, assistant, assistant_content)
            )
            db.commit()
            return cur.lastrowid

    def get_chat_messages(self, db_name: str, session_id: int, limit: int = 20, get_id=False) -> List[Dict[str, Any]]:
        """获取某个会话最新 limit 条消息（按时间正序返回，便于展示）"""
        with self._connect(db_name) as db:
            cur = db.execute(
                '''
                SELECT id, session_id, user, user_content, assistant, assistant_content, create_time
                FROM chat_history
                WHERE session_id = ?
                ORDER BY create_time DESC
                LIMIT ?
                ''',
                (session_id, limit)
            )
            rows = [dict(r) for r in cur.fetchall()]
            # 倒序取出的，再按时间正序还原对话流
            rows.sort(key=lambda x: x["create_time"])
        messages = []
        for row in rows:
            # 用户问题
            
            # AI回答
            if row["assistant_content"] and get_id==False:  # 防止为空
                messages.append((row["user"],row["user_content"]))
                messages.append((row["assistant"],row["assistant_content"]))
            elif row["assistant_content"] and get_id==True:
                messages.append({row["user"]:row["user_content"],row["assistant"]:row["assistant_content"],"message_id":row["id"]})
            else:
                messages.append((row["user"],row["user_content"]))
                messages.append((row["assistant"],"回答出现错误，并没有成功回答用户"))
        return messages

    def delete_chat_message(self, db_name: str, message_id: int) -> int:
        with self._connect(db_name) as db:
            cur = db.execute("DELETE FROM chat_history WHERE id = ?", (message_id,))
            db.commit()
            return cur.rowcount


# ========== 使用示例（同步版，可直接运行） ==========
# def main():
    # db = DB("./history")  # 指定数据库目录

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
    # msgs = db.get_chat_messages("history", 2, limit=20)
    # print("历史消息：", msgs)
    # db.delete_chat_message("history","")
#     # 获取所有会话
#     sessions = db.get_sessions("session_table")
#     print("会话列表：", sessions)

# if __name__ == "__main__":
#     main()
