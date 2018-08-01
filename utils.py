import os
from copy import deepcopy
from functools import wraps

from docopt import docopt
from enoslib.api import run_ansible as enos_run_ansible
from enoslib.task import enostask

JUICE_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
ANSIBLE_PATH = os.path.join(JUICE_PATH, 'ansible')
SYMLINK_NAME = os.path.abspath(os.path.join(os.getcwd(), 'current'))

DOC_GLOBAL = {}


def doc(doc_param=None):
    def decorator(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            # Format the arguments for convenient use
            new_kwargs = deepcopy(kwargs)
            for k, v in kwargs.items():
                if k.startswith('--'):
                    new_kwargs[k.lstrip('--')] = v
                elif k.startswith('-'):
                    new_kwargs[k.lstrip('-')] = v
            # Proceeds with the function execution
            fn(*args, **new_kwargs)
        DOC_GLOBAL[fn.__name__] = decorated
        # https://stackoverflow.com/questions/10307696/how-to-put-a-variable-into-python-docstring
        if doc_param:
            decorated.__doc__ = decorated.__doc__.format(doc_param)
        return decorated
    return decorator


def doc_lookup(fn_name, argv):
    fn = DOC_GLOBAL.get(fn_name, error_lookup)
    return fn(**docopt(fn.__doc__, argv=argv))


def error_lookup(**kwargs):
    """
Usage:
    juice [-h | --help] [-v | --version] <command> [<args>...]

    """
    exit("%r is not a juice command. \n%s" % (kwargs['<command>'],
                                              error_lookup.__doc__))


@enostask()
def run_ansible(playbook, extra_vars=None, tags=None,
                on_error_continue=False, env=None, **kwargs):
    """State combinator for enoslib.api.run_ansible

    Reads the inventory path from the state and then applied and
    returns value of `enoslib.api.run_ansible`.

    """
    inventory = env["inventory"]
    playbooks = [os.path.join(ANSIBLE_PATH, playbook)]

    return enos_run_ansible(playbooks, inventory, extra_vars, tags,
                            on_error_continue)
