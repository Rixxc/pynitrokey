# -*- coding: utf-8 -*-
#
# Copyright 2020 Nitrokey Developers
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT>, at your option. This file may not be
# copied, modified, or distributed except according to those terms.
import logging
import platform
import subprocess

import click

from pynitrokey.cli.exceptions import CliException
from pynitrokey.helpers import AskUser, local_critical, local_print
from pynitrokey.libnk import BaseLibNitrokey, DeviceNotFound, NitrokeyStorage, RetCode


def connect_nkstorage():
    try:
        nks = NitrokeyStorage()
        nks.connect()
        return nks
    except DeviceNotFound:
        raise CliException("No Nitrokey Storage device found", support_hint=False)

logger = logging.getLogger(__name__)

@click.group()
def storage():
    """Interact with Nitrokey Storage devices, see subcommands."""
    pass


def process_runner(c: str) -> str:
    """Wrapper for running command and returning output, both logged"""
    logger.debug(f'Running {c}')
    local_print(f'* Running \t"{c}"')
    try:
        output = subprocess.check_output(c.split(), stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError as e:
        logger.error(f'Output for "{c}": {e.output}')
        local_print(f'Output for "{c}": {e.output.decode()}')
        raise
    logger.debug(f'Output for "{c}": {output}')
    return output


class DfuTool:
    name = 'dfu-programmer'

    @classmethod
    def is_available(cls):
        """Check whether `name` is on PATH and marked as executable."""
        from shutil import which
        return which(cls.name) is not None

    @classmethod
    def get_version(cls) -> str:
        c = f'{cls.name} --version'
        output = process_runner(c).strip()
        return output

    @classmethod
    def check_version(cls) -> bool:
        # todo choose and use specialized package for version strings management, e.g:
        #   from packaging import version
        ver_string = cls.get_version()
        ver = ver_string.split()[1]
        ver_found = (*map(int, ver.split('.')),)
        ver_required = (0, 6, 1)
        local_print(f'Tool found: {ver_string} -> {ver_found}')
        return ver_found >= ver_required

    @classmethod
    def self_check(cls) -> bool:
        if not cls.is_available():
            local_print(f"{cls.name} is not available. Please install it or use another tool for update.")
            raise click.Abort()

        local_print('')
        cls.check_version()
        local_print('')
        return True


@click.command()
@click.argument('firmware', type=click.Path(exists=True, readable=True))
@click.option(
    "--experimental",
    default=False,
    is_flag=True,
    help="Allow to execute experimental features",
)
def update(firmware: str, experimental):
    """experimental: run assisted update through dfu-programmer tool"""
    if platform.system() != "Linux" or not experimental:
        local_print("This feature is Linux only and experimental, which means it was not tested thoroughly.\n"
                    "Please pass --experimental switch to force running it anyway.")
        raise click.Abort()
    assert firmware.endswith('.hex')

    DfuTool.self_check()

    commands = f"""
        dfu-programmer at32uc3a3256s erase
        dfu-programmer at32uc3a3256s flash --suppress-bootloader-mem "{firmware}"
        dfu-programmer at32uc3a3256s launch
        """

    local_print('Note: During the execution update program will try to connect to the device. '
                'Check your udev rules in case of connection issues.')
    local_print(f'Using firmware path: {firmware}')
    local_print(f'Commands to be executed: {commands}')
    if not click.confirm("Do you want to perform the firmware update now?"):
        logger.info("Update cancelled by user")
        raise click.Abort()

    commands_clean = commands.strip().split('\n')
    for c in commands_clean:
        c = c.strip()
        if not c: continue
        try:
            output = process_runner(c)
            if output:
                local_print(output)
        except subprocess.CalledProcessError as e:
            local_critical(e)

    local_print('')
    local_print('Finished!')
    storage.commands["list"].callback()



@click.command()
def list():
    """list connected devices"""

    local_print(":: 'Nitrokey Storage' keys:")
    devices = NitrokeyStorage.list_devices()
    for dct in devices:
        local_print(f' - {dct}')
    if len(devices) == 1:
        nks = NitrokeyStorage()
        nks.connect()
        local_print(f'Found libnitrokey version: {nks.library_version()}')
        local_print(f'Firmware version: {nks.fw_version}')
        local_print(f'Admin PIN retries: {nks.admin_pin_retries}')
        local_print(f'User PIN retries: {nks.user_pin_retries}')


@click.command()
def enable_update():
    """enable firmware update for NK Storage device

    If the Firmware Password is not in the environment variable NITROPY_FIRMWARE_PASSWORD, it will be prompted from stdin
    """
    password = AskUser(
        "Firmware Password", envvar="NITROPY_FIRMWARE_PASSWORD", hide_input=True
    ).ask()
    local_print("Enabling firmware update mode")
    nks = connect_nkstorage()
    if nks.enable_firmware_update(password) == 0:
        local_print("setting firmware update mode - success!")


@click.command()
def open_encrypted():
    """Unlock the encrypted volume

    If the User PIN is not in the environment variable NITROPY_USER_PIN, it will be prompted from stdin
    """
    password = AskUser("User PIN", envvar="NITROPY_USER_PIN", hide_input=True).ask()
    nks = connect_nkstorage()
    ret = nks.unlock_encrypted_volume(password)
    if not ret.ok:
        if ret == RetCode.WRONG_PASSWORD:
            raise CliException("Wrong user PIN", support_hint=False)
        else:
            raise CliException(
                "Unexpected error unlocking the encrypted volume {}".format(str(ret))
            )


@click.command()
def close_encrypted():
    """Lock the encrypted volume"""
    nks = connect_nkstorage()
    ret = nks.lock_encrypted_volume()
    if not ret.ok:
        raise CliException("Error closing the encrypted volume: {}".format(str(ret)))


@click.command()
def open_hidden():
    """Unlock an hidden volume

    If the hidden volume passphrase is not in the environment variable NITROPY_HIDDEN_PASSPHRASE, it will be prompted from stdin
    """
    password = AskUser(
        "Hidden volume passphrase", envvar="NITROPY_HIDDEN_PASSPHRASE", hide_input=True
    ).ask()
    nks = connect_nkstorage()
    ret = nks.unlock_hidden_volume(password)
    if not ret.ok:
        if ret == RetCode.WRONG_PASSWORD:
            raise CliException("Wrong hidden volume passphrase", support_hint=False)
        else:
            raise CliException(
                "Unexpected error unlocking the hidden volume: {}".format(str(ret))
            )


@click.command()
def close_hidden():
    """Lock the hidden volumes"""
    nks = connect_nkstorage()
    ret = nks.lock_hidden_volume()
    if not ret.ok:
        raise CliException("Error closing the hidden volume: {}".format(str(ret)))


@click.command()
@click.argument(
    "slot",
    type=int,
)
@click.argument(
    "begin",
    type=int,
)
@click.argument("end", type=int)
def create_hidden(slot, begin, end):
    """Create an hidden volume

    SLOT is the slot used for the hidden volume (1-4)\n
    START is where the volume begins expressed in percent of total available storage (0-99)\n
    END is where the volume ends expressed in percent of total available storage (1-100)\n
    If the hidden volume passphrase is not in the environment variable NITROPY_HIDDEN_PASSPHRASE, it will be prompted from stdin
    """
    if not slot in [1, 2, 3, 4]:
        raise CliException("Error: Slot must be between 1 and 4", support_hint=False)
    elif begin > 99 or begin < 0:
        raise CliException("Error: Begin must be between 0 and 99", support_hint=False)
    elif end < 1 or end > 100:
        raise CliException("Error: End must be between 1 and 100", support_hint=False)
    elif begin >= end:
        raise CliException(
            "Error: END must be strictly superior than START", support_hint=False
        )

    password = AskUser(
        "Hidden volume passphrase", envvar="NITROPY_HIDDEN_PASSPHRASE", hide_input=True
    ).ask()

    nks = connect_nkstorage()
    ret = nks.create_hidden_volume(slot - 1, begin, end, password)
    if not ret.ok:
        raise CliException("Error creating the hidden volume: {}".format(str(ret)))


storage.add_command(list)
storage.add_command(enable_update)
storage.add_command(open_encrypted)
storage.add_command(close_encrypted)
storage.add_command(open_hidden)
storage.add_command(close_hidden)
storage.add_command(create_hidden)
storage.add_command(update)
