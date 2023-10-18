import warnings
import os
import json
import logging
import tornado.locale
from copy import deepcopy
from tornado.options import options
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm.collections import InstrumentedList
from sqlalchemy.orm.attributes import QueryableAttribute, InstrumentedAttribute
from sqlalchemy.orm.base import instance_state
from schema import Base, bson


import functools
from copy import deepcopy
from sqlalchemy.orm.base import instance_state
from core.schema import Base, bson
from inspect import getfullargspec, iscoroutinefunction
from tornado.gen import is_coroutine_function
from itertools import zip_longest
from tornado.web import Finish

from exception import *
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 加载i18n
i18n_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'locales')
tornado.locale.load_translations(i18n_path)
tornado.locale.set_default_locale('zh_CN')


class InternalError(Exception):
    """应用层统一的异常"""
    def __init__(self, msg='内部错误', code=-1):
        self.code = code
        self.msg = msg


class ParametersError(InternalError):
    """参数错误"""



def _(text, lang=options.DEFAULT_LOCALE, **kwargs):
    user_locale = tornado.locale.get(lang)
    if '：' in text:
        text = user_locale.translate(text) % kwargs
        return '：'.join([user_locale.translate(t) % kwargs for t in text.split('：')])
    if '\n' in text:
        return '\n'.join([user_locale.translate(t) % kwargs for t in text.split('\n')])
    return user_locale.translate(text) % kwargs


def row2dict(row, lang=''):
    """将对象(一般为orm row)转换为dict"""
    record = {}
    # 清除掉过期状态，强制的跳过state._load_expired(state, passive)
    # 如果有字段确实需要而没有的，要么设置default值，要么使用refresh从数据库拿到server_default值
    state = instance_state(row)
    state.expired_attributes.clear()
    attributes, cls = deepcopy(row.__dict__), row.__class__
    for c in dir(row):
        if hasattr(cls, c):
            a = getattr(cls, c)
            # hybrid_property
            if isinstance(a, QueryableAttribute) and not isinstance(a, InstrumentedAttribute):
                attributes[c] = 1  # 这里只需要有attribute name就可以了

    for c in attributes:
        if not c.startswith('_') and 'metadata' != c:
            try:
                v = row.__getattribute__(c)
            except KeyError as e:  # https://github.com/zzzeek/sqlalchemy/blob/master/lib/sqlalchemy/orm/attributes.py#L579 这个函数可能会raise KeyError出来
                logging.exception(e)
                v = datetime.now() if c in ['created', 'modified'] else None
            if isinstance(v, Base):
                v = row2dict(v, lang=lang)
            elif isinstance(v, Decimal):
                v = int(v)
            # 特殊处理一下生日，以及开始时间结束时间
            elif c in ['start', 'end'] and row.__tablename__ in ['work', 'education']:
                v = v.strftime('%Y-%m')
            elif c in ['birthday'] and row.__tablename__ in ['user']:
                v = v.strftime('%Y-%m-%d')
            elif c in ['account_type'] and row.__tablename__ in ["admin_user"]:
                v = v.split(",")
            elif isinstance(v, datetime):
                v = v.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(v, InstrumentedList):
                v = list(map(lambda i: row2dict(i, lang=lang), v))
            elif isinstance(v, str) and '%' not in v:
                # 翻译字段
                v = _(v, lang=lang)
            record[c] = v

    return record


def format_time(t):
    return t.strftime('%Y-%m-%d %H:%M:%S')


class DateTimeStr(str):

    def __new__(cls, value, **kwargs):
        try:
            return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except Exception as e:
            logging.exception(e)
            raise ParametersError(value)


class DateStr(str):

    def __new__(cls, value, **kwargs):
        try:
            datetime.strptime(value, '%Y-%m-%d')
        except Exception as e:
            logging.exception(e)
            raise ParametersError(value)
        return str(value, **kwargs)


class ObjIDStr(str):

    def __new__(cls, value, **kwargs):
        if not bson.ObjectId.is_valid(value):
            raise ParametersError(value)
        return str(value, **kwargs)


class ExtendJSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj == obj.to_integral_value() else float(obj)
        elif isinstance(obj, datetime):
            return format_time(obj)
        elif isinstance(obj, Base):
            return row2dict(obj)
        elif isinstance(obj, InstrumentedList):
            return [row2dict(i) for i in obj]

        return super(ExtendJSONEncoder, self).default(obj)


def json_encode(value) -> str:
    """JSON-encodes the given Python object."""
    # JSON permits but does not require forward slashes to be escaped.
    # This is useful when json data is emitted in a <script> tag
    # in HTML, as it prevents </script> tags from prematurely terminating
    # the javascript.  Some json libraries do this escaping by default,
    # although python's standard library does not, so we do it here.
    # http://stackoverflow.com/questions/1580647/json-why-are-forward-slashes-escaped
    return json.dumps(value, cls=ExtendJSONEncoder, ensure_ascii=False).replace("</", "<\\/")


def arguments(method):
    """从请求体自动装填被修饰方法的参数，自动类型转换，捕获异常"""
    @functools.wraps(method)
    async def wrapper(self, *args, **kwargs):
        spec = getfullargspec(method)
        filling_args = spec.args[len(args) + 1:]  # 切出需要填充的参数
        default_values = spec.defaults[-len(filling_args):] if spec.defaults else []  # 切出需要的默认值

        # 倒序，参数与默认值对齐
        for key, default in zip_longest(reversed(filling_args), reversed(default_values)):
            if key in kwargs:
                continue
            if key in self._json_args:
                kwargs[key] = self._json_args.get(key)
                continue
            if isinstance(default, list):
                value = self.get_arguments(key, True) or default
            else:
                value = self.get_argument(key, default)
            kwargs[key] = value

        # 根据注解做类型转换
        model_dict = {}
        for key, value in kwargs.items():
            if key not in spec.annotations:
                continue
            annotations = spec.annotations.get(key)
            try:
                from core.base import HandlerContext, BaseModel
                if issubclass(annotations, BaseModel):
                    model = annotations(context=HandlerContext(self))
                    kwargs[key] = model
                    model_dict[key] = model
                elif isinstance(value, list):
                    kwargs[key] = [annotations(item) for item in value if item != '']
                elif value:
                    kwargs[key] = annotations(value)
            except Exception as e:
                logging.warn(e)
                logging.info(f'{key} 字段期待类型为: {str(annotations)} 实际为: "{value}"')
                self.finish({'code': -1, 'msg': '参数错误'})
                return

        try:  # 捕获异常，关闭连接
            if iscoroutinefunction(method) or is_coroutine_function(method):
                response = await method(self, *args, **kwargs)
            else:
                response = method(self, *args, **kwargs)
            return response
        except ParametersError as e:
            logging.warn(e)
            self.finish({'code': -1, 'msg': '参数错误'})
        except (NotFound, Duplicate, PermissionDenied, InternalError) as e:
            self.finish({'code': e.code, 'msg': e.msg})
        except Finish as e:
            raise e
        except Exception as e:
            logging.exception(e)
            self.finish({'code': -1, 'msg': '内部错误'})
        finally:
            for key, model in model_dict.items():
                model.clear()

    return wrapper


