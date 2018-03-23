# juice

A tool to test OpenStack with MariaDB and CockroachDB using [enoslib](https://github.com/BeyondTheClouds/enoslib)


## Installation

On a Grid'5000 frontend:

```bash
git clone https://github.com/Marie-Donnie/juice.git
cd juice
```

```bash
virtualenv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Configuration

Change *conf.yaml* according to your needs.

## Launch

Launch with `./juice.py deploy` or `./juice.py deploy` with db being 'cockroachdb' (default) or 'mariadb'.

Once it has been launched, you can destroy the containers using `./juice destroy` and then restart them with `./juice prepare`.

### Getting information about the used environment

Use `./juice.py info` to get informations about current environment. You can format the results into *json*, *yaml* and *pickle* using `./juice.py info --out <format>`.

### Benchmarking

#### Sysbench

You can launch sysbench tests afterwards using `./juice stess`.

#### Rally (CockroachDB only for now)

1. Launch devstack (only Keystone service) using `./juice openstack`. This will deploy Keystone on every database nodes. (- Note from 02/22/18 - this is a bit unstable for now, you may have to use it several times until it succeeds. You can check the logs using the command ansible will provide you before launching *stack.sh*)
2. You can use either `./juice.py rally --files <service-name>/<scenario>` to launch one or several specific scenarios or `./juice.py rally --directory <service-name>` to launch every scenarios for the given service.
   * tip1: you can use `./juice.py rally --directory .` to launch every scenarios
   * tip2: you can use `./juice.py rally` to execute every keystone scenarios

### Grafana

There are two data sources for Grafana, using InfluxDB: [collectd](https://collectd.org/) (only for MariaDB currently) and [cAdvisor](https://github.com/google/cadvisor).

To monitor activity on your databases:
1. Open a ssh tunnel in a shell using`ssh -NL 8080:<control-node>:3000 <location-of-the-node>.g5k` (assuming you have followed [Grid'5000 tutorial](https://www.grid5000.fr/mediawiki/index.php/SSH#Using_SSH_with_ssh_proxycommand_setup_to_access_hosts_inside_Grid.275000)). You can check which node is used using `./juice.py info` and find control node.
2. Go to <http://localhost:8080/> in your browser
3. You can check your data sources in *Configuration* -> *Data Sources*
4. There are several dashboard you can import for cadvisor and collectd:
   * [Service - MySQL InnoDB Metrics](https://grafana.com/dashboards/564) provides performance metrics about MariaDB Innodb engine
   * [Service - MySQL Metrics](https://grafana.com/dashboards/561) provides performance metrics for MariaDB
   * For cAdvisor, you have to make your own dashboards using whatever metrics you need because the one made for cAdvisor/InfluxDB does not work with Juice

### Backup

Backup important metrics using `./juice.py backup`.

## Help

```
Tool to test Keystone Federation over MariaDB on Grid'5000 using Enoslib

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
```
