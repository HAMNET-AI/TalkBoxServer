import asyncio
import logging
import json

import tornado.log
import tornado.web
import tornado.ioloop
import tornado.autoreload
import tornado.httpserver
from os.path import abspath, dirname, join
from tornado.options import options, parse_command_line
from core.route import routes, route
from core.utils import *
from model import ServerModel
from dotenv import load_dotenv
import os

import core.mysql

# 读取 .env file.
load_dotenv()
api_keys = os.getenv('API_KEYS')
HOST = os.getenv('HOST')
PORT = os.getenv('PORT')


@route(r"/novel")
class NovelHandler(tornado.web.RequestHandler):
    # get /novel
    def get(
        self,
        model: ServerModel = None
    ):
        novels, total = model.get_novel_list()
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


@route(r"/novel/([0-9a-z]{24})")
class CharacterHandler(tornado.web.RequestHandler):
    # get /novel/{novel_id}
    def get(
        self,
        novel_id: ObjIDStr = "",
        model: ServerModel = None
    ):
        characters, total = model.get_character_list(novel_id)
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

                } for novel in characters
            ]
        })


@route(r"/novel/character/([0-9a-z]{24})")
class ChatHandler(tornado.web.RequestHandler):
    # get /novel/character/{character_id}
    def get(
        self,
        character_id: ObjIDStr = "",
        model: ServerModel = None
    ):
        info, chatlogs, total = model.get_character_info(character_id)
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
    # get /novel/character/chat
    def post(self, model: ServerModel = None):
        characters = model.get_character_list()
        self.finish(

        )


if __name__ == "__main__":

    application = tornado.web.Application(routes(), **dict(
        debug=options.DEBUG,
    ))
    server = tornado.httpserver.HTTPServer(application)
    server.listen(port=options.SERVER_PORT)
    server.start()
    logging.info("Start Success: 0.0.0.0:{}".format(options.SERVER_PORT))

    tornado.ioloop.IOLoop.instance().start()
