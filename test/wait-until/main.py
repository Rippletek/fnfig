import time

last = None


def initializer(_context):
    pass


def step1(args):
    global last
    last = time.time()


def check_if_3second(args):
    return time.time() - last > 3


def step2(args):
    current = time.time()
    if current - last <= 3:
        raise Exception(f"bad time last: {last}, current: {current}")
