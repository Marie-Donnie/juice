from functools import wraps
from docopt import docopt

DOC_GLOBAL = {}


def doc(doc_param=None):
    def decorator(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            # Format the arguments for convenient use
            for k, v in kwargs.items():
                if k.startswith('--'):
                    kwargs[k.lstrip('--')] = v
                elif k.startswith('-'):
                    kwargs[k.lstrip('-')] = v
            # Proceeds with the function execution
            fn(*args, **kwargs)
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


def db_validation(db):
    databases = ['mariadb', 'cockroachdb', 'galera']
    if db not in databases:
        exit("%s is not an allowed database. Try one of the following: %s"
             % (db, ', '.join(databases)))
