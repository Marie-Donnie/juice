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

Launch with `./juice.py deploy` or `./juice.py deploy --db=<db>` with <db> being 'cockroachdb' (default) or 'mariadb'

## Help

```
Tool to test Keystone over Galera and CockroachdB on Grid'5000 using Enoslib

Usage:
    juice [-h | --help] [-v | --version] <command> [<args>...]

Options:
    -h --help      Show this help
    -v --version   Show version number

Commands:
    deploy         Claim resources from g5k and configure them
    g5k            Claim resources on Grid'5000 (from a frontend)
    inventory      Generate the Ansible inventory file
    prepare        Configure the resources
    destroy        Destroy all the running dockers (not destroying the resources)
    backup         Backup the environment
```
