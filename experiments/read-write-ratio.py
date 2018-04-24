#!/usr/bin/env python

import sys
sys.path.insert(0, '..')  # Give me an access to juice

import logging
import os
from pprint import pprint

import pymysql
import yaml

import juice as j



# This experiment runs Keystone rally scenarios referred in
# `SCENARIOS` and gives the database reads/write ratio for each. Note
# that the ratio is not fully accurate since it also measure the
# creation/deletion of rally context for each scenario.
#
# Results are:
# - keystone/authenticate-user-and-validate-token.yaml:
#   + reads: 13339
#   + writes: 489
#   + %reads: 96.46
#   + %writes: 3.54
#
# - keystone/create-add-and-list-user-roles.yaml:
#   + reads: 13303.0
#   + writes: 523.0
#   + %reads: 96.22
#   + %writes: 3.78
#
# - keystone/create-and-list-tenants.yaml:
#   + reads: 1427.0
#   + writes: 122.0
#   + %reads: 92.12
#   + %writes: 7.88
#
# - keystone/create-and-list-users.yaml:
#   + reads: 12061.0
#   + writes: 1042.0
#   + %reads: 92.05
#   + %writes: 7.95
#
# - keystone/create-and-update-user.yaml:
#   + reads: 2379.0
#   + writes: 219.0
#   + %reads: 91.57
#   + %writes: 8.43
#
# - keystone/create-user-set-enabled-and-delete.yaml:
#   + reads: 25125.0
#   + writes: 2463.0
#   + %reads: 91.07
#   + %writes: 8.93
#
# - keystone/create-user-update-password.yaml:
#   + reads: 13554.0
#   + writes: 1542.0
#   + %reads: 89.79
#   + %writes: 10.21
#
# - keystone/get-entities.yaml:
#   + reads: 25427.0
#   + writes: 2242.0
#   + %reads: 91.9
#   + %writes: 8.1

JOB_NAME = 'juice-read-write-ratio'
WALLTIME = '4:50:00'
# WALLTIME = '44:55:00'
# WALLTIME = '13:59:58'
RESERVATION = None
# RESERVATION = '2018-04-18 19:00:00'
# RESERVATION = '2018-04-20 19:00:01'

CONF = {
  'enable_monitoring': False,
  'g5k': {'dhcp': True,
          'env_name': 'debian9-x64-nfs',
          'job_name': JOB_NAME,
          'walltime': WALLTIME,
          'reservation': RESERVATION,
          'resources': {'machines': [{'cluster': 'graphene',
                                      'nodes': 1,
                                      'roles': ['chrony',
                                                'database',
                                                'sysbench',
                                                'openstack',
                                                'rally',
                                                'registry',
                                                'control'],
                                      'primary_network': 'n1',
                                      'secondary_networks': []}],
                        'networks': [{'id': 'n1',
                                      'roles': ['control_network', 'database_network'],
                                      'site': 'nancy',
                                      'type': 'prod'}
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
        j.deploy(CONF, 'mariadb', False, JOB_NAME)
        j.openstack('mariadb', env=JOB_NAME)
    except Exception as e:
        logging.error("Setup goes wrong with error: %s" % e)


def total_reads_writes(host_address):
    """Returns the total of reads and writes on `host_address`.

    Returns a tuple with first, the total of reads, and second, the
    total of writes that have been performed on the mariadb database
    `host_address`.
    """
    SQL = '''
    SELECT
      SUM(IF(variable_name = 'Com_select', variable_value, 0))
         AS `Total reads`,
      SUM(IF(variable_name IN ('Com_delete',
                               'Com_insert',
                               'Com_update',
                               'Com_replace'), variable_value, 0))
         AS `Total writes`
    FROM  information_schema.GLOBAL_STATUS;
  '''
    result = (0, 0)
    db_conn = pymysql.connect(host=host_address,
                              user='root',
                              password='my-secret-pw',
                              db='information_schema',
                              cursorclass=pymysql.cursors.DictCursor)

    try:
        with db_conn.cursor() as cursor:
            cursor.execute(SQL)
            sql_res = cursor.fetchone()
            logging.info("Read/Write for database %s: %s" % (db_conn, sql_res))

            result = (sql_res.get('Total reads', 0),
                      sql_res.get('Total writes', 0))
    except Exception as e:
        logging.error("Error while requesting database: %s" % e)
    finally:
        db_conn.close()

    return result


def read_write_ratio():
    results = {}
    db_host = None

    # Get the address of the database
    with open(os.path.join(JOB_NAME, 'env'), "r") as f:
        db_host = yaml.load(f)['roles']['database'][0]
        logging.info("Database is %s", db_host)

    for scn in SCENARIOS:
        logging.info("Treating scenario: %s" % scn)
        # Gets total reads/writes in the database; then executes rally
        # scenario; and finally re-gets total reads/writes.
        total_reads_before_scn, total_writes_before_scn = total_reads_writes(
          db_host.address)
        j.rally([scn], "keystone")
        total_reads_after_scn, total_writes_after_scn = total_reads_writes(
          db_host.address)

        # Compute number of reads/writes for this scenario and its ratio
        scn_reads  = total_reads_after_scn - total_reads_before_scn
        scn_writes = total_writes_after_scn - total_writes_before_scn
        scn_rws    = scn_reads + scn_writes

        results[scn] = {
          'reads'  : scn_reads,
          'writes' : scn_writes,
          '%reads' : round((scn_reads / scn_rws) * 100, 2),
          '%writes': round((scn_writes / scn_rws) * 100, 2)
        }

        # Log the ratio result
        logging.info("Ratio for %s: %s" % (scn, results[scn]))

    # Output results
    pprint(results)


if __name__ == '__main__':
    # Do the initial reservation and boilerplate
    init()

    # Run experiment
    read_write_ratio()
