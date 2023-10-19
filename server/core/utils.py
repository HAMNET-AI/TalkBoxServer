import json
import logging
import functools
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm.collections import InstrumentedList
from sqlalchemy.orm.attributes import QueryableAttribute, InstrumentedAttribute
from sqlalchemy.orm.base import instance_state
from core.schema import Base, bson
from inspect import getfullargspec, iscoroutinefunction
from tornado.gen import is_coroutine_function
from itertools import zip_longest
from core.exception import ParametersError, NotFound, InternalError, Duplicate, PermissionDenied
from tornado.web import Finish


def row2dict(row):
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
                v = row2dict(v)
            if isinstance(v, Decimal):
                v = int(v)
            # 特殊处理一下生日，以及开始时间结束时间
            if c in ['start', 'end'] and row.__tablename__ in ['work', 'education']:
                v = v.strftime('%Y.%m')
            if c in ['birthday'] and row.__tablename__ in ['user']:
                v = v.strftime('%Y.%m.%d')
            if isinstance(v, datetime):
                v = v.strftime('%Y.%m.%d %H:%M:%S')
            if isinstance(v, InstrumentedList):
                v = list(map(lambda i: row2dict(i), v))
            record[c] = v

    return record


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


import tiktoken
import aiofiles
import hashlib
from typing import List
import re


ENCODER = tiktoken.get_encoding("cl100k_base")


def token_str(content: str) -> int:
    return len(ENCODER.encode(content))


async def get_pdf_md5(pdf_file_path: str) -> str:
    async with aiofiles.open(pdf_file_path, 'rb') as f:
        file_content = await f.read()
    pdf_md5 = hashlib.md5(file_content).hexdigest()
    return pdf_md5


def chunk_text_by_max_token(text: str, max_token=512) -> List[str]:
    if token_str(text) <= max_token:
        return [text]
    res = []
    num_split = token_str(text) // max_token
    # 切分的步长
    steps = [400, 200, 100]
    # 搜索标点符号正则
    punctuation = r'(?<!\d)([。？！…?!]|\.(?=\s))(?!\d)'
    while len(text) > 0:
        split_pos = 0
        while split_pos < len(text):
            for step in steps:
                next_step = min(step, len(text) - split_pos)
                temp_text = text[:split_pos + next_step]
                if token_str(temp_text) <= max_token:
                    split_pos += next_step
                    break
            else:
                break
        # 搜索最后一个标点符号
        search_res = re.search(punctuation, text[:split_pos][::-1])
        if search_res:
            split_pos = split_pos - int(search_res.end()) + 1
        res.append(text[:split_pos])
        text = text[split_pos:]
    return res

def chunk_list_by_max_token(paragraphs: List[str], max_token=512) -> List[str]:
    res = []
    temp_text = ''
    for paragraph in paragraphs:
        if token_str(paragraph) > max_token:
            res.extend(chunk_text_by_max_token(paragraph, max_token))
        elif token_str(temp_text + paragraph) > max_token:
            res.append(temp_text)
            temp_text = paragraph + '\n'
        else:
            temp_text += paragraph + '\n'
    return res

from langid.langid import LanguageIdentifier, model
lang_identifier = LanguageIdentifier.from_modelstring(model, norm_probs=True)
import uuid

def get_uuid()->str:
    return str(uuid.uuid4())

def detect_language(text: str) -> str:
    lang, _ = lang_identifier.classify(text)
    # print(lang)
    # chinese_characters = sum(1 for character in text if '\u4e00' <= character <= '\u9fff')
    # percentage = chinese_characters / len(text) * 100
    # if percentage > threshold:
    #     return 'zh'
    return lang


def is_english(text: str) -> bool:
    try:
        return detect_language(text) == 'en'
    except:
        return False
    
def check_language(language: str, text: str):
    if language != 'English' and is_english(text):
        raise Exception(f"The summary is not {language}")
    elif language == 'English' and not is_english(text):
        raise Exception(f"The summary is not {language}")

