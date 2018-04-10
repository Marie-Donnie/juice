#!/usr/bin/env python

"""Analyse your results from experiments

Usage:
    analysis [-h | --help] [-v | --version] <command> [<args>...]

Options:
    -h --help      Show this help
    -v --version   Show version number

Commands:
    deploy         Claim resources from g5k and configure them

Run 'analysis COMMAND --help' for more information on a command
"""

import logging
import re
import os
import tarfile
import json

import pandas as pd
import matplotlib.pyplot as plt
from docopt import docopt

from utils.doc import doc, doc_lookup


pd.options.display.float_format = '{:20,.6f}'.format

DF = []


@doc()
def full_run(directory, **kwargs):
    """
usage: analysis full_run (--directory=directory)

Full run from a directory
    """
    directories = check_directory(directory)
    for result_dir in directories:
        unzip_rally(result_dir)
        add_results(result_dir)
    # _plot()
    # print(DF)
    test_graph = DF[0][2]
    test_graph.plot.bar()
    plt.show()


def check_directory(folder, **kwargs):
    results = []
    if os.path.exists(folder):
        if os.path.isdir(folder):
            directories = os.listdir(folder)
            for directory in directories:
                if _check_result_dir(directory, folder):
                    results.append(folder + directory)
            return results
        else:
            logging.error("%s is not a directory." % directory)
    else:
        logging.error("%s does not exists." % directory)


def unzip_rally(directory, **kwargs):
    tar = _find_tar(directory)
    ar = tarfile.open(tar)
    results_dir = os.path.join(directory, "results/")
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    ar.extractall(path=results_dir,
                  members=_safe_json(ar, directory))
    ar.close()
    return


def _collect_actions(actions):
    result = []
    # print(actions)
    for a in actions:
        result.append(a)
        for suba in _collect_actions(a['children']):
            result.append(suba)
    return result


def add_results(directory, **kwargs):
    results = os.path.join(directory, "results")
    dir_name = os.path.basename(directory)
    for fil in os.listdir(results):
        file_path = os.path.join(results, fil)
        with open(file_path, "r") as fileopen:
            json_file = json.load(fileopen)
            task = json_file['tasks'][0]['subtasks'][0]['title']
            data = json_file['tasks'][0]['subtasks'][0]['workloads'][0]['data']
            actions = []
            for v in data:
                for a in v['atomic_actions']:
                    actions.append(a)
            all_actions = _collect_actions(actions)
            df = pd.DataFrame(all_actions, columns=['name',
                                                    'started_at',
                                                    'finished_at'])
            df['duration'] = df['finished_at'].subtract(df['started_at'])
            groupby_name = df.drop(columns=['finished_at', 'started_at'])
            # groupby_name = df['duration'].groupby(df['name']).describe()
            groupby_name = groupby_name.groupby('name').mean()
            # groupby_name = groupby_name.rename(columns={'duration': dir_name})
            # DF.append([dir_name, task, groupby_name.describe(include='all')])
            DF.append([dir_name, task, groupby_name])
    return


def _plot():
    df_0ms = []
    df_50ms = []
    df_150ms = []
    for result in DF:
        if '-0-' in result[0]:
            db = result[0].split('-', 1)[0]
            result[2].rename(columns={'duration': db})
            df_0ms.append(result[2])
    df_0ms.plot.bar()
    plt.show()


def _check_result_dir(directory, folder):
    pattern = re.compile(("(maria|cockroach)(db)-\d{1,3}"
                          "-\d{1,3}-(local|nonlocal)"))
    if pattern.match(directory):
        if "backup" in os.listdir(folder + directory):
            return True
        else:
            logging.warning("No backup folder in %s" % directory)
            return False
    else:
        logging.warning("%s does not match the correct pattern" % directory)
        return False


def _find_tar(directory):
    folder_pattern = re.compile(".*(maria|cockroach).*")
    tar_pattern = re.compile("(rally-).*(grid5000.fr.tar.gz)")
    tar_in_dir = []
    for folder in os.listdir(directory):
        if folder == "backup":
            backup_folder = os.path.join(directory, folder)
            for f in os.listdir(backup_folder):
                path_to_f = os.path.join(backup_folder, f)
                if folder_pattern.match(f) and os.path.isdir(path_to_f):
                    for tar in os.listdir(path_to_f):
                        path_to_tar = os.path.join(path_to_f, tar)
                        if (tar_pattern.match(tar) and
                            tarfile.is_tarfile(path_to_tar)):
                            tar_in_dir.append(path_to_tar)
                            return(path_to_tar)


# resolved = lambda x: os.path.realpath(os.path.abspath(x))
def resolved(path):
    return os.path.realpath(os.path.abspath(path))


# see https://stackoverflow.com/questions/10060069/safely-extract-zip-or-tar-using-python
def badpath(path, base):
    # joinpath will ignore base if path is absolute
    return not resolved(os.path.join(base, path)).startswith(base)


def badlink(info, base):
    # Links are interpreted relative to the directory containing the link
    tip = resolved(os.path.join(base, os.path.dirname(info.name)))
    return badpath(info.linkname, base=tip)


def _safe_json(members, directory):
    base = resolved(directory)

    for finfo in members:
        if badpath(finfo.name, base):
            logging.error("%s is blocked (illegal path)" % finfo.name)
        elif finfo.issym() and badlink(finfo, base):
            logging.error("%s is blocked: Hard link to: %s" % (finfo.name,
                                                               finfo.linkname))
        elif finfo.islnk() and badlink(finfo, base):
            logging.error("%s is blocked: Symlink to: %s" % (finfo.name,
                                                             finfo.linkname))
        else:
            if finfo.name.endswith('.json'):
                finfo.name = re.sub('rally_home/', '', finfo.name)
                yield finfo



if __name__ == '__main__':

    args = docopt(__doc__,
                  version='analysis version 1.0.0',
                  options_first=True)

    argv = [args['<command>']] + args['<args>']

    doc_lookup(args['<command>'], argv)
