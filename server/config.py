from os.path import dirname, join, isfile
from tornado.options import define, parse_config_file


def load_config():
    define('DEBUG', default=True)
    define('SERVER_PORT', default=9999)
    define('A',default=1)
    define("MYSQL", default={
        "master": "mysql+pymysql://root:1662326564gsh@mysql:3306/talk_box?charset=utf8",
        "slaves": [
           "mysql+pymysql://root:1662326564gsh@mysql:3306/talk_box?charset=utf8",
        ]
    })

    root_path = dirname(dirname(__file__))

    config_file = join(root_path, "etc", "web_config.conf")
    if isfile(config_file):
        parse_config_file(config_file)



