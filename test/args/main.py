def initializer(_context):
    pass


X = 2021


def step1(result):
    result['x'] = X
    return result


def step2(result):
    return result


def step3(result):
    if result['x'] != X:
        raise Exception(f"bad x: {result['x']}, which should be {X}")

    if result['userInputKey'] != 'userInputValue':
        raise Exception(f"bad userInputKey: {result['userInputKey']}, which should be 'userInputValue'")

    return result
