from core.utils import row2dict
from sqlalchemy import func, sql
from core.base import MysqlModel
from core.schema import *
from core.chat import *

class ServerModel(MysqlModel):

    async def get_novel_list(self):
        novels = self.session.query(Novel)
        total = novels.count()
        
        if total == 0:
            return [], total
        #return [row2dict(item) for item in novels.all()], total
        return [row2dict(item) for item in novels.all()], total

    async def get_character_list(self,novel_id):
        characters = self.session.query(People).filter(
            People.novel_id==novel_id
        )
        total = characters.count()
        
        if total == 0:
            return [], 0
        return [row2dict(item) for item in characters.all()], total

    async def get_character_info(self,character_id):
        character = self.session.query(People).filter(
            People.id==character_id
        )

        chatlogs = self.session.query(ChatLog).filter(
            ChatLog.people_id==character_id
        )

        total = chatlogs.count()
        #query_all 出错
        #return row2dict(character),[row2dict(item) for item in self.query_all(chatlogs)], total
        return [row2dict(item) for item in character.all()],[row2dict(item) for item in chatlogs.all()], total
    
    async def chat(self,query,character_id):
        import asyncio

        openai.openAIAPI.lock = asyncio.Lock()
        openAI_semaphore = asyncio.Semaphore(50)
        #     asyncio.run(main('novels/', "santi", "ye"))

        answer = await chat_book(openAI_semaphore, 'novels/santi.json', 'novels/ye.txt', 'santi', 'ye', query)

        print(answer)
        return answer
    
