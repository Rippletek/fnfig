import os
import re
import sys
import pathlib
from jinja2 import Template


KEYWORD_LOOP = 'foreach'
KEYWORD_WAIT = 'wait'

STATEMENT_LOOP = 'statement_loop'
STATEMENT_WAIT = 'statement_wait'
STATEMENT_WAITUNTIL = 'statement_waituntil'
STATEMENT_FUNC = 'statement_func'

ENTRYNAME = 'fig_runner'
METHOD_COMPLETED_NAME = '_completed'


def is_positive_int(s):
    return re.search("^[1-9][0-9]*$", s)


def do_file_exist(file):
    return pathlib.Path(file).is_file()


def get_package_name(fig_file):
    return pathlib.Path(fig_file).stem


def gen_runner_head(statements, fig_file):
    statement = statements[0]
    if statement['method_type'] != STATEMENT_FUNC:
        raise Exception(f'first line [{statement["raw_line"]}] must be a normal function.')

    basename = get_package_name(fig_file)
    funcs = ['initializer']
    funcs += [s['values'][0] for s in statements if s['method_type'] not in [STATEMENT_WAIT, STATEMENT_WAITUNTIL]]
    funcs += [s['values'][1] for s in statements if s['method_type'] == STATEMENT_WAITUNTIL]

    head = render_tpl('runner_head.py.jinja2', {'basename': basename, 'funcs': funcs, 'statement': statement})
    return [head]


def gen_runner_completed():
    s = f"""
def {METHOD_COMPLETED_NAME}(_args):
    return {{'fdl_action': 'end'}}
    """

    return [s]


def gen_runner_method(scurrent, rest_statements, sprevious):
    if len(rest_statements) > 0:
        snext = rest_statements[0]
    else:
        snext = new_statement_completed()

    return_optons = {"'fdl_action'": f"'{snext['method_name']}'"}

    body_lines = []
    if snext['method_type'] == STATEMENT_LOOP:
        if scurrent['method_type'] == STATEMENT_WAIT:
            body_lines.append("keys = args.get('fdl_foreach_keys')")
        else:
            body_lines.append(f"result, keys = {scurrent['values'][0]}(args.get('result'))")
            body_lines.append("args['result'] = result")

        if len(rest_statements) > 1:
            method_reduce = rest_statements[1]['method_name']
        else:
            method_reduce = 'end'
        body_lines.append("if len(keys) == 0: return {'fdl_action': '%s', 'fdl_foreach_values': []}\n" % (method_reduce,))
        return_optons["'fdl_foreach_keys'"] = 'keys'

    if scurrent['method_type'] == STATEMENT_WAIT:
        return_optons["'fdl_wait'"] = f"{scurrent['values'][0]}"
    elif scurrent['method_type'] == STATEMENT_LOOP:
        return_optons["'fdl_value'"] = f"{scurrent['values'][0]}(args.get('result'), args['fdl_key'])"
    elif scurrent['method_type'] == STATEMENT_WAITUNTIL:
        body_lines.append("if not %s(args.get('result')): return {'fdl_wait': %s}\n" % (scurrent['values'][1], scurrent['values'][0]))

    if scurrent['method_type'] == STATEMENT_FUNC and snext['method_type'] != STATEMENT_LOOP:
        if sprevious and sprevious['method_type'] == STATEMENT_LOOP:
            return_optons["'result'"] = f"{scurrent['values'][0]}(args.get('result'), args['fdl_foreach_values'])"
        else:
            return_optons["'result'"] = f"{scurrent['values'][0]}(args.get('result'))"
    else:
        return_optons["'result'"] = "args.get('result')"

    creturn_value = ", ".join(["{}: {}".format(k, v) for k, v in return_optons.items()])
    body_lines.append('return check_go_to({%s})' % (creturn_value,))
    cbody = '\n'.join(map(lambda l: f'    {l}', body_lines))

    method = f"""
def {scurrent['method_name']}(args):
{cbody}
    """

    return [method]


def gen_runner_methods(statements, codes, sprevious=None):
    if len(statements) == 0:
        return codes

    scurrent = statements[0]
    statements = statements[1:]

    codes += gen_runner_method(scurrent, statements, sprevious)
    return gen_runner_methods(statements, codes, scurrent)


def new_statement(raw_line, mname, mtype, values):
    return {
        'raw_line': raw_line,
        'method_name': mname,
        'method_type': mtype,
        'values': values,
    }


def new_statement_completed():
    return new_statement('completed', METHOD_COMPLETED_NAME, STATEMENT_FUNC, ['completed'])


def parse_keyword_loop(line, args, index):
    if len(args) != 1:
        print(f'invalid format of line [{line}]')
        sys.exit(1)

    func = args[0]
    return new_statement(line, f'_foreach_{func}_{index}', STATEMENT_LOOP, [func])


def parse_keyword_wait(line, args, index):
    if len(args) == 1 and is_positive_int(args[0]):
        seconds = int(args[0])
        return new_statement(line, f'_wait_{seconds}_{index}', STATEMENT_WAIT, [seconds])
    elif len(args) == 3 and is_positive_int(args[0]) and args[1] == 'until':
        seconds = int(args[0])
        func = args[2]
        return new_statement(line, f'_wait_{seconds}_until_{func}_{index}', STATEMENT_WAITUNTIL, [seconds, func])
    else:
        print(f'invalid format of line [{line}]')
        sys.exit(1)


def parse_line(line, index):
    terms = [term for term in line.split(' ') if term != '']
    command = terms[0]
    args = terms[1:]

    if command == KEYWORD_LOOP:
        return parse_keyword_loop(line, args, index)
    if command == KEYWORD_WAIT:
        return parse_keyword_wait(line, args, index)

    return new_statement(line, f'_func_{line}_{index}', STATEMENT_FUNC, [line])


def parse_lines(lines):
    return [parse_line(line.strip(), index) for index, line in enumerate(lines) if line.strip() != '']


def read_file(filename):
    fullname = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'template', filename)
    with open(fullname) as f:
        return f.read()


def write_file(content, name):
    with open(name, 'w') as f:
        f.write(content.strip())


def render_tpl(tpl_filename, items):
    return Template(read_file(tpl_filename)).render(items)


def generate_pymain(statements, fig_file):
    basename = pathlib.Path(fig_file).stem
    main_file = f'{basename}.py'

    if do_file_exist(main_file):
        return

    lines = ['# import fig_utils', 'def initializer(_context): pass']
    lines += gen_main_methods(statements, [])

    code = '\n\n\n'.join(lines)
    write_file(code, main_file)


def gen_main_method(scurrent, rest_statements, sprevious):
    if len(rest_statements) > 0:
        snext = rest_statements[0]
    else:
        snext = new_statement_completed()

    lines = []

    if scurrent['method_type'] == STATEMENT_FUNC:
        if snext['method_type'] == STATEMENT_LOOP:
            lines += [f'def {scurrent["values"][0]}(args): return args, []']
        elif sprevious and sprevious['method_type'] == STATEMENT_LOOP:
            lines += [f'def {scurrent["values"][0]}(args, values): return args']
        else:
            lines += [f'def {scurrent["values"][0]}(args): return args']
    elif scurrent['method_type'] == STATEMENT_LOOP:
        lines += [f'def {scurrent["values"][0]}(args, value): return value']
    elif scurrent['method_type'] == STATEMENT_WAITUNTIL:
        lines += [f'def {scurrent["values"][1]}(args): return args']

    return lines


def gen_main_methods(statements, codes, sprevious=None):
    if len(statements) == 0:
        return codes

    scurrent = statements[0]
    statements = statements[1:]

    codes += gen_main_method(scurrent, statements, sprevious)
    return gen_main_methods(statements, codes, scurrent)


def generate_pyrunner(statements, fig_file):
    lines = gen_runner_head(statements, fig_file)
    lines += gen_runner_methods(statements, [])
    lines += gen_runner_completed()
    code = '\n'.join(lines)
    write_file(code, f'{ENTRYNAME}.py')


def generate_pyutils():
    code = read_file('utils.py')
    write_file(code, 'fig_utils.py')


def generate_python(statements, fig_file):
    generate_pymain(statements, fig_file)
    generate_pyrunner(statements, fig_file)
    generate_pyutils()


def generate_testpy(fig_file):
    test_file = 'test.py'
    if do_file_exist(test_file):
        return

    code = render_tpl('test.py.jinja2', {'basename': get_package_name(fig_file)})
    write_file(code, 'test.py')


def generate_testsh():
    code = read_file('test.sh')
    write_file(code, 'test.sh')


def generate_test(fig_file):
    generate_testpy(fig_file)
    generate_testsh()


def main():
    fig_file = sys.argv[1]
    with open(fig_file, 'r') as f:
        lines = f.readlines()
    statements = parse_lines(lines)

    generate_python(statements, fig_file)
    generate_test(fig_file)


if __name__ == '__main__':
    main()
