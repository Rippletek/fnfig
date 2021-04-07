import time

last = None


def initializer(_context): pass


def step1(_args):
    global last
    last = time.time()


def step2(_args):
    current = time.time()
    if current - last <= 1:
        raise Exception(f"bad time last: {last}, current: {current}")
