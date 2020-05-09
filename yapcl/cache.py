from functools import wraps
from contextlib import contextmanager
from random import random

_curr_cache = None


class CacheStats:
    def __init__(self, query, mapping, size):
        self._query = query
        self._mapping = mapping
        self._size = size

    size = property(fget=lambda self: self._size)
    stats = property(fget=lambda self: {'hits': self._mapping['hits'],
                                        'misses': self._mapping['misses']})

    def erase(self):
        dummy = object()
        self._query.clear()
        self._mapping.clear()
        for i in range(self._size):
            self._query.append((dummy, i))
            self._mapping[(dummy, i)] = (i, i, False)



@contextmanager
def cache_size(size=128):
    global _curr_cache
    old_cache = _curr_cache
    dummy = object()
    mapping = {(dummy, i): (i, i, False) for i in range(size)}
    mapping['hits'] = 0
    mapping['misses'] = 0
    query = [(dummy, i) for i in range(size)]

    _curr_cache = (query, mapping, size)

    yield CacheStats(query, mapping, size)

    _curr_cache = old_cache

def cached(func):
    global _curr_cache
    if not _curr_cache:
        return func

    query, mapping, size = _curr_cache
    size_less_one = size - 1
    m_pop = mapping.pop
    q_get = query.__getitem__
    q_set = query.__setitem__
    m_get = mapping.__getitem__
    m_set = mapping.__setitem__
    minimun = min
    _round = round
    _rand = random

    def miss(key, retval, throw):
        m_set('misses', m_get('misses') + 1)
        rand_val = _rand()
        index = _round(rand_val * rand_val * rand_val * size_less_one)
        old_args = q_get(index)
        m_pop(old_args)
        q_set(index, key)
        m_set(key, (retval, index, throw))
        return retval

    def hit(key):
        m_set('hits', m_get('hits') + 1)
        retval, index, throw = m_get(key)
        index1 = minimun(size_less_one, index + 1)
        v1 = q_get(index1)
        v = q_get(index)
        q_set(index, v1)
        q_set(index1, v)
        m_set(key, (retval, index1, throw))
        if throw:
            raise retval
        return retval

    def wrapper(data, string):
        fid = id(func)
        key = (data[2], id(string), fid)
        if key in mapping:
            return hit(key)

        try:
            return miss(key, func(data, string), False)
        except Exception as e:
            miss(key, e, True)
            raise e

    return wrapper
