import inspect
import re
from types import FunctionType
from functools import wraps
from . cache import cached
from . context import GlobalContext
from . errors import ParserError
from . debug import trace_parser


class Discarded:
    def __repr__(self):
        return 'Discarded'


Discarded = Discarded()


def _parser_funcs_unpack(arg, multiple=True):

    if isinstance(arg, Parser):
        return arg.func

    elif isinstance(arg, (list, tuple)) and multiple:
        return [_parser_funcs_unpack(p, multiple=False) for p in arg]

    return _make_parser(arg).func


def _make_parser(obj):
    if isinstance(obj, Parser):
        return obj
    if isinstance(obj, (list, tuple)):
        return seq(*obj)

    elif isinstance(obj, str):
        return lit(obj)

    raise ValueError(f'Invalid parser type {obj}')


def _overridable(method):
    @wraps(method)
    def decorated(self, *args, **kwargs):
        if method.__name__ in self._overrides:
            return self._overrides[method.__name__](self, *args, **kwargs)
        else:
            return method(self, *args, **kwargs)

    decorated.overridable = True

    return decorated


class Parser:

    max_repr_size = 75

    def __init__(self, func):
        self.funcname = func.__name__
        self._overrides = {}
        func.parser_obj = self
        if GlobalContext.trace_file:
            stack = inspect.stack(context=GlobalContext.trace_code_context)
            for frame in stack:
                if frame.filename == GlobalContext.trace_file:
                    code_context = frame.code_context
                    context_line_index = frame.index
                    func = trace_parser(func, code_context, context_line_index, frame.lineno, frame.filename)
        self.func = cached(func)

    repr_str = None

    def set_func(self, func):
        self.func = func

    def parse(self, string):
        data = (None, None, 0)
        return self.func(data, string)

    def override(self, func, name=None):
        if name:
            self._overrides[name] = func
        self._overrides[func.__name__] = func

    def __setattr__(self, k, v):
        if getattr(getattr(self, k, None), 'overridable', False):
            if isinstance(v, FunctionType):
                self.override(v, k)
                return

        object.__setattr__(self, k, v)

    def __repr__(self):
        if '__repr__' in self._overrides:
            string = self._overrides['__repr__'](self)
            if len(string) > self.max_repr_size:
                return re.match(r'[a-zA-Z_0-9]*', string)[0] + '(...)'
            return string
        return object.__repr__(self)

    __repr__.overridable = True

    @_overridable
    def __add__(self, other):
        return seq(self, other)

    @_overridable
    def __radd__(self, other):
        return _make_parser(other).__add__(self)

    @_overridable
    def __sub__(self, other):
        return self.__lshift__(other)

    def __rsub__(self, other):
        return _make_parser(other).__sub__(self)

    @_overridable
    def __or__(self, other):
        return either(self, other)

    @_overridable
    def __ror__(self, other):
        return _make_parser(other).__or__(self)

    @_overridable
    def __rshift__(self, other):
        return seq(self.discard(), other, auto_capture=True)

    @_overridable
    def __lshift__(self, other):
        return seq(self, _make_parser(other).discard(), auto_capture=True)

    @_overridable
    def __rrshift__(self, other):
        return _make_parser(other).__rshift__(self)

    @_overridable
    def __rlshift__(self, other):
        return _make_parser(other).__lshift__(self)

    @_overridable
    def __eq__(self, other):
        return self.tag(other)

    @_overridable
    def __getitem__(self, key):
        if isinstance(key, slice):
            mi = key.start or 0
            ma = key.stop or float('inf')
            return self.many(mi, ma)

        elif isinstance(key, int):
            return self.many(key, key)

        elif isinstance(key, Parser):
            parser = self.leftassoc(key)
            parser.many = lambda self1, mi=0, ma=float('inf'): self.leftassoc(key, mi, ma)
            return parser

        elif isinstance(key, tuple) and len(key) == 2 and isinstance(key[1], type(Ellipsis)):
            parser = sepby(self, key[0])
            parser.many = lambda self1, mi=0, ma=float('inf'): sepby(self, key[0], mi, ma)
            return parser

        else:
            if isinstance(key, tuple):
                key = either(*(_make_parser(x) for x in key))
            else:
                key = _make_parser(key)
            parser = self.leftassoc(key)
            parser.many = lambda self, mi=0, ma=float('inf'): self.leftassoc(key, mi, ma)
            return parser

    @_overridable
    def tag(self, other):
        return tag(self, other)

    @_overridable
    def discard(self, should_discard=True):
        if should_discard:
            return discard(self)

    @_overridable
    def concat(self, other):
        return concat(self, other)

    @_overridable
    def many(self, mi=0, ma=float('inf')):
        return many(self, mi, ma)

    @_overridable
    def sepby(self, separator, mi=0, ma=float('inf')):
        return sepby(self, separator, mi, ma)

    @_overridable
    def leftassoc(self, *parsers, mi=0, ma=float('inf')):
        if len(parsers) == 1:
            return leftassoc(self, parsers[0], mi, ma)
        else:
            return leftassoc(self, either(*parsers), mi, ma)

    @_overridable
    def repeat(self, count):
        return many(self, count, count)

    @_overridable
    def ahead(self, other):
        return lookahead(self, other)

    @_overridable
    def error_message(self, msg):
        return error_message(self, msg)

    @_overridable
    def map(self, func):
        return map(self, func)

    @_overridable
    def result(self, value):
        return self.map(self, lambda result: value)


def regex(pattern):
    pattern = re.compile(pattern)

    @Parser
    def regex_parser(data, string):
        index = data[2]
        match = pattern.match(string, index)
        if match:
            result = match[0]
            return (result, None, index + len(result))
        else:
            raise ParserError(regex_parser, index)

    regex_parser.__repr__ = lambda self: f'regex({repr(pattern.pattern)})'

    return regex_parser


def lit(text):
    le = len(text)

    @Parser
    def literal_parser(data, string):
        index = data[2]
        if string.find(text, index, index + le) == -1:
            raise ParserError(literal_parser, index)
        else:
            return (text, None, index + le)

    literal_parser.__repr__ = lambda self: f'lit({repr(text)})'

    return literal_parser


def either(*parsers):
    funcs = _parser_funcs_unpack(parsers)

    @Parser
    def either_parser(data, string):
        errors = []
        for func in funcs:
            try:
                return func(data, string)
            except ParserError as e:
                errors.append(e.expected)

        raise ParserError(errors, data[2])

    either_parser.__repr__ = lambda self: f'either{parsers}'

    either_parser.__or__ = lambda self, other: either(*parsers, other)

    either_parser.__ror__ = lambda self, other: either(other, *parsers)

    return either_parser


class SeqParser(Parser):
    pass


def seq(*parsers, ignore=None, capture=None, auto_capture=False):
    parsers = tuple(_make_parser(p) for p in parsers)
    funcs = _parser_funcs_unpack(parsers)

    ignore_fn = GlobalContext.make_ignore_fn(ignore)

    @SeqParser
    def sequence_parser(data, string):
        result = []

        data = ignore_fn(data, string)

        for func in funcs:
            data = func(data, string)

            if not data[0] == Discarded:
                result.append(data)

            data = ignore_fn(data, string)

        if auto_capture and len(result) == 1:
            return (*result[0][:2], data[2])

        if capture is not None:
            result, tag, _ = result[capture]
            return (result, tag, data[2])

        return (result, None, data[2])

    sequence_parser.__repr__ = lambda self: f'seq{parsers}'
    sequence_parser.capture = lambda index: seq(*parsers, capture=index)
    sequence_parser.__rshift__ = lambda self, other: seq(
        *parsers[:-1], parsers[-1].discard(True), other, auto_capture=True)
    sequence_parser.__lshift__ = lambda self, other: seq(*parsers, _make_parser(other).discard(), auto_capture=True)
    sequence_parser.__add__ = lambda self, other: seq(*parsers, other, auto_capture=auto_capture)

    return sequence_parser


def many(parser, mi=0, ma=float('inf'), capture=None, ignore=None):
    func = _parser_funcs_unpack(parser, multiple=False)
    ignore_fn = GlobalContext.make_ignore_fn(ignore)

    @SeqParser
    def many_parser(data, string):
        result = []
        error = None

        data = ignore_fn(data, string)

        while len(result) < ma:
            try:
                data = func(data, string)
                if not data[0] == Discarded:
                    result.append(data)

                data = ignore_fn(data, string)

            except ParserError as e:
                error = e
                break

        if len(result) >= mi:
            if capture is not None:
                result, tag, _ = result[capture]
                return (result, tag, data[2])

            return (result, None, data[2])

        if error:
            raise error

        raise ParserError(many_parser, data[2])

    many_parser.__repr__ = lambda self: f'many{parser, mi, ma}'
    many_parser.capture = lambda index: many(parser, mi, ma, capture=index)

    return many_parser


def sepby(parser, separator, mi=0, ma=float('inf'), ignore=None):
    func = _parser_funcs_unpack(parser)
    sep_func = _parser_funcs_unpack(separator)
    ignore_fn = GlobalContext.make_ignore_fn(ignore)

    @Parser
    def sep_parser(data, string):
        error = None
        result = []

        data = ignore_fn(data, string)

        while len(result) < ma:
            try:
                data = func(data, string)
                result.append(data)
                data = ignore_fn(data, string)
                data = sep_func(data, string)
                data = ignore_fn(data, string)

            except ParserError as e:
                error = e
                break

        if len(result) >= mi:
            return (result, None, data[2])

        elif error:
            raise error

        else:
            raise ParserError(sep_parser, data[2])

    sep_parser.__repr__ = lambda self: f'sepby{parser, separator, min, max}'

    return sep_parser


def leftassoc(start, parser, mi=0, ma=float('inf'), ignore=None):
    func_start = _parser_funcs_unpack(start, multiple=False)
    if isinstance(parser, (list, tuple)):
        func = either(*parser).func
    else:
        func = _parser_funcs_unpack(parser)

    ignore_fn = GlobalContext.make_ignore_fn(ignore)

    @Parser
    def lassoc_parser(data, string):
        data = ignore_fn(data, string)
        data = func_start(data, string)

        n = 0
        while n < ma:
            try:
                data = ignore_fn(data, string)

                result, tag, index = func(data, string)
                if not result == Discarded:
                    data = ([data, result], tag, index)
                    n += 1

            except ParserError as e:
                error = e
                break

        data = ignore_fn(data, string)

        if n >= mi:
            return data

        if error:
            raise error
        else:
            raise ParserError(lassoc_parser, data[2])

    lassoc_parser.__repr__ = lambda self: f'leftassoc{start, parser, mi, ma}'

    return lassoc_parser


def concat(*parsers):
    funcs = _parser_funcs_unpack(parsers)
    sequences = [isinstance(p, (SeqParser, list, tuple)) for p in parsers]

    @SeqParser
    def concat_parser(data, string):
        result = []
        for func, is_seq in zip(funcs, sequences):
            data = func(data, string)
            if not data[0] == Discarded:
                if is_seq:
                    result.extend(data[0])

                else:
                    result.append(data)

        return (result, None, data[2])

    concat_parser.__repr__ = lambda self: f'cocnat{parsers}'

    return concat_parser


def map(parser, function):
    func = _parser_funcs_unpack(parser, multiple=False)

    @Parser
    def map_parser(data, string):
        result, tag, index = func(data, string)
        return (function(result), tag, index)

    map_parser.__repr__ = lambda self: f'map{parser, function}'
    return map_parser


def tag(parser, new_tag):
    func = _parser_funcs_unpack(parser, multiple=False)

    @Parser
    def tag_parser(data, string):
        result, tag, index = func(data, string)
        if tag is None:
            return (result, new_tag, index)
        else:
            return ((result, tag, index), new_tag, index)

    # tag_parser.__repr__ = lambda self: f'tag{parser, new_tag}'
    tag_parser.__repr__ = lambda self: f'tag{parser, new_tag}'
    return tag_parser


def discard(parser):
    func = _parser_funcs_unpack(parser, multiple=False)

    @Parser
    def discard_parser(data, string):
        result, tag, index = func(data, string)
        return (Discarded, tag, index)

    discard_parser.__repr__ = lambda self: f'discard({parser})'

    discard_parser.discard = lambda self, should_discard=True: self if should_discard else parser

    return discard_parser


def deepjoin(parser):
    func = _parser_funcs_unpack(parser, multiple=False)

    def join(result):
        if isinstance(result, tuple) and len(result) == 3:
            return join(result[0])

        elif isinstance(result, list):
            return ''.join(join(x) for x in result)

        else:
            return str(result)

    @Parser
    def deepstr_parser(data, string):
        result, tag, index = func(data, string)
        return (join(result), tag, index)

    deepstr_parser.__repr__ = lambda self: f'deepstr_parser({parser})'

    return deepstr_parser


def lookahead(parser1, parser2):
    func1 = _parser_funcs_unpack(parser1, multiple=False)
    func2 = _parser_funcs_unpack(parser2, multiple=False)

    @Parser
    def lookahead_parser(data, string):
        data = func1(data, string)
        func2(data, string)
        return data

    lookahead_parser.__repr__ = lambda self: f'lookahead{parser1, parser2}'

    return lookahead_parser


def fail(expected):

    @Parser
    def fail_aways(data, string):
        raise ParserError(expected, data[2])

    fail_aways.__repr__ = lambda self: f'fail({repr(expected)})'

    return fail_aways


def success(result, tag=None):

    @Parser
    def success_always(data, string):
        return (result, tag, data[2])

    success_always.__repr__ = lambda self: f'success{result, tag}'

    return success_always


def error_message(parser, msg):
    func = _parser_funcs_unpack(parser)

    @Parser
    def error_override(data, string):
        try:
            return func(data, string)
        except ParserError as e:
            e.message = msg
            raise e

    error_override.__repr__ = lambda self: f'success{parser, msg}'

    return error_override


@Parser
def eof(data, string):
    if data[2] >= len(string):
        return (eof, None, data[2])
    else:
        raise ParserError(eof, data[2])


eof.__repr__ = lambda self: 'eof'


@Parser
def copy_last(data, string):
    return data


copy_last.__repr__ = lambda self: 'copy_last'


def token(match_tag):
    @Parser
    def token_parser(data, data_string):
        index = data[2]
        if index >= len(data_string):
            raise ParserError(token_parser, data[2] + 1)

        data_data = data_string[data[2]]
        result, tag, _ = data_data

        if tag is not None and tag == match_tag:
            return (data_data, None, data[2] + 1)

        elif result == tag:
            return (data_data, None, data)

        raise ParserError(token_parser, data[2] + 1)

    token_parser.__repr__ = lambda self: f'token({repr(match_tag)})'
    return token_parser


class RecursionContainer:
    def __init__(self):
        object.__setattr__(self, 'parsers', {})

    def __setattr__(self, k, v):
        if not isinstance(v, Parser):
            raise ValueError(f'invalid type {type(v)}')
        object.__getattribute__(self, 'parsers')[k] = v

    def __getattribute__(self, k):
        parsers = object.__getattribute__(self, 'parsers')
        if k in parsers:
            return parsers[k]

        func = None

        @Parser
        def promissed(data, string):
            nonlocal func
            if func:
                return func(data, string)

            if k in parsers:
                func = parsers[k].func
                return func(data, string)

            raise KeyError(f'parser {k} promissed but never assigned.')

        promissed.__repr__ = lambda self: f'r.{k}'
        return promissed
