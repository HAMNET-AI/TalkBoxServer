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
from core.route import routes,route

from model import ServerModel
from dotenv import load_dotenv
import os

# 读取 .env file.
load_dotenv()
api_keys = os.getenv('API_KEYS')
HOST = os.getenv('HOST')
PORT = os.getenv('PORT')

@route(r"/novel")
class NovelHandler(tornado.web.RequestHandler):
    #get /novel
    def get(self,model: ServerModel = None):
        novels = model.get_novel_list()
        self.finish(

        )


@route(r"/novel/([0-9a-z]{24})")
class CharacterHandler(tornado.web.RequestHandler):
    #get /novel/character
    def get(self,model: ServerModel = None):
        characters = model.get_character_list()
        self.finish(

        )

@route(r"/novel/character/chat")
class ChatHandler(tornado.web.RequestHandler):
    #get /novel/character/chat
    def get(self,model: ServerModel = None):
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






