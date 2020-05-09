from yapcl.combinators import regex, either, RecursionContainer, eof
from yapcl.debug import pretty_print
from yapcl.context import trace, ignore, cache_size


with trace():
    with cache_size(10):
        whitespace = regex(r'\s+')
    integer = regex(r'\d+') == 'int'
    float_val = regex(r'\d+\.\d+') == 'float'
    id = regex('[a-zA-Z_]+[a-zA-Z_0-9]*') == 'id'

    r = RecursionContainer()
    value = either(float_val, integer, r.funccall, id, r.parenthesis)

    with ignore(whitespace):
        value = ('-' >> value == 'negate') | value

        factor = value[
            '*' >> value == 'mul',
            '/' >> value == 'div',
        ]

        term = factor[
            '+' >> factor == 'add',
            '-' >> factor == 'sub',
        ]

        r.parenthesis = '(' >> term << ')'
        paramlist = id.sepby(',') == 'paramlist'

        funcdef = id << '(' >> paramlist << ')' << '=' >> term == 'funcdef'

        arglist = term.sepby(',') == 'arglist'

        r.funccall = id << '(' >> arglist << ')' == 'funccall'

main_parser = either(funcdef, term) << eof.error_message('unexpected token')

RESULT = 0
TAG = 1
INDEX = 2


def interpret(tree, arguments=None, functions=None):
    tag = tree[TAG]
    result = tree[RESULT]

    if tag == 'add':
        return interpret(result[0], arguments, functions) + interpret(result[1], arguments, functions)
    elif tag == 'sub':
        return interpret(result[0], arguments, functions) - interpret(result[1], arguments, functions)
    elif tag == 'mul':
        return interpret(result[0], arguments, functions) * interpret(result[1], arguments, functions)
    elif tag == 'div':
        return interpret(result[0], arguments, functions) / interpret(result[1], arguments, functions)
    elif tag == 'negate':
        return interpret(result, arguments, functions) * -1
    elif tag == 'int':
        return int(result)
    elif tag == 'float':
        return float(result)
    elif tag == 'id':
        if arguments and result in arguments:
            return arguments[result]
        else:
            raise NameError(result)
    elif tag == 'funcdef':
        func = FunctionDefinition(tree)
        pretty_print(tree)
        print('function definition processed sucessfully')
        functions[func.name] = func
        return ''
    elif tag == 'funccall':
        name = result[0][RESULT]
        if functions and name in functions:
            return functions[name].call(tree, arguments, functions)
        else:
            raise NameError(name)


class FunctionDefinition:
    def __init__(self, tree):
        result = tree[RESULT]

        self.name = result[0][RESULT]
        self.params = [name[RESULT] for name in result[1][RESULT]]
        self.tree = result[2]

    def call(self, tree, arguments, functions):
        result = tree[RESULT]
        arglist = result[1][RESULT]
        if not len(arglist) == len(self.params):
            raise ValueError(f'wrong number of parameters in call to {self.name}({", ".join(self.params)})')

        arguments_new = {}
        for arg_name, arg_tree in zip(self.params, arglist):
            arguments_new[arg_name] = interpret(arg_tree, arguments, functions)

        return interpret(self.tree, arguments_new, functions)


if __name__ == '__main__':
    functions = {}
    while 1:
        try:
            arguments = {}
            print(interpret(main_parser.parse(input('maths :) >>')), arguments, functions))
        except Exception as e:
            print(repr(e))
            raise e
