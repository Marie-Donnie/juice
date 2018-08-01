#!/usr/bin/env python

"""Tool to test the performances of MariaDB, Galera and CockroachdB with
OpenStack on Grid'5000 using Enoslib

Usage:
    juice [-h | --help] [-v | --version] <command> [<args>...]

Options:
    -h --help      Show this help
    -v --version   Show version number

Commands:
    deploy         Claim resources from g5k and configure them
    openstack      Add OpenStack Keystone to the deployment
    stress         Launch sysbench tests (after a deployment)
    rally          Benchmark the Openstack
    emulate        Emulate network using tc
    backup         Backup the environment
    destroy        Destroy all the running dockers (not the resources)
    info           Show information of the actual deployment

Run 'juice COMMAND --help' for more information on a command
"""

import os
import logging
import sys
import time
import pprint
import yaml
import json
import operator
import pickle

from docopt import docopt
from enoslib.api import (generate_inventory, emulate_network,
                         validate_network)
from enoslib.task import enostask
from enoslib.infra.enos_g5k.provider import G5k

from utils import (JUICE_PATH, ANSIBLE_PATH, SYMLINK_NAME, doc,
                   doc_lookup, run_ansible)

logging.basicConfig(level=logging.DEBUG)

tc = {
    "enable": True,
    "default_delay": "0ms",
    "default_rate": "10gbit",
    "constraints": [{
        "src": "database",
        "dst": "database",
        "delay": "0ms",
        "rate": "10gbit",
        "loss": "0",
        "network": "database_network",
    }],
    "groups": ['database'],
}

######################################################################
## SCAFFOLDING
######################################################################


@doc()
def deploy(conf, tags, xp_name=None, **kwargs):
    """
usage: juice deploy [--conf CONFIG_PATH] [--tags TAGS...] [--force]

Claim resources from g5k and configure them.

Options:
  --conf CONFIG_PATH    Path to the configuration file describing the
                        deployment [default: ./conf.yaml]
  --tags TAGS           Only run tasks relative to the specific tags
                        [default: read-config g5k inventory prepare]
  --force               Force kadeploy3 to re-install the environment
    """
    config = {}

    if 'read-config' in tags:
      if isinstance(conf, str):
          # Get the config object from a yaml file
          with open(conf) as f:
              config = yaml.load(f)
      elif isinstance(conf, dict):
          # Get the config object from a dict
          config = conf
      else:
          # Data format error
          raise Exception(
              ('conf is type {!r} while it should be',
               'a yaml file or a dict').format(type(conf)))

    if 'g5k' in tags:
        g5k(env=xp_name, config=config, **kwargs)
        logging.info("Wait 30 seconds for eth to be ready...")
        time.sleep(30)

    if 'inventory' in tags:
        inventory()

    if 'prepare' in tags:
        prepare()


@enostask(new=True)
def g5k(env=None, force=False, config=None, **kwargs):
    "Claim resources on Grid'5000 (from a frontend)"

    provider = G5k(config["g5k"])
    roles, networks = provider.init(force_deploy=force)
    env["config"] = config
    env["roles"] = roles
    env["networks"] = networks
    env["tasks_ran"] = ['g5k']
    env["latency"] = "0ms"
    env["db"] = config.get('database', 'cockroachdb')


@enostask()
def inventory(env=None, **kwargs):
    "Generate the Ansible inventory file, requires a g5k execution"

    roles = env["roles"]
    networks = env["networks"]
    env["inventory"] = os.path.join(env["resultdir"], "hosts")
    generate_inventory(roles, networks, env["inventory"],
                       check_networks=True)
    env["tasks_ran"].append('inventory')


@enostask()
def prepare(env=None, **kwargs):
    """Configure the resources, requires both g5k and inventory
executions

    """
    # Generate inventory
    extra_vars = {
        "registry": env["config"]["registry"],
        "db": env['db'],
        # Set monitoring to True by default
        "enable_monitoring": env['config'].get('enable_monitoring', True)
    }
    # use deploy of each role
    extra_vars.update({"enos_action": "deploy"})
    run_ansible('scaffolding.yml', extra_vars=extra_vars)
    env["tasks_ran"].append('prepare')


@doc()
@enostask()
def backup(env=None, **kwargs):
    """
usage: juice backup

Backup the environment, requires g5k, inventory and prepare executions
    """
    db = env.get('db', 'cockroachdb')
    nb_nodes = len(env["roles"]["database"])
    latency = env["latency"]
    extra_vars = {
        "enos_action": "backup",
        "db": db,
        "backup_dir": os.path.join(os.getcwd(),
                                   "current/backup/%snodes-%s-%s"
                                   % (nb_nodes, db, latency)),
        "tasks_ran": env["tasks_ran"],
        # Set monitoring to True by default
        "enable_monitoring": env['config'].get('enable_monitoring', True),
        "rally_nodes": env.get('rally_nodes', [])
    }
    run_ansible('scaffolding.yml', extra_vars=extra_vars)
    run_ansible('openstack.yml', extra_vars=extra_vars)
    run_ansible('rally.yml', extra_vars=extra_vars)
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
        "db": env.get('db', 'cockroachdb'),
        "tasks_ran": env["tasks_ran"],
        # Set monitoring to True by default
        "enable_monitoring": env['config'].get('enable_monitoring', True),
        "rally_nodes": env.get('rally_nodes', [])
    })
    run_ansible('scaffolding.yml', extra_vars=extra_vars)
    run_ansible('openstack.yml', extra_vars=extra_vars)
    run_ansible('rally.yml', extra_vars=extra_vars)
    env["tasks_ran"].append('destroy')


######################################################################
## Scaffolding ++
######################################################################


@doc()
@enostask()
def openstack(env=None, **kwargs):
    """
usage: juice openstack

Launch OpenStack.
    """
    # Generate inventory
    extra_vars = {
        "registry": env["config"]["registry"],
        "db": env.get('db', 'cockroachdb'),
    }
    # use deploy of each role
    extra_vars.update({"enos_action": "deploy"})
    run_ansible('openstack.yml', extra_vars=extra_vars)
    env["tasks_ran"].append('openstack')


######################################################################
## Stress
######################################################################


@doc()
@enostask()
def stress(env=None, **kwargs):
    """
usage: juice stress

Launch sysbench tests.
    """
    # Generate inventory
    extra_vars = {
        "registry": env["config"]["registry"],
        "db": env.get('db', 'cockroachdb'),
        "enos_action": "stress"
    }
    # use deploy of each role
    run_ansible('stress.yml', extra_vars=extra_vars)
    env["tasks_ran"].append('stress')


@doc()
@enostask()
def rally(files, directory, burst, env=None, **kwargs):
    """
usage: juice rally [--files FILE... | --directory DIRECTORY] [--burst]

Benchmark the Openstack

  --files FILE           Files to use for rally scenarios (name must be a path
from rally scenarios folder).
  --directory DIRECTORY  Directory that contains rally scenarios. [default:
keystone]
  --burst                Use burst or not
    """
    logging.info("Launching rally using scenarios: %s" % (', '.join(files)))
    logging.info("Launching rally using all scenarios in %s directory.",
                 directory)

    if burst:
        rally = list(map(operator.attrgetter('address'),
                         reduce(operator.add,
                                [hosts for role, hosts in env['roles'].items()
                                 if role.startswith('database')])))
    else:
        rally = [hosts[1].address for role, hosts in env['roles'].items()
                 if role.startswith('database')]
    env['rally_nodes'] = rally
    extra_vars = {
        "registry": env["config"]["registry"],
        "rally_nodes": rally
    }
    if files:
        extra_vars.update({"rally_files": files})
    else:
        extra_vars.update({"rally_directory": directory})

    # use deploy of each role
    extra_vars.update({"enos_action": "deploy"})
    run_ansible('rally.yml', extra_vars=extra_vars)
    env["tasks_ran"].append('rally')


######################################################################
## Other
######################################################################


@doc(tc)
@enostask()
def emulate(tc=tc, env=None, **kwargs):
    """
usage: juice emulate

Emulate network using: {0}
    """
    inventory = env["inventory"]
    roles = env["roles"]
    logging.info("Emulates using constraints: %s" % tc)
    emulate_network(roles, inventory, tc)
    env["latency"] = tc['constraints'][0]['delay']
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
        print(json.dumps(env, default=operator.attrgetter('__dict__')))
    elif out == 'pickle':
        print(pickle.dumps(env))
    elif out == 'yaml':
        print(yaml.dump(env))
    else:
        print("--out doesn't suppport %s output format" % out)
        print(info.__doc__)


if __name__ == '__main__':
    args = docopt(__doc__,
                  version='juice version 1.0.0',
                  options_first=True)

    argv = [args['<command>']] + args['<args>']

    doc_lookup(args['<command>'], argv)
