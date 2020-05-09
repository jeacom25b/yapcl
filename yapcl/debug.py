from . context import GlobalContext
from os import path

def last_file_name(file_path):
    return file_path.split(path.sep)[-1]

def get_string_index_slice(string, index, radius):
    left = string[max(index - radius, 0): index]
    right = string[index: index + radius]
    return ANSI.green + left + ANSI.reset + right, f'{" " * len(left)}{ANSI.yellow}^{index}{ANSI.reset}'

class ANSI:
    '''
    colors defined as escape sequences for fancy output.
    easy to use but dont work on all terminals
    https://en.wikipedia.org/wiki/ANSI_escape_code
    '''

    @classmethod
    def move(cls, x, y):
        if cls.red == '':  # disabled
            return ''
        return f'\u001b[{y};{x}H'

    @classmethod
    def enable(cls):
        cls.red = '\u001b[31m'
        cls.yellow = '\u001b[38;5;221m'
        cls.pink = '\u001b[38;5;213m'
        cls.cyan = '\u001b[38;5;38m'
        cls.green = '\u001b[38;5;112m'
        cls.reset = '\u001b[0m'
        cls.clear = '\u001b[2J'

    @classmethod
    def disable(cls):
        cls.red = ''
        cls.yellow = ''
        cls.pink = ''
        cls.cyan = ''
        cls.green = ''
        cls.reset = ''
        cls.clear = ''


ANSI.enable()


def trace_parser(func, code_context, index, line_no, file):
    '''
    creates an interactive visualization of the parser calls and behaviour
    '''
    trace_lines = GlobalContext.trace_lines
    max_lines = GlobalContext.max_trace_lines

    def print_parser():
        print(repr(func.parser_obj), '\n')
        print(last_file_name(file), ':', line_no)
        for i, line in enumerate(code_context):
            if i == index:
                print(f'{ANSI.green}->>>|' + line.replace('\n', '') + ANSI.reset)
            else:
                print(f'{ANSI.yellow}    |' + line.replace('\n', '') + ANSI.reset)
        print()

    def print_string_index(string, index):
        print(ANSI.clear)  # clear screen
        print(ANSI.move(1, 1))  # move terminal cursor to 0, 0
        string_slice, index_pointer = get_string_index_slice(string, index, 25)
        print(string_slice)
        print(index_pointer)

    def print_trace_lines():
        for line in reversed(trace_lines[-max_lines:]):
            print(line)

    def traced(data, string):
        trace_lines.append(code_context[index].strip()
                           + f'\n{" "*10}{ANSI.green}in {repr(func.parser_obj)}\n{ANSI.reset}')
        print_string_index(string, data[2])
        print_parser()
        print('this parser was called\n')
        print_trace_lines()
        input()
        try:
            data = func(data, string)

        except BaseException as e:
            print_string_index(string, data[2])
            print_parser()
            print('this parser rasised an BaseException\n')
            print(ANSI.red + repr(e) + ANSI.reset + '\n')
            print_trace_lines()
            input()
            trace_lines.pop(-1)
            raise e

        print_string_index(string, data[2])
        print_parser()
        print('this parser returned data\n')
        pretty_print(data)
        print()
        print_trace_lines()
        input()
        trace_lines.pop(-1)
        return data

    return traced


def pretty_print(data, indent='', color=True, print_fn=print):
    '''
    prints a nice tree visualization of the parse data
    '''
    green = ANSI.green
    cyan = ANSI.cyan
    reset = ANSI.reset

    if isinstance(data, list):
        for item in data:
            pretty_print(item, indent=indent + '│   ', color=color, print_fn=print_fn)
        print_fn(indent + '└─────')

    elif isinstance(data, tuple) and len(data) == 3:
        result, tag, index = data
        tag, index = repr(tag), repr(index)

        if isinstance(result, list):
            print_fn(''.join((indent, green, tag, ' [', cyan, index, green, ']:', reset)))
            pretty_print(result, indent=indent, color=color, print_fn=print_fn)

        elif isinstance(result, tuple) and len(result) == 3:
            print_fn(''.join((indent, green, tag, ' [', cyan, index, green, ']:', reset)))
            pretty_print(result, indent=indent + '    ', color=color, print_fn=print_fn)
        else:
            print_fn(''.join((indent, green, tag, ' [', cyan, index, green, ']:', cyan, repr(result), reset)))

    else:
        print_fn(''.join((indent, cyan, repr(data), reset)))


def deep_sizeof(x):
    if isinstance(x, (list, tuple)):
        return sum(deep_sizeof(y) for y in x) + x.__sizeof__()
    else:
        return x.__sizeof__()
