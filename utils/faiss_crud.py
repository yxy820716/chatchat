from langchain_ollama import OllamaEmbeddings
import sys
import uuid
import shutil
import asyncio

sys.path.insert(0, r"../../")
from chatchat.configs.setting import get_config
import faiss
import os
import shutil
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from chatchat.dataset.db_crud import DB
from chatchat.utils.markdown_utils import binary_split
ollama_args=get_config("configs/Model_Config.yaml")
faiss_args=get_config("configs/Kb_Config.yaml")


class FAISS_CURD:
    def __init__(self):
        self.embedding_model = OllamaEmbeddings(
            model = ollama_args["EMBEDDING_MODEL"],
            base_url = ollama_args["EMBEDDING_URL"]
        )
    def get_vector(self,faiss_name):
        self.vectorstore = FAISS.load_local(
        faiss_name, self.embedding_model, allow_dangerous_deserialization=True
        )
        return self.vectorstore
    def add_vector(self,faiss_name,texts,file_path):
        faiss_name=faiss_args["KB_PATH"]+faiss_name
        vectorstore = self.get_vector(faiss_name)

        document = [Document(page_content=i, metadata={"file_path":file_path}) for i in texts]
        uuids = [str(uuid.uuid4()) for _ in range(len(document))]
        vectorstore.add_documents(document,ids=uuids)
        vectorstore.save_local(faiss_name)
        Vector_DB=DB(faiss_name)
        [
            Vector_DB.add_vector_data(vector_id=uuids[i], db_name="knowledge_base", texts=texts[i], file_path=file_path) 
            for i in range(len(uuids))
        ]
    def revome_kb(self,index_name):
        index_name=faiss_args["KB_PATH"]+index_name
        shutil.rmtree(index_name)
    
    def revome_vector(self,index_name,ids):
        faiss_name=faiss_args["KB_PATH"]+index_name
        vectorstore = self.get_vector(faiss_name)
        if vectorstore.delete(ids=ids):
            vectorstore.save_local(faiss_name)
            Vector_DB=DB(faiss_name)
            [
                Vector_DB.remove_vector_data(db_name = "knowledge_base",vector_id=i)
                for i in ids
            ]
        else:
            print("删除失败")


    import math

    def search_vector(self, index_name: str, query: str, max_len: int | None = None):
        """
        在向量库中搜索相似文本，返回 JSON（含内容、metadata、相似度分数 0~1）
        """
        index_name = faiss_args["KB_PATH"] + index_name
        vectorstore = self.get_vector(index_name)

        # 获取 (Document, 距离)
        results = vectorstore.similarity_search_with_score(
            query,
            k=faiss_args["TOP-K"]
        )

        output = []
        for doc, distance in results:
            similarity = float(1 / (1 + distance))
            contents = [doc.page_content]
            if max_len:
                contents = binary_split(doc.page_content, max_len)
            for c in contents:
                output.append({
                    "content": c,
                    "metadata": doc.metadata,
                    "score": similarity,
                })
        return output
    

    def mkdir_faiss(self, index_name):
        index_name = faiss_args["KB_PATH"] + index_name
        # 确保目录存在
        os.makedirs(index_name, exist_ok=True)
        
        index = faiss.IndexFlatL2(len(self.embedding_model.embed_query("hello world")))
        vectorstore = FAISS(
            embedding_function=self.embedding_model,
            index=index,
            docstore=InMemoryDocstore(),
            index_to_docstore_id={},
        )
        vectorstore.save_local(index_name)
        Vector_DB=DB(index_name)
        Vector_DB.create_vector_db("knowledge_base")
        return vectorstore


if __name__ == "__main__":

    # 创建向量库
    faiss_curd=FAISS_CURD()
    # faiss_curd.mkdir_faiss("cs")
    # # 向向量库添加文档
    # faiss_curd.add_vector("cs",["你好","我好","大家好"],"test.txt")
    # 搜索向量库
    # answer=faiss_curd.search_vector("cs1","工作站")
    # print(answer)
    # # 删除向量库
    # faiss_curd.revome_kb("ce")
    # # 删除知识库单条向量
    # faiss_curd.revome_vector("cs",['09b39256-24bb-4269-bafe-b24fe0a9e7cd'])


