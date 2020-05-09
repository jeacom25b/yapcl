from contextlib import contextmanager
import inspect
from . errors import ParserError
from . cache import cache_size


class GlobalContext:
    '''
    Class that stores global options and exposes context managers to change global options
    '''
    def __init__(self):
        assert False, 'Cant instantiate this class'

    _global_ignore_parser = None
    current_context = None
    trace_lines = []
    trace_file = None
    trace_code_context=7
    max_trace_lines = 5

    @classmethod
    @contextmanager
    def ignore(cls, *parsers):
        from . combinators import _make_parser
        '''
        to be used as:
        with ignore(whitespace):
            parser_that_ignores_whitespace = seq('foo', 'bar')
        '''
        old_val = cls._global_ignore_parser
        cls._global_ignore_parser = _make_parser(parsers[0]) if len(parsers) == 1 else either(*parsers)
        yield
        cls._global_ignore_parser = old_val

    @classmethod
    @contextmanager
    def trace(cls, code_context=7, max_trace_lines=5):
        '''
        this context manager inspects the stack and gets the file from which its being called.
        it sets this file as a global trace file while the context is active. each time a new parser
        is called, it will check its call stack to see if the file is the same, if so it setups itself to be
        traced by wrapping its function with debug.trace_parser().

        to be used as:
        whith debug_trace():
            parser_to_be_debugged = seq('foo', 'bar')
        '''
        old_lines = cls.trace_lines
        old_val = cls.trace_file
        old_code_context = cls.trace_code_context
        old_max_lines = cls.max_trace_lines
        stack = inspect.stack()
        outer = stack[2]
        cls.trace_lines = []
        cls.trace_file = outer.filename
        cls.trace_code_context = code_context

        yield
        cls.trace_lines = old_lines
        cls.trace_file = old_val
        cls.trace_code_context = old_code_context
        cls.max_trace_lines = old_max_lines

    @classmethod
    @contextmanager
    def context_push(cls):
        '''
        currently not used anywhere
        '''
        old_context = cls.current_context
        cls.current_context = old_context.copy()
        yield
        cls.current_context = old_context

    @classmethod
    def get_context(cls):
        '''
        currently not used anywhere
        '''
        if cls.current_context is None:
            raise ValueError('must push a context before')
        return cls.current_context

    @classmethod
    def make_ignore_fn(cls, ignore_override=None):
        from . combinators import _make_parser
        '''
        checks if there's a global parser to be ignored or if there or takes a parser as input
        produces a parsing function to consume input but not change the result, essentialy
        advancing the element index if there's something matched to ignore.
        '''
        if ignore_override is None:
            ignore_override = cls._global_ignore_parser

        if ignore_override is None:
            return lambda data, string: data

        ignore_fn = _make_parser(ignore_override).func

        def ignore_impl(data, string):
            try:
                return (*data[:2], ignore_fn(data, string)[2])
            except ParserError:
                return data

        return ignore_impl


ignore = GlobalContext.ignore
trace = GlobalContext.trace
context_push = GlobalContext.context_push
get_context = GlobalContext.get_context

__all__ = [
    'cache_size',
    'ignore',
    'trace',
    'context_push',
    'get_context',
]
