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

Change *conf.yaml* according to your needs

## Launch

Launch with `./cli.py deploy`
