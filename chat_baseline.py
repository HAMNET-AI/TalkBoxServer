from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.faiss import FAISS
from langchain.vectorstores.utils import DistanceStrategy
from langchain.text_splitter import CharacterTextSplitter

from dotenv import load_dotenv
import os, json
import pickle
import faiss
import litellm
from typing import Tuple, List
PARSE_FOLDER_PATH = os.path.join(os.getcwd(), 'parse_res')

# 读取 .env file.
load_dotenv()
openai_api_key= os.getenv('LITELLM_OPENAI_API_KEY')
openai_api_base= os.getenv('LITELLM_OPENAI_API_BASE')
INDEX_PATH = os.path.join(os.getcwd(), 'embedding')
litellm.api_base=openai_api_base
litellm.api_key=openai_api_key

class BaselineChat:
    EXTRA_NAME = 'baseline'
    def __init__(self,novel_path: str,book_name: str,role: str):
        self.novel_path = novel_path
        self.book_name = book_name
        self.role = role
        self.json_name = self.novel_path.split('/')[-1].split('.')[0]
        self.FILE_NAME=f"{self.json_name}_{self.EXTRA_NAME}"
        if not os.path.exists(self.novel_path):
            raise Exception("原文不存在")
        self.knowledge_base = self._init_index()
        self.messages = [self._system_message()]
        return
    
    def _system_message(self):
        with open('novels/叶文洁.txt', 'r') as f:
            content = f.read()
        return {'role': 'system', 'content':
            f"""
        I want you to act like {self.role} from {self.book_name}.
        Answer in user's language as concisely as possible.
        The following is information about {self.role}, please follow the instructions below to extract and expand only the description of the role
         {content}"""}

    def _init_index(self):
        if not os.path.exists(os.path.join(
            INDEX_PATH, f"{self.json_name}_{self.EXTRA_NAME}.pkl")) or not os.path.exists(
                os.path.join(INDEX_PATH, f"{self.json_name}_{self.EXTRA_NAME}.index")):
            # 重新构建索引
            print('重新构建知识库中')
            raw_text = self._get_raw_text()
            chunks = self._chunks(raw_text)
            knowledge_base = self._construct_index(chunks)
            print('构建知识库完成')
            return knowledge_base
        else:
            with open(os.path.join(INDEX_PATH, f"{self.FILE_NAME}.pkl"), "rb") as f:
                knowledge_base: FAISS = pickle.load(f)
                print('加载知识库完成')
                return knowledge_base


    def _get_raw_text(self):
        # 如果已经存在索引文件，则不再重复生成
        with open(self.novel_path, 'r') as f:
            content=f.read()
        return content
    
    def _chunks(self, raw_text):
        text_splitter = CharacterTextSplitter(
                separator="\n",
                chunk_size=500,
                chunk_overlap=200,
                length_function=len
            )
        chunks = text_splitter.split_text(str(raw_text))
        return chunks

    

    def _construct_index(self, chunks: List[str]):
        embedding = OpenAIEmbeddings(openai_api_key=openai_api_key,
                    openai_api_base=openai_api_base)
        knowledge_base= FAISS.from_texts(
            texts = chunks,
            embedding=embedding,
            distance_strategy=DistanceStrategy.COSINE
        )
        faiss.write_index(knowledge_base.index,
                      os.path.join(INDEX_PATH, f"{self.FILE_NAME}.index"))
        
        with open(os.path.join(INDEX_PATH, f"{self.FILE_NAME}.pkl"), "wb") as f:
            pickle.dump(knowledge_base, f)
        return knowledge_base

    def search_related_knowledges(self, query: str):
        result = self.knowledge_base.similarity_search_with_score(query=query, k=20,score_threshold=0.9)
        result_dict = [{"document": doc.page_content, "score": float(score)} for doc, score in result]
        record_dict = {
            "query":query,
            "search_results":result_dict
        }
        search_res_path = os.path.join(PARSE_FOLDER_PATH,
                                           f'baseline_search_results.json')
        json.dump(
                record_dict,
                open(search_res_path, 'w'),
                indent=4,
                ensure_ascii=False)
        return [item.page_content for item, score in result]
    

    def chat(self, input:str):
        full_response = ''
        msgs = self.messages.copy()
        msgs.append({'role':"user", 'content':input})
        # print(self.conversation[convo_id])
        response = litellm.completion(model="gpt-3.5-turbo-16k-0613", messages=msgs, stream=True)
        for chunk in response:
            try:
                chunk_content = chunk['choices'][0]['delta'].content
                # print(chunk['choices'][0])
                chunk_content = chunk_content.replace('\n', '<br>')
                if not chunk_content.endswith('content'):
                    full_response += chunk_content
                    print(chunk_content, end="")
            except Exception as e:
                break

            if chunk['choices'][0]['finish_reason'] == "stop":
                break

        return full_response
    
    def chat_main(self):
        while True:
            query = input("请输入查询问题: \n")
            self.messages.append({'role':"user", 'content':query})
            search_texts = self.search_related_knowledges(query)
            prompt = f"""
- {self.book_name} 中的相关节选：{'<br>'.join(search_texts)}
- 用户问题：{query}
You are now cosplay {self.role} to answer the user's question.
If others‘ questions are related with the novel, please try to reuse the original lines from the novel.
I want you to respond and answer like {self.role} using the tone, manner and vocabulary {self.role} would use. 
You must know all of the knowledge of {self.role}.
Never say you are playing {self.role} , you just know the answer because you are {self.role}.
Be sure to speak naturally.
"""
            full_response = self.chat(prompt)
            self.messages.append({'role':'assistant',"content":full_response})
            print("")


    def chat_for_test(self, inputs: List[str]):
        return [(inputs[i], self.chat(inputs[i])) for i in range(len(inputs))]



if __name__ == '__main__':
    baseline_chat= BaselineChat('novels/三体I：地球往事.txt',book_name='三体I：地球往事', role='叶文洁')
    baseline_chat.chat_main()