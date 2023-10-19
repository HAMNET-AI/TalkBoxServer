import bson
import json
import logging
from sqlalchemy import (
    Column, TIMESTAMP, Integer, String, Text,
    text, BINARY,
    Float, DECIMAL, ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime

B = declarative_base()

class ObjID(BINARY):
    """基于bson.ObjectId用于mysql主键的自定义类型"""
    def bind_processor(self, dialect):
        def processor(value):
            return bson.ObjectId(value).binary if bson.ObjectId.is_valid(value) else value

        return processor

    def result_processor(self, dialect, coltype):
        def processor(value):
            return str(bson.ObjectId(value)) if bson.ObjectId.is_valid(value) else value

        return processor

    @staticmethod
    def new_id():
        return str(bson.ObjectId())

    @staticmethod
    def is_valid(value):
        return bson.ObjectId.is_valid(value)

class Base(B):
    """公共字段"""
    __abstract__ = True
    id = Column(ObjID(12), primary_key=True)
    created = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="创建时间")
    modified = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment="修改时间")
#330000000000000000000000
class Novel(Base):
    """小说表"""
    __tablename__ = 'novel'

    name = Column(String(128), nullable=True, server_default=text("''"), comment="小说名")
    author = Column(String(128), nullable=True, server_default=text("''"), comment="小说作者")
    image = Column(String(256), nullable=True, server_default=text("''"), comment="小说封面")
    index = Column(String(256), nullable=True, server_default=text("''"), comment="小说index文件相对路径")


class People(Base):
    """人物信息表"""
    __tablename__ = 'people'
    novel_id = Column(ObjID(12), ForeignKey('novel.id'), nullable=True, comment="小说ID")
    name = Column(String(128), nullable=True, server_default=text("''"), comment="姓名")
    image = Column(String(256), nullable=True, server_default=text("''"), comment="人物头像")
    index = Column(String(256), nullable=True, server_default=text("''"), comment="人物description文件相对路径")

class ChatLog(Base):
    """对话历史表"""
    __tablename__ = 'chatlog'
    people_id = Column(ObjID(12), ForeignKey('people.id'), nullable=True, comment="人物ID")
    query = Column(String(1024), nullable=True, server_default=text("''"), comment="询问")
    answer = Column(String(1024), nullable=True, server_default=text("''"), comment="回答")

