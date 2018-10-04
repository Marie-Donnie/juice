# juice

A tool to test the performance of MariaDB, Galera and CockroachDB with OpenStack using [enoslib](https://github.com/BeyondTheClouds/enoslib)


## Installation

On a Grid'5000 frontend:

```bash
git clone https://github.com/Marie-Donnie/juice.git
cd juice
```

```bash
virtualenv -p python3 venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt

```

## Configuration

There is a sample configuration you can use `cp conf.yaml.sample conf.yaml`
You can then change *conf.yaml* according to your needs. For instance,
change the value of database from cockroachdb to mariadb or galera to go
with the mariadb or a galera replicated database.

## Launch

Launch with `./juice.py deploy`.

Once it has been launched, you can destroy the containers using `./juice destroy` and then restart them with `./juice deploy`.

## Full experiment

In the experiments folder you'll find different scenarios you can tweak to accomodate to your needs. For example, if you want to test the impact of latency on the cluster:
```bash
cd experiments
python latency-impact.py
```

### Getting information about the used environment

Use `./juice.py info` to get informations about current environment. You can format the results into *json*, *yaml* and *pickle* using `./juice.py info --out <format>`.

### Benchmarking

#### Sysbench

You can launch sysbench tests afterwards using `./juice stress`.

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

### Emulate

You can emulate different constraints on the network with emulate by changing the *juice.py* (or directly in the experiment file if you use one). The constraints look like that:
```python
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
```
The *constraints* are applicable to a specific network (network) for different roles (src and dst). You can change the delay, rate and packet loss of the network. There are also global choices for the network, with a default delay and rate, applicable if need be on specific roles.


### Backup

Backup important metrics using `./juice.py backup`.

### Destroy

The destroy tasks, called with `./juice.py destroy` removes all dockers and unmount volumes.

### Induce faults

You can induce faults in your deployment with os-faults.
To do that, `cp faults.yaml.sample faults.yaml` then change `faults.yaml` according to your needs. The syntax is as follows:
```
- name: Restart keystone
  type: service
  action: restart
  targets:
    - definition: keystone
      when:
	    ips:
		   - xxx.xxx.xxx.xxx
        role: database
        network: database_network
```
The parameters are:
```
name - the name of the task
type - the thing you want to act on (one of service/system_service/nodes/container)
action - the action you want to make (see https://os-faults.readthedocs.io/en/latest/api.html for a list of action that can be completed)
targets - the targets of the action (list)
definition - the name of the service or container you want to act on
when - defines a set of constraints to apply the action on
	ips - a list of ips; ips and role/network are mutually exclusive
	role - the role you defined; ips and role are mutually exclusive
	network - a specific network you defined; ips and network are mutually exclusive (optional)
```

## Help

```
Tool to test the performances of MariaDB, Galera and CockroachdB with OpenStack on Grid'5000 using Enoslib

Usage:
    juice [-h | --help] [-v | --version] <command> [<args>...]

Options:
    -h --help      Show this help
    -v --version   Show version number

Commands:
    deploy         Claim resources from g5k and configure them
    openstack      Add OpenStack Keystone to the deployment
    rally          Benchmark the Openstack
    stress         Launch sysbench tests (after a deployment)
	  emulate        Emulate network using tc
    backup         Backup the environment
    destroy        Destroy all the running dockers (not the resources)
    info           Show information of the actual deployment

Run 'juice COMMAND --help' for more information on a command
```
