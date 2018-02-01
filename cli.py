#!/usr/bin/env python

import os
import logging
import yaml

import click

import tasks


logging.basicConfig(level=logging.DEBUG)

DEFAULT_CONF = os.path.dirname(os.path.realpath(__file__))
DEFAULT_CONF = os.path.join(DEFAULT_CONF, "conf.yaml")


# cli part
@click.group()
def cli():
    pass


@cli.command(help="Claim resources from g5k and configure them")
@click.option("--conf",
              default=DEFAULT_CONF,
              help="Configuration file to use")
@click.option("--env",
              help="Use this environment directory instead of the default one")
def deploy(conf, env):
    config = {}
    with open(conf) as f:
        config = yaml.load(f)

    tasks.g5k(config=config, env=env)
    tasks.inventory()
    tasks.prepare()


@cli.command(help="Claim resources on Grid'5000 (from a frontend)")
def g5k():
    tasks.g5k()


@cli.command(help="Generate the Ansible inventory file")
def inventory():
    tasks.inventory()


@cli.command(help="Configure the resources")
def prepare():
    tasks.prepare()


@cli.command(
    help="Destroy all the running dockers (not destroying the resources)")
def destroy():
    tasks.destroy()


@cli.command(help="Backup the environment")
def backup():
    tasks.backup()


if __name__ == "__main__":
    cli()
