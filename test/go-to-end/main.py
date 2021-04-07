import fig_utils

def initializer(_context):
    pass


def step1(result):
    return fig_utils.go_to_end(result)


def step2(_):
    raise Exception('this method can not be reached.')


def step3(_):
    raise Exception('this method can not be reached.')
