#!/usr/bin/env python

import sys
sys.path.insert(0, '..')  # Give me an access to juice

import copy
import logging
import os
from pprint import pformat

import juice as j
from execo_engine.sweep import (ParamSweeper, sweep)


SWEEPER_DIR = os.path.join(os.getenv('HOME'), 'juice-sweeper-latency-impact')

# G5k parameters
JOB_NAME = 'juice-latency-impact'
WALLTIME = '61:59:00'
RESERVATION = '2018-05-11 19:00:01'
CLUSTER = 'ecotype'
SITE = 'nantes'

# Experimentation parameters
DATABASES = ['mariadb', 'galera', 'cockroachdb']
DELAYS = [50, 150]
BURST = [False, True]

CONF = {
  'monitoring': True,
  'g5k': {'dhcp': True,
          'env_name': 'debian9-x64-nfs',
          'job_name': JOB_NAME,
          # 'queue': 'testing',
          'walltime': WALLTIME,
          'reservation': RESERVATION,
          'resources': {'machines': [{'cluster': CLUSTER,
                                      'nodes': 9,
                                      'roles': ['chrony',
                                                'database',
                                                'sysbench',
                                                'openstack',
                                                'rally'],
                                      'primary_network': 'n1',
                                      'secondary_networks': ['n2']},
                                     {'cluster': CLUSTER,
                                      'nodes': 1,
                                      'roles': ['registry', 'control'],
                                      'primary_network': 'n1',
                                      'secondary_networks': []}],
                        'networks': [{'id': 'n1',
                                      'roles': ['control_network'],
                                      'site': SITE,
                                      'type': 'prod'},
                                      {'id': 'n2',
                                      'roles': ['database_network'],
                                      'site': SITE,
                                      'type': 'kavlan'},
                                     ]}},
  'registry': {'ceph': True,
               'ceph_id': 'discovery',
               'ceph_keyring': '/home/discovery/.ceph/ceph.client.discovery.keyring',
               'ceph_mon_host': ['ceph0.rennes.grid5000.fr',
                                 'ceph1.rennes.grid5000.fr',
                                 'ceph2.rennes.grid5000.fr'],
               'ceph_rbd': 'discovery_kolla_registry/datas',
               'type': 'internal'},
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
  , "keystone/create-user-update-password.yaml"
  , "keystone/create-user-set-enabled-and-delete.yaml"
  , "keystone/create-and-list-users.yaml"
]


logging.basicConfig(level=logging.INFO)


def init():
  try:
    j.g5k(config=CONF, force=True)
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
        "Setup went wrong. This is not necessarily a bad news, "
        "in particular, if it is the first time you run the "
        "experiment: %s" % e)


def keystone_exp():
    sweeper = ParamSweeper(
        SWEEPER_DIR,
        sweeps=sweep({
              'db':    DATABASES
            , 'delay': DELAYS
            , 'burst': BURST
        }))

    while sweeper.get_remaining():
        combination = sweeper.get_next()
        logging.info("Treating combination %s" % pformat(combination))

        db    = combination['db']
        delay = combination['delay']
        burst = combination['burst']

        try:
            # Setup parameters
            conf = copy.deepcopy(CONF)  # Make a deepcopy so we can run
                                        # multiple sweeps in parallels
            conf['tc']['constraints'][0]['delay'] = "%sms" % delay
            xp_name = "%s-9-%s-%s" % (db, delay, str(burst)[0])

            # Let's get it started hun!
            j.deploy(conf, db, xp_name)
            j.openstack(db)
            j.emulate(conf['tc'])
            j.rally(SCENARIOS, "keystone", burst)
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
