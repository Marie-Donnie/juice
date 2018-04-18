#!/usr/bin/env python

import logging
import copy
from pprint import pformat

import juice as j
from execo_engine.sweep import (ParamSweeper, sweep)

# From https://github.com/rcherrueau/juice/blob/keystone-experiments/experiments.py

SWEEPER_DIR = './sweeper'

WALLTIME = '1:00:00'
# WALLTIME = '01:40:00'
# RESERVATION = '2018-03-21 01:15:00'
RESERVATION = None

#DATABASES = [('mariadb', False), ('cockroachdb', False), ('cockroachdb', True)]
DATABASES = [('cockroachdb', False), ('cockroachdb', True)]
# DATABASES = [('mariadb', False)]
# CLUSTER_SIZES = [25]
CLUSTER_SIZES = [10]
# DELAYS = [0, 50, 150]
DELAYS = [0]

MAX_CLUSTER_SIZE = max(CLUSTER_SIZES)

CONF = {
  'enable_monitoring': True,
  'g5k': {'dhcp': True,
          'env_name': 'debian9-x64-nfs',
          'job_name': 'juice-tests',
          'queue': 'testing',
          'walltime': WALLTIME,
          'reservation': RESERVATION,
          'resources': {'machines': [{'cluster': 'ecotype',
                                      'nodes': MAX_CLUSTER_SIZE,
                                      'roles': ['chrony',
                                                'database',
                                                'sysbench',
                                                'openstack',
                                                'rally'],
                                      'primary_network': 'n1',
                                      'secondary_networks': ['n2']},
                                     {'cluster': 'ecotype',
                                      'nodes': 1,
                                      'roles': ['registry', 'control'],
                                      'primary_network': 'n1',
                                      'secondary_networks': []}],
                        'networks': [{'id': 'n1',
                                      'roles': ['control_network'],
                                      'site': 'nantes',
                                      'type': 'prod'},
                                      {'id': 'n2',
                                      'roles': ['database_network'],
                                      'site': 'nantes',
                                      'type': 'kavlan'},
                                     ]}},
  'registry': {'ceph': True,
               'ceph_id': 'discovery',
               'ceph_keyring': '/home/discovery/.ceph/ceph.client.discovery.keyring',
               'ceph_mon_host': ['ceph0.rennes.grid5000.fr',
                                 'ceph1.rennes.grid5000.fr',
                                 'ceph2.rennes.grid5000.fr'],
               'ceph_rbd': 'discovery_kolla_registry/datas',
               'type': 'none'},
  'tc': {'constraints': [{'delay': '0ms',
                          'src': 'database',
                          'dst': 'database',
                          'loss': 0,
                          'rate': '10gbit',
                          "network": "database_network"}],
         'default_delay': '0ms',
         'default_rate': '10gbit',
         'enable': True,
         'groups': ['database']}
}

SCENARIOS = [
    "keystone/authenticate-user-and-validate-token.yaml"
  , "keystone/create-add-and-list-user-roles.yaml"
  , "keystone/create-and-list-tenants.yaml"
  , "keystone/get-entities.yaml"
  , "keystone/create-and-update-user.yaml"
  , "keystone/create-user-update-password.yaml"
  , "keystone/create-user-set-enabled-and-delete.yaml"
  , "keystone/create-and-list-users.yaml"
]


logging.basicConfig(level=logging.INFO)


def init():
  try:
    j.g5k(config=CONF)
    j.inventory()
    j.destroy()
    j.emulate(CONF['tc'])
  except Exception as e:
    logging.error(
        "Setup goes wrong. This is not necessarily a bad news, "
        "in particular, if it is the first time you run the "
        "experiment: %s" % e)


def teardown():
  try:
    j.destroy()
    j.emulate(CONF['tc'])
  except Exception as e:
    logging.warning(
        "Setup goes wrong. This is not necessarily a bad news, "
        "in particular, if it is the first time you run the "
        "experiment: %s" % e)


def keystone_exp():
    sweeper = ParamSweeper(
        SWEEPER_DIR,
        sweeps=sweep({
              'db':    DATABASES
            , 'delay': DELAYS
            , 'db-nodes': CLUSTER_SIZES
        }))

    while sweeper.get_remaining():
        combination = sweeper.get_next()
        logging.info("Treating combination %s" % pformat(combination))

        try:
            # Setup parameters
            conf = copy.deepcopy(CONF) # Make a deepcopy so we can run
            # multiple sweeps in parallels
            conf['g5k']['resources']['machines'][0]['nodes'] = combination['db-nodes']
            conf['tc']['constraints'][0]['delay'] = "%sms" % combination['delay']
            db = combination['db'][0]
            db_locality = combination['db'][1]

            xp_name = "%s-%s-%s-" % (db, combination['db-nodes'], combination['delay'])
            xp_name = xp_name + ("local" if db_locality else "nonlocal")

            # Let's get it started hun!
            j.deploy(conf, db, db_locality, xp_name)
            j.openstack(db)
            j.emulate(conf['tc'])
            j.rally(SCENARIOS, "keystone")
            j.backup()

            # Everything works well, mark combination as done
            sweeper.done(combination)
            logging.info("End of combination %s" % pformat(combination))

        except Exception as e:
          # Oh no, something goes wrong! Mark combination as cancel for
          # a later retry
            logging.error("Combination %s Failed with message %s" % (pformat(combination), e))
            sweeper.cancel(combination)

        finally:
            teardown()

if __name__ == '__main__':
  # Do the initial reservation and boilerplate
  init()

  # Run experiment
  keystone_exp()
