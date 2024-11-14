import contextlib
import json
from pathlib import Path

import pytest

pytest.importorskip(
    "salt.version",
    minversion="3007",
    reason="relies on cp.get_template wrapper, only present in Salt 3007.0+",
)

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Salt-SSH is not available for Windows"),
]


@pytest.fixture(scope="module", autouse=True)
def ssh_opts(master):
    ssh_opts = {
        "ssh_minion_opts": {
            "tplroot": {
                "data_source": "opts",
                "opts": True,
            },
            "roles": ["db", "db_master"],
        },
    }
    with pytest.helpers.temp_file(
        "ssh_opts.conf",
        json.dumps(ssh_opts),
        Path(master.config_dir) / "master.d",
    ):
        yield


@pytest.fixture(scope="module", autouse=True)
def formula_setup(master):
    param_files = {
        "defaults.yaml": (
            """\
            values:
              data_source: defaults_yaml
              defaults_yaml: true
            """
        ),
        "roles/db.yaml.jinja": (
            """\
            values:
              data_source: db_yaml
              db_yaml: true
              previous: {{ mapdata["data_source"] }}
            """
        ),
        "map_jinja.yaml": (
            """\
            values:
              sources:
                - defaults.yaml
                - Y:G@os
                - C@{{ tplroot }}
                - Y:C@roles
                - Y:G@id
            """
        ),
    }
    with contextlib.ExitStack() as stack:
        for path, contents in param_files.items():
            stack.enter_context(
                master.state_tree.base.temp_file(f"tplroot/parameters/{path}", contents)
            )
        yield


@pytest.fixture
def post_map(master):
    contents = """\
        {%- do mapdata.update({"data_source": "post_map", "post_map": true}) %}
        """
    with master.state_tree.base.temp_file("tplroot/post-map.jinja", contents):
        yield


@pytest.fixture(scope="module", autouse=True)
def _cp_wrapper(master, salt_ssh_cli):
    # The wrapper returns minion paths.
    # Since we're testing on the same node, the path would exist
    # when running in the test suite, but not when running for real.
    # This wrapper deletes the minion cache path to ensure we validate
    # the map.data wrapper converts it to the master cache path.
    # We cannot override single functions of inbuilt modules, so we need
    # to provide all functions our wrapper is going to use.
    contents = """\
        from pathlib import Path

        import salt.utils.context
        from salt.client.ssh.wrapper import cp

        __virtualname__ = "cp"


        def __virtual__():
            return __virtualname__


        def _call_cp(func, args, kwargs):
            with salt.utils.context.func_globals_inject(
                func,
                __opts__=__opts__,
                __salt__=__salt__,
                __grains__=__grains__,
                __pillar__=__pillar__,
                __context__=__context__,
            ):
                return func(*args, **kwargs)


        def get_template(*args, **kwargs):
            res = _call_cp(cp.get_template, args, kwargs)
            if res:
                Path(res).unlink()
            return res


        def convert_cache_path(*args, **kwargs):
            return _call_cp(cp.convert_cache_path, args, kwargs)


        def is_wrapped_correctly():
            return True
        """
    with master.state_tree.base.temp_file("_wrapper/cp.py", contents):
        res = master.salt_run_cli().run("saltutil.sync_all")
        assert res.returncode == 0
        assert "wrapper.cp" in res.data["wrapper"]
        res = salt_ssh_cli.run("cp.is_wrapped_correctly")
        assert res.returncode == 0
        assert res.data is True
        yield


def test_data(salt_ssh_cli):
    res = salt_ssh_cli.run("map.data", "tplroot/foo/bar")
    assert res.returncode == 0
    _assert_data(res.data, "db_yaml")


@pytest.mark.usefixtures("post_map")
def test_data_post_map(salt_ssh_cli):
    res = salt_ssh_cli.run("map.data", "tplroot/foo/bar")
    assert res.returncode == 0
    _assert_data(res.data, "post_map", "post_map")


@pytest.fixture
def _state_data(master):
    contents = """\
        foo:
          test.show_notification:
            - text: '{{ salt["map.data"](tpldir) | json }}'
        """
    with master.state_tree.base.temp_file("tplroot/_mapdata.sls", contents):
        yield "tplroot._mapdata"


def test_data_in_template(salt_ssh_cli, _state_data):
    res = salt_ssh_cli.run("state.show_sls", _state_data)
    assert res.returncode == 0
    assert res.data
    _assert_data(res.data, "db_yaml", show_sls=True)


@pytest.mark.usefixtures("post_map")
def test_data_in_template_with_post_map(salt_ssh_cli, _state_data):
    res = salt_ssh_cli.run("state.show_sls", _state_data)
    assert res.returncode == 0
    assert res.data
    _assert_data(res.data, "post_map", "post_map", show_sls=True)


def _assert_data(data, source, *extra_keys, show_sls=False):
    if show_sls:
        for param in data["foo"]["test"]:
            if "text" not in param:
                continue
            data = json.loads(param["text"])
            break
        else:
            raise RuntimeError("Failed parsing state.show_sls output")
    assert data["data_source"] == source
    assert data["previous"] == "opts"
    for param in ("defaults_yaml", "db_yaml", "opts", *extra_keys):
        assert param in data
