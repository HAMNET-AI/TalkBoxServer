from collections import namedtuple
from core.mysql import get_engine_by_name,get_session_by_name
from sqlalchemy import func, sql
from sqlalchemy.orm.scoping import scoped_session
from tornado.options import options
from tornado.concurrent import run_on_executor
from concurrent.futures import ThreadPoolExecutor

Context = namedtuple("HandlerContext", "current_user")  # example


class ContextMaker:
    """example：model需要的上下文，与RequertHandler解耦"""

    def __call__(self, *args, **kwargs):
        return Context(current_user=None)


class HandlerContextMaker(ContextMaker):
    """接收一个RequertHandler实例，生成用于model的上下文"""

    def __call__(self, handler):
        return Context(current_user=handler.current_user)


# default handler context for model
HandlerContext = HandlerContextMaker()

class BaseModel(object):
    """model基类，约定上下文"""

    def __init__(self, *args, context: Context = None, **kwargs):
        self.context = context
        if context and context.current_user:
            setattr(self, 'current_user', context.current_user)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.clear()

    def clear(self):
        """释放资源"""

class MysqlModel(BaseModel):
    """用于连接mysql的model"""

    executor = ThreadPoolExecutor(10)

    def __init__(self, *args, engine='master', **kwargs):
        self.engine = engine
        super().__init__(*args, **kwargs)

    def _create_session(self, name=None, transaction=True):
        return scoped_session(
            get_session_by_name(
                name or self.engine,
                transaction=transaction,
                expire_on_commit=False,
                autocommit=True,
            ),
            scopefunc=lambda: self
        )

    @property
    def session(self):
        if not hasattr(self, '_session'):
            self._session = self._create_session()
        return self._session

    @property
    def slave_session(self):
        """slave_session从slaves连接池中选一个，只作为查询"""
        if not hasattr(self, '_slave_session'):
            self._slave_session = self._create_session(name="slaves", transaction=False)
        return self._slave_session

    @run_on_executor
    def query_one(self, query):
        """查询一条记录"""
        return query.with_session(
            self.slave_session()
        ).first()

    @run_on_executor
    def query_all(self, query):
        """查询所有"""
        return query.with_session(self.slave_session()).all()

    @run_on_executor
    def query_total(self, query):
        """查询总数"""
        if getattr(query, "_limit", None):
            return int(query.with_entities(
                sql.literal_column('1')
            ).with_session(self.slave_session()).count() or 0)
        if getattr(query, "_group_by", None):
            return int(query.with_entities(
                sql.literal_column('1')
            ).order_by(None).with_session(self.slave_session()).count() or 0)
        return int(self.slave_session.execute(
            query.with_labels().statement.with_only_columns(
                func.count(1)
            ).order_by(None)
        ).scalar() or 0)

    def clear(self):
        """释放连接"""
        if hasattr(self, '_session'):
            self._session.remove()
        if hasattr(self, '_slave_session'):
            self._slave_session.remove()
        super().clear()

    def copy_obj(self, obj, extra=dict(), autocommit=True):
        doc = {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
        doc.update(extra)
        newobj = obj.__class__(**doc)
        self.session.add(newobj)
        if autocommit:
            self.session.commit()
        return newobj.id