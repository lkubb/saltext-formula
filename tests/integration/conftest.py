from pathlib import Path

import pytest
from saltfactories import cli
from saltfactories.daemons.master import SaltMaster
from saltfactories.daemons.minion import SaltMinion

from tests._types import Yielder


@pytest.fixture(scope="package")
def master(master: SaltMaster) -> Yielder[SaltMaster]:  # pragma: no cover
    with master.started():
        yield master


@pytest.fixture(scope="package")
def minion(minion: SaltMinion) -> Yielder[SaltMinion]:  # pragma: no cover
    with minion.started():
        yield minion


@pytest.fixture
def salt_run_cli(master: SaltMaster) -> cli.run.SaltRun:  # pragma: no cover
    return master.salt_run_cli()


@pytest.fixture
def salt_cli(master: SaltMaster) -> cli.salt.SaltCli:  # pragma: no cover
    return master.salt_cli()


@pytest.fixture
def salt_call_cli(minion: SaltMinion) -> cli.call.SaltCall:  # pragma: no cover
    return minion.salt_call_cli()


@pytest.fixture(scope="module")
def salt_ssh_cli(
    master: SaltMaster,
    salt_ssh_roster_file: Path,
    sshd_config_dir: Path,
    known_hosts_file: Path,  # pylint: disable=unused-argument
) -> cli.ssh.SaltSsh:  # pragma: no cover
    return master.salt_ssh_cli(
        timeout=180,
        roster_file=salt_ssh_roster_file,
        target_host="localhost",
        client_key=str(sshd_config_dir / "client_key"),
    )
