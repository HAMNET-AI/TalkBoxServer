from core.utils import row2dict
from sqlalchemy import func, sql
from core.base import MysqlModel
from core.schema import *
    

class ServerModel(MysqlModel):

    def get_novel_list(self):
        novels = self.session.query(Novel)
        total = novels.count()
        
        if total == 0:
            return [], 0
        return [row2dict(item) for item in self.query_all(novels)], total

    def get_character_list(self,novel_id):
        characters = self.session.query(Character).filter(
            Character.novel_id==novel_id
        )
        total = characters.count()
        
        if total == 0:
            return [], 0
        return [row2dict(item) for item in self.query_all(characters)], total

    def get_character_info(self,character_id):
        character = self.session.query(Character).filter(
            Character.id==character_id
        ).first()

        chatlogs = self.session.query(ChatLog).filter(
            ChatLog.character_id==character_id
        )

        total = chatlogs.count()
        return row2dict(character),[row2dict(item) for item in self.query_all(chatlogs)], total