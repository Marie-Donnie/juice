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
from docopt import docopt

from utils.doc import doc, doc_lookup


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


def unzip_rally(directory, **kwargs):
    _find_tar(directory)
    # tarfile.getmembers(
    return


def _find_tar(directory):
    folder_pattern = re.compile(".*(maria|cockroach).*")
    tar_pattern = re.compile("(rally-).*(grid5000.fr.tar.gz)")
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
                            print(path_to_tar)
                            return(path_to_tar)


def add_results(directory, **kwargs):
    return


if __name__ == '__main__':

    args = docopt(__doc__,
                  version='analysis version 1.0.0',
                  options_first=True)

    argv = [args['<command>']] + args['<args>']

    doc_lookup(args['<command>'], argv)
