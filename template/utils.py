import json
import time
import concurrent.futures
import collections

def go_to_end(result=None):
    return [result, {'_next_step': 'end'}]


def check_go_to(r):
    if isinstance(r['result'], list) and len(r['result']) == 2 and isinstance(r['result'][1], dict) and '_next_step' in r['result'][1]:
        r['fdl_action'] = r['result'][1]['_next_step']
        r['result'] = r['result'][0]

    return r


class Handler:
    def __init__(self, funcs, first):
        self.funcs = funcs
        self.first = first

    def run(self, event, _context):
        args = json.loads(event)
        action = args.pop('fdl_action')
        if action == 'begin':
            r = {'fdl_action': self.first}
        else:
            f = self.funcs.get(action)
            print(f'invoking {f.__name__} with {args}')
            r = f(args)

        if 'fdl_wait' not in r:
            r['fdl_wait'] = 0
            if 'fdl_action' not in r:
                raise Exception('fdl_action is missing')
        return r


class FakeResponder:
    def __init__(self, resp):
        self.resp = resp

    def __getattr__(self, name):
        def method(*args, **kwargs):
            if name in self.resp:
                v = self.resp[name]
                if isinstance(v, list):
                    return v.pop(0)
                if isinstance(v, collections.Callable):
                    return v(*args)
            raise Exception(f'undefined method {name}')
        return method


class FakeFDL:
    def __init__(self, f, args, context):
        self.handler = f
        self.args = args
        self.context = context
        self.args['fdl_action'] = 'begin'

    def run_each(self, arglist):
        args, f, c, k = arglist
        args['fdl_key'] = k
        return f(json.dumps(args), c)


    def run(self):
        while self.args['fdl_action'] != 'end':
            print('run with args:', self.args)
            if self.args['fdl_action'].startswith('_foreach_'):
                r = {}
                keys = self.args['fdl_foreach_keys']
                print(f'foreach keys: {keys}')

                with concurrent.futures.ProcessPoolExecutor() as executor:
                    vals = executor.map(self.run_each, [(self.args, self.handler, self.context, key) for key in keys])
                    cols = [(v['fdl_value'], v['fdl_action']) for v in vals]
                    r['fdl_foreach_values'] = [v[0] for v in cols]
                    r['fdl_action'] = cols[0][1]
            else:
                r = self.handler(json.dumps(self.args), self.context)
            print('return result:', r)
            self.args.update(r)
            ws = self.args['fdl_wait']
            if ws > 0:
                print(f'waiting for {ws} seconds..')
                time.sleep(1)
                continue


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)
