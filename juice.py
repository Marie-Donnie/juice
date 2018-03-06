#!/usr/bin/env python

"""Tool to test Keystone over Galera and CockroachdB on Grid'5000 using Enoslib

Usage:
    juice [-h | --help] [-v | --version] <command> [<args>...]

Options:
    -h --help      Show this help
    -v --version   Show version number

Commands:
    deploy         Claim resources from g5k and configure them
    g5k            Claim resources on Grid'5000 (from a frontend)
    info           Show information of the actual deployment
    inventory      Generate the Ansible inventory file
    prepare        Configure the resources
    stress         Launch sysbench tests (after a deployment)
    openstack      Add OpenStack Keystone to the deployment
    rally          Benchmark the Openstack
    backup         Backup the environment
    destroy        Destroy all the running dockers (not the resources)

Run 'juice COMMAND --help' for more information on a command
"""

import os
import logging
import yaml

from docopt import docopt
import pprint
import json
import operator
import pickle
import yaml
from enoslib.api import (run_ansible, generate_inventory,
                         emulate_network, validate_network)
from enoslib.task import enostask
from enoslib.infra.enos_g5k.provider import G5k

from utils.doc import doc, doc_lookup, db_validation

logging.basicConfig(level=logging.DEBUG)

DEFAULT_CONF = os.path.dirname(os.path.realpath(__file__))
DEFAULT_CONF = os.path.join(DEFAULT_CONF, "conf.yaml")

SYMLINK_NAME = os.path.abspath(os.path.join(os.getcwd(), 'current'))

tc = {
    "enable": True,
    "default_delay": "0ms",
    "default_rate": "10gbit",
    "constraints": [{
        "src": "database",
        "dst": "database",
        "delay": "200ms",
        "rate": "10gbit",
        "loss": "0",
    }],
}


@doc()
def deploy(conf, db, locality, **kwargs):
    """
usage: juice deploy [--conf CONFIG_PATH] [--db {mariadb,cockroachdb}]
                    [--locality]

Claim resources from g5k and configure them.

Options:
  --conf CONFIG_PATH    Path to the configuration file describing the
                        deployment [default: ./conf.yaml]
  --db DATABASE         Database to deploy on [default: cockroachdb]
  --locality            Use follow-the-workload (only for CockroachDB)
    """
    config = {}
    with open(conf) as f:
        config = yaml.load(f)
    db_validation(db)

    g5k(config=config)
    inventory()
    prepare(db=db, locality=locality)


@doc()
@enostask(new=True)
def g5k(env=None, force=False, config=None,  **kwargs):
    """
usage: juice g5k

Claim resources on Grid'5000 (from a frontend)
    """
    provider = G5k(config["g5k"])
    roles, networks = provider.init(force_deploy=force)
    env["config"] = config
    env["roles"] = roles
    env["networks"] = networks
    env["tasks_ran"] = ['g5k']


@doc()
@enostask()
def inventory(env=None, **kwargs):
    """
usage: juice inventory

Generate the Ansible inventory file, requires a g5k execution
    """
    roles = env["roles"]
    networks = env["networks"]
    env["inventory"] = os.path.join(env["resultdir"], "hosts")
    generate_inventory(roles, networks, env["inventory"], check_networks=True)
    env["tasks_ran"].append('inventory')


@doc()
@enostask()
def prepare(env=None, db='cockroachdb', locality=False, **kwargs):
    """
usage: juice prepare [--db {mariadb,cockroachdb}] [--locality]

Configure the resources, requires both g5k and inventory executions

  --db DATABASE         Database to deploy on [default: cockroachdb]
  --locality            Use follow-the-workload (only for CockroachDB)
    """
    db_validation(db)
    # Generate inventory
    extra_vars = {
        "registry": env["config"]["registry"],
        "db": db,
        "locality": locality,
    }
    env["db"] = db
    # use deploy of each role
    extra_vars.update({"enos_action": "deploy"})
    run_ansible(["ansible/prepare.yml"], env["inventory"], extra_vars=extra_vars)
    env["tasks_ran"].append('prepare')


@doc()
@enostask()
def stress(db, env=None, **kwargs):
    """
usage: juice stress [--db {mariadb,cockroachdb}]

Launch sysbench tests

  --db DATABASE         Database to test [default: cockroachdb]
    """
    db_validation(db)
    # Generate inventory
    extra_vars = {
        "registry": env["config"]["registry"],
        "db": db,
    }
    # use deploy of each role
    extra_vars.update({"enos_action": "deploy"})
    run_ansible(["ansible/stress.yml"], env["inventory"], extra_vars=extra_vars)
    env["tasks_ran"].append('stress')


@doc()
@enostask()
def openstack(db, env=None, **kwargs):
    """
usage: juice openstack [--db {mariadb,cockroachdb}]

Launch OpenStack

  --db DATABASE         Database to test [default: cockroachdb]
    """
    db_validation(db)
    # Generate inventory
    extra_vars = {
        "registry": env["config"]["registry"],
        "db": db,
    }
    # use deploy of each role
    extra_vars.update({"enos_action": "deploy"})
    run_ansible(["ansible/openstack.yml"], env["inventory"], extra_vars=extra_vars)
    env["tasks_ran"].append('openstack')


@doc()
@enostask()
def rally(db, files, directory, env=None, **kwargs):
    """
usage: juice rally [--db {mariadb,cockroachdb}] [--files FILE... | --directory DIRECTORY]

Benchmark the Openstack

  --db DATABASE         Database to test [default: cockroachdb]
  --files FILE          Files to use for rally scenarios (name must be a path from rally scenarios folder).
  --directory DIRECTORY    Directory that contains rally scenarios. [default: keystone]
    """
    db_validation(db)
    logging.info("Launching rally using scenarios : %s" % ( ', '.join(files)))
    logging.info("Launching rally using all scenarios in %s directory.", directory)
    # Generate inventory
    extra_vars = {
        "registry": env["config"]["registry"],
        "db": db,
    }
    if files:
        extra_vars.update({"rally_files": files})
    else:
        extra_vars.update({"rally_directory": directory})

    # use deploy of each role
    extra_vars.update({"enos_action": "deploy"})
    run_ansible(["ansible/rally.yml"], env["inventory"], extra_vars=extra_vars)
    env["tasks_ran"].append('rally')


@doc()
@enostask()
def emulate(env=None, **kwargs):
    """
usage: juice emulate

Emulate network
    """
    inventory = env["inventory"]
    roles = env["roles"]
    emulate_network(roles, inventory, tc)
    env["tasks_ran"].append('emulate')


@doc()
@enostask()
def validate(env=None, **kwargs):
    """
usage: juice validate

Validate network. Doesn't work for now since there is no flent installed
    """
    inventory = env["inventory"]
    roles = env["roles"]
    validate_network(roles, inventory)
    env["tasks_ran"].append('validate')


@doc(SYMLINK_NAME)
@enostask()
def info(env, out, **kwargs):
    """
usage: enos info [-e ENV|--env=ENV] [--out=FORMAT]

Show information of the `ENV` deployment.

Options:
  -e ENV --env=ENV         Path to the environment directory. You should use
                           this option when you want to link a
                           specific experiment [default: {0}].
  --out FORMAT             Output the result in either json, pickle or
                           yaml format.
    """
    if not out:
        pprint.pprint(env)
    elif out == 'json':
        print json.dumps(env, default=operator.attrgetter('__dict__'))
    elif out == 'pickle':
        print pickle.dumps(env)
    elif out == 'yaml':
        print yaml.dump(env)
    else:
        print("--out doesn't suppport %s output format" % out)
        print(info.__doc__)


@doc()
@enostask()
def backup(env=None, **kwargs):
    """
usage: juice backup

Backup the environment, requires g5k, inventory and prepare executions
    """
    extra_vars = {
        "enos_action": "backup",
        "backup_dir": os.path.join(os.getcwd(), "current/backup"),
        "tasks_ran" : env["tasks_ran"],
    }
    run_ansible(["ansible/prepare.yml"], env["inventory"], extra_vars=extra_vars)
    run_ansible(["ansible/stress.yml"], env["inventory"], extra_vars=extra_vars)
    run_ansible(["ansible/openstack.yml"], env["inventory"], extra_vars=extra_vars)
    run_ansible(["ansible/rally.yml"], env["inventory"], extra_vars=extra_vars)
    env["tasks_ran"].append('backup')


@doc()
@enostask()
def destroy(env=None, **kwargs):
    """
usage: juice destroy

Destroy all the running dockers (not destroying the resources), requires g5k
and inventory executions
    """
    extra_vars = {}
    # Call destroy on each component
    extra_vars.update({
        "enos_action": "destroy",
        "db": env["db"],
        "tasks_ran" : env["tasks_ran"],
    })
    run_ansible(["ansible/prepare.yml"], env["inventory"], extra_vars=extra_vars)
    run_ansible(["ansible/stress.yml"], env["inventory"], extra_vars=extra_vars)
    run_ansible(["ansible/openstack.yml"], env["inventory"], extra_vars=extra_vars)
    run_ansible(["ansible/rally.yml"], env["inventory"], extra_vars=extra_vars)
    env["tasks_ran"].append('destroy')


if __name__ == '__main__':

    args = docopt(__doc__,
                  version='juice version 1.0.0',
                  options_first=True)

    argv = [args['<command>']] + args['<args>']

    doc_lookup(args['<command>'], argv)
