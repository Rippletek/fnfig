def initializer(_context):
    pass


def assert_equal(r, expected):
    if r != expected:
        raise Exception(f"bad result {r}, expecting {expected}")


def initx(args):
    print(f'initx, args: {args}')
    args['x'] = 5
    return args


def addx_all(args):
    print(f'addx_all, args: {args}')
    return args, [1, 2, 3, 4, 5]


def addx(args, value):
    print(f'addx, args: {args}, value: {value}')
    return value + args['x']


def verify1(args, values):
    print(f'verify1, args: {args}, values: {values}')
    assert_equal(values, [6, 7, 8, 9, 10])
    return args


def verify2(args):
    print(f'verify2, args: {args}')
    assert_equal(args, {'x': 5})


def add1_all(args):
    print(f'add1_all, args: {args}')
    return args, [1, 2, 3, 4, 5]


def add1(args, value):
    print(f'addx, args: {args}, value: {value}')
    return value + 1


def verify3(args, values):
    print(f'verify3, args: {args}, values: {values}')
    assert_equal(values, [2, 3, 4, 5, 6])
    return args