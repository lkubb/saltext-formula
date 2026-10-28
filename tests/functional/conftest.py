from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import pytest
from saltfactories.utils import random_string
from saltfactories.utils.functional import Loaders

if TYPE_CHECKING:
    from _pytest.tmpdir import TempPathFactory
    from saltfactories.manager import FactoriesManager  # Needs lazy import

    from tests._types import SaltLoader
    from tests._types import Yielder

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def minion_id() -> str:  # pragma: no cover
    # Random to avoid factory directory collisions, e.g. with pytest-xdist
    return random_string("func-tests-minion-")


@pytest.fixture(scope="module")
def state_tree(tmp_path_factory: TempPathFactory) -> Yielder[Path]:  # pragma: no cover
    state_tree_path = tmp_path_factory.mktemp("state-tree-base")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def state_tree_prod(tmp_path_factory: TempPathFactory) -> Yielder[Path]:  # pragma: no cover
    state_tree_path = tmp_path_factory.mktemp("state-tree-prod")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def minion_config_defaults() -> dict[str, Any]:  # pragma: no cover
    """
    Functional test modules can provide this fixture to tweak the default
    configuration dictionary passed to the minion factory
    """
    return {}


@pytest.fixture(scope="module")
def minion_config_overrides() -> dict[str, Any]:  # pragma: no cover
    """
    Functional test modules can provide this fixture to tweak the configuration
    overrides dictionary passed to the minion factory
    """
    return {}


@pytest.fixture(scope="module")
def minion_opts(
    salt_factories: FactoriesManager,
    minion_id: str,
    state_tree: Path,
    state_tree_prod: Path,
    minion_config_defaults: dict[str, Any],
    minion_config_overrides: dict[str, Any],
) -> dict[str, Any]:  # pragma: no cover
    minion_config_overrides.update(
        {
            "file_client": "local",
            "file_roots": {
                "base": [
                    str(state_tree),
                ],
                "prod": [
                    str(state_tree_prod),
                ],
            },
        }
    )
    factory = salt_factories.salt_minion_daemon(
        minion_id,
        defaults=minion_config_defaults or None,
        overrides=minion_config_overrides,
    )
    return factory.config.copy()


@pytest.fixture(scope="module")
def master_config_defaults() -> dict[str, Any]:  # pragma: no cover
    """
    Functional test modules can provide this fixture to tweak the default
    configuration dictionary passed to the master factory
    """
    return {}


@pytest.fixture(scope="module")
def master_config_overrides() -> dict[str, Any]:  # pragma: no cover
    """
    Functional test modules can provide this fixture to tweak the configuration
    overrides dictionary passed to the master factory
    """
    return {}


@pytest.fixture(scope="module")
def master_opts(
    salt_factories: FactoriesManager,
    state_tree: Path,
    state_tree_prod: Path,
    master_config_defaults: dict[str, Any],
    master_config_overrides: dict[str, Any],
) -> dict[str, Any]:  # pragma: no cover
    master_config_overrides.update(
        {
            "file_client": "local",
            "file_roots": {
                "base": [
                    str(state_tree),
                ],
                "prod": [
                    str(state_tree_prod),
                ],
            },
        }
    )
    factory = salt_factories.salt_master_daemon(
        "func-tests-master-opts",
        defaults=master_config_defaults or None,
        overrides=master_config_overrides,
    )
    return factory.config.copy()


@pytest.fixture(scope="module")
def loaders(minion_opts: dict[str, Any]) -> Loaders:  # pragma: no cover
    return Loaders(minion_opts, loaded_base_name=f"{__name__}.loaded")


@pytest.fixture(autouse=True)
def reset_loaders_state(loaders: Loaders) -> Yielder[None]:  # pragma: no cover
    try:
        # Run the tests
        yield
    finally:
        # Reset the loaders state
        loaders.reset_state()


@pytest.fixture(scope="module")
def modules(loaders: Loaders) -> SaltLoader:  # pragma: no cover
    return loaders.modules


@pytest.fixture(scope="module")
def states(loaders: Loaders) -> SaltLoader:  # pragma: no cover
    return loaders.states
