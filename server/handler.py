import logging
import json

import tornado.log
import tornado.web
import tornado.ioloop
import tornado.autoreload
import tornado.httpserver
from tornado.options import options, parse_command_line
from core.route import routes, route
from core.utils import *


from dotenv import load_dotenv
import os
from model import ServerModel
# 读取 .env file.
load_dotenv()
api_keys = os.getenv('API_KEYS')
HOST = os.getenv('HOST')
PORT = os.getenv('PORT')
        
@route(r"/novel")
class NovelHandler(tornado.web.RequestHandler):
    _json_args = {}
    # get /novel
    @arguments
    async def get(
        self,
        model: ServerModel = None
    ):
        novels, total = await model.get_novel_list()
        self.finish({
            "code": 0,
            "msg": "success",
            "total": total,
            "data": [
                {
                    "id": novel["id"],
                    "name": novel["name"],
                    "author": novel["author"],
                    "image": novel["image"]

                } for novel in novels
            ]
        })
        

@route(r"/novel/([0-9a-z]+)")
class CharacterHandler(tornado.web.RequestHandler):
    _json_args = {}
    # get /novel/{novel_id}
    @arguments
    async def get(
        self,
        novel_id: str = "",
        model: ServerModel = None
    ):
        characters, total = await model.get_character_list(novel_id)
        self.finish({
            "code": 0,
            "msg": "success",
            "total": total,
            "data": [
                {
                    "character_id": character["id"],
                    "name": character["name"],
                    "image": character["image"]

                } for character in characters
            ]
        })


@route(r"/novel/character/([0-9a-z]+)")
class ChatHandler(tornado.web.RequestHandler):
    _json_args = {}
    # get /novel/character/{character_id}
    @arguments
    async def get(
        self,
        character_id: str = "",
        model: ServerModel = None
    ):
        info, chatlogs, total =await model.get_character_info(character_id)
        self.finish({
            "code": 0,
            "msg": "success",
            "total": total,
            "name": info["name"],
            "image": info["image"],
            "chatlog": [
                {
                    "query": chatlog["query"],
                    "answer": chatlog["answer"],
                } for chatlog in chatlogs
            ]
        })


@route(r"/novel/character/chat")
class ChatHandler(tornado.web.RequestHandler):
    _json_args = {}
    # post /novel/character/chat
    @arguments
    async def post(
        self,
        query: str = "",
        character_id: str = "",
        model: ServerModel = None
    ):
        answer = model.chat(query,character_id)
        self.finish({
            "code": 0,
            "msg": "success",
            "data": [{
                "content": answer
            }]
        })


if __name__ == "__main__":

    application = tornado.web.Application(routes(), **dict(
        debug=True,
    ))
    server = tornado.httpserver.HTTPServer(application)
    server.listen(port=PORT)
    server.start()
    logging.info("Start Success: 0.0.0.0:{}".format(PORT))

    tornado.ioloop.IOLoop.instance().start()
