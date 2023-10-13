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


from model import ServerModel, AdminModel
from flask import Flask     #导入Flask模块
from dotenv import load_dotenv
import os

# 读取 .env file.
load_dotenv()
api_keys = os.getenv('API_KEYS')
HOST = os.getenv('HOST')
PORT = os.getenv('PORT')

print(api_keys)
#创建Flask的实例对象
app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello World!'

@app.route('/novel')
def hello_world():
    return 'Hello World!'

class NovelHandler(tornado.web.RequestHandler):
    #get /novel
    def get(self,model: ServerModel = None):
        novels = model.get_novel_list()


if __name__ == '__main__':
    app.run(port=PORT,host=HOST)





