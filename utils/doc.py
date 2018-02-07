from functools import wraps
from docopt import docopt

DOC_GLOBAL = {}


def doc():
    def decorator(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            # Format the arguments for convenient use
            for k,v in kwargs.items():
                if k.startswith('--'):
                    kwargs[k.lstrip('--')]=v
            # Proceeds with the function execution
            fn(*args, **kwargs)
        DOC_GLOBAL[fn.__name__]= decorated
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
    exit("%r is not a juice command. \n%s" % (kwargs['<command>'], error_lookup.__doc__))
