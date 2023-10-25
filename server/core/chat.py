from typing import Dict, List, Tuple
import json
import re
from core.utils import chunk_text_by_max_token, token_str
import pickle
import faiss
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from core.openai_prompt import OpenAI
import asyncio
from dotenv import load_dotenv
import os
 

# 读取 .env file.
load_dotenv()
api_keys = os.getenv('API_KEYS').split(',')

openai = OpenAI(api_keys=api_keys)
OPENAI_API_KEY = api_keys[0]

# 存向量的文件夹
INDEX_PATH = os.path.join(os.getcwd(), 'embedding')
os.makedirs(INDEX_PATH, exist_ok=True)


# 将paragraphs中图标的文本提取出来,整理paragraphs
def format_paragraphs(paragraphs: list) -> List[str]:
    res = []
    for paragraph in paragraphs:
        if isinstance(paragraph, str):
            res.append(paragraph)
        elif isinstance(paragraph, dict):
            res.append(paragraph.get('text', ''))
    return res

# 将文本转换成向量存储
def embedding_paper(json_path: str = '', chunk_size=512):
    json_name = json_path.split('/')[-1].replace('.json', '')
    # 如果已经存在索引文件，则不再重复生成
    if os.path.exists(os.path.join(INDEX_PATH, f"{json_name}.pkl")):
        return
    with open(json_path, 'r',encoding='utf-8') as f:
        data = json.load(f)
    chapters = data['chapter'].copy()
    
    section_id = 0
    infos = []
    metadatas = []
    for chapter in chapters:

        plots = chapter.get('plots', [])
        title = chapter.get('title', '')

        for plot in plots:
            section_id += 1
            text = plot.get('text', '')
            embeddings = plot.get('embeddings', [])
            chunks = chunk_text_by_max_token(text)
            for chunk in chunks:
                infos.append(chunk)
                metadatas.append({
                    'section_id': section_id,
                    'section_title': title,
                    'summary': '\n'.join(embeddings),
                    'text': text,
                    'chunk_text': chunk
                })
            for embedding in embeddings:
                infos.append(embedding)
                metadatas.append({
                    'section_id': section_id,
                    'section_title': title,
                    'summary': '\n'.join(embeddings),
                    'text': text,
                    'chunk_text': embedding
                })

    openaiEmbedding = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

    store = FAISS.from_texts(infos,
                            openaiEmbedding,
                            metadatas=metadatas)
    # 将文本转换成向量
    # aka = OpenAIEmbeddings(openai_api_base="https://api.aios.chat/v1/",openai_api_key=OPENAI_API_KEY)
    #一次性将所有的infos 与 metadatas打包发送，会被限速
    

    # 保存索引文件
    faiss.write_index(store.index,
                    os.path.join(INDEX_PATH, f"{json_name}.index"))
    store.index = None
    with open(os.path.join(INDEX_PATH, f"{json_name}.pkl"), "wb") as f:
        pickle.dump(store, f)

from langchain.chat_models import ChatOpenAI

llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY,
                 temperature=0.9,
                 request_timeout=6000,
                 max_tokens=1000)  # type: ignore


# 将l2距离转换成余弦相似度(因为都是单位向量，所以l2距离和余弦相似度等价)
def l2_distance_to_cosine_similarity(l2_distance):
    return 1 - (l2_distance ** 2) / 2


# 从索引中搜索
def search_query_from_vector_db(json_path,
                                query: str,
                                k: int = 25,
                                chunk_size: int = 512,
                                max_tokens: int = 8000,
                                thereshold: float = 0.6) -> (str, Dict):
    json_name = json_path.split('/')[-1].replace('.json', '')
    # 载入索引文件
    print(os.path.join(INDEX_PATH, f"{json_name}.pkl"))
    if not os.path.exists(os.path.join(
            INDEX_PATH, f"{json_name}.pkl")) or not os.path.exists(
        os.path.join(INDEX_PATH, f"{json_name}.index")):
        raise Exception("索引文件不存在")
    with open(os.path.join(INDEX_PATH, f"{json_name}.pkl"), "rb") as f:
        VectorDBStorePapers: FAISS = pickle.load(f)
    vectorDBIndexPapers = faiss.read_index(
        os.path.join(INDEX_PATH, f"{json_name}.index"))
    VectorDBStorePapers.index = vectorDBIndexPapers
    # 搜索
    search_results = VectorDBStorePapers.similarity_search_with_score(query,
                                                                      k=k)
    res_dict = {}
    for result in search_results:
        doc = result[0]
        score = result[1]
        section_id = doc.metadata['section_id']
        chunk_text = doc.metadata['chunk_text']
        summary = doc.metadata['summary']
        if chunk_text in summary:
            chunk_text = ''
        section_title = doc.metadata['section_title']
        text = doc.metadata['text']
        if section_id not in res_dict:
            res_dict[section_id] = {
                'score':
                    int(l2_distance_to_cosine_similarity(score) * 100) / 100,
                'summary': summary,
                'text': text,
                'section_title': section_title,
                'searched_texts': [chunk_text],
            }
        else:
            searched_texts = res_dict[section_id]['searched_texts']
            if chunk_text not in searched_texts:
                searched_texts.append(chunk_text)
            res_dict[section_id]['score'] = max(
                res_dict[section_id]['score'],
                int(l2_distance_to_cosine_similarity(score) * 100) / 100)
            res_dict[section_id]['searched_texts'] = searched_texts

    # sort the res_dict by score
    res_dict = dict(
        sorted(res_dict.items(),
               key=lambda item: item[1]['score'],
               reverse=True))
    final_text = ''
    for section_id, section in res_dict.items():
        current_format_text = ''
        current_format_text += 'section_title: ' + section[
            'section_title'] + '\n'
        current_format_text += f"section summary: \n{section['summary']}\n"
        current_format_text += 'section text:'
        for searched_text in section['searched_texts']:
            if searched_text != '':
                current_format_text += f"{searched_text}\n"
        current_format_text += '\n'
        if token_str(final_text + current_format_text) > max_tokens:
            break
        final_text += current_format_text
    return final_text, res_dict


async def chat_book(
    openAI_semaphore, 
    parse_json_path: str, 
    role_desc_path: str,
    book_name: str,
    role_name: str,
    query: str
) -> None:
    role_desc = open(role_desc_path, 'r', encoding='utf-8').read()
    if parse_json_path != "":
        # optimized_query = await openai.optimize_query(openAI_semaphore,query)
        # 从索引中搜索
        search_texts, search_results = search_query_from_vector_db(
            parse_json_path, query)

        res = await openai.generate_answer_by_search_results(
            openAI_semaphore, search_texts, query, book_name, role_name,role_desc)

        #print(res)
        return res


#    asyncio.run(main('novels/', "santi", "ye"))
