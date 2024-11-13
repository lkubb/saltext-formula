from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from salt.modules import config as config_mod
from salt.modules import grains as grains_mod
from salt.modules import pillar as pillar_mod

import saltext.formula.modules.map as map_mod


@pytest.fixture
def grains():
    return {
        "os": "Fedora",
        "os_family": "RedHat",
        "osfinger": "Fedora 40",
        "osarch": "x86_64",
        "roles_grain": ["grain_role_a", "grain_role_b"],
        "tplroot_grains": {"config": "data"},
        "selinux": {"enabled": True, "enforced": "Enforcing"},
        "nested": {"grains": {"config": {"data": True}, "switch": 1}},
    }


@pytest.fixture
def opts():
    return {
        "roles_opts": ["opts_role_a", "opts_role_b"],
        "tplroot_opts": {"config": "data"},
        "nested": {"opts": {"config": {"data": True}, "switch": 2}},
    }


@pytest.fixture
def pillar():
    return {
        "roles_pillar": ["pillar_role_a", "pillar_role_b"],
        "tplroot_pillar": {"config": "data"},
        "nested": {"pillar": {"config": {"data": True}, "switch": 3}},
    }


@pytest.fixture
def context():
    return {}


@pytest.fixture
def cp_get_template():
    return MagicMock()


@pytest.fixture
def configure_loader_modules(opts, grains, pillar, context, cp_get_template):
    module_globals = {
        "__salt__": {
            "config.get": config_mod.get,
            "grains.get": grains_mod.get,
            "pillar.get": pillar_mod.get,
            "cp.get_template": cp_get_template,
        },
        "__opts__": opts,
        "__grains__": grains,
        "__pillar__": pillar,
        "__context__": context,
    }
    return {
        map_mod: module_globals,
        config_mod: module_globals,
        grains_mod: module_globals,
        pillar_mod: module_globals,
    }


@pytest.mark.parametrize(
    "matcher,expected",
    (
        (
            "tplroot_opts",
            {"query_method": "config.get", "query": "tplroot_opts", "value": {"config": "data"}},
        ),
        (
            "C@tplroot_opts",
            {"query_method": "config.get", "query": "tplroot_opts", "value": {"config": "data"}},
        ),
        (
            "C@nested:opts:config",
            {"query_method": "config.get", "query": "nested:opts:config", "value": {"data": True}},
        ),
        (
            "C:::@nested:opts:config",
            {"query_method": "config.get", "query": "nested:opts:config", "value": {"data": True}},
        ),
        (
            "C:SUB@nested:opts:config",
            {
                "query_method": "config.get",
                "query": "nested:opts:config",
                "value": {"data": True},
                "option": "SUB",
            },
        ),
        (
            "C:SUB:!@nested!opts!config",
            {
                "query_method": "config.get",
                "query": "nested!opts!config",
                "value": {"data": True},
                "option": "SUB",
            },
        ),
        (
            "C:SUB::@nested:opts:config",
            {
                "query_method": "config.get",
                "query": "nested:opts:config",
                "value": {"data": True},
                "option": "SUB",
            },
        ),
        (
            "G@tplroot_grains",
            {"query_method": "grains.get", "query": "tplroot_grains", "value": {"config": "data"}},
        ),
        (
            "I@tplroot_pillar",
            {"query_method": "pillar.get", "query": "tplroot_pillar", "value": {"config": "data"}},
        ),
        ("defaults.yaml", {"query_method": None, "query": "defaults.yaml", "value": ...}),
        (
            "Y@roles_opts",
            {
                "query_method": "config.get",
                "query": "roles_opts",
                "value": ["opts_role_a", "opts_role_b"],
            },
        ),
        (
            "Y:C@roles_opts",
            {
                "query_method": "config.get",
                "query": "roles_opts",
                "value": ["opts_role_a", "opts_role_b"],
            },
        ),
        (
            "Y:I@roles_pillar",
            {
                "query_method": "pillar.get",
                "query": "roles_pillar",
                "value": ["pillar_role_a", "pillar_role_b"],
            },
        ),
        (
            "Y:G@roles_grain",
            {
                "query_method": "grains.get",
                "query": "roles_grain",
                "value": ["grain_role_a", "grain_role_b"],
            },
        ),
        ("Y:G@os", {"query_method": "grains.get", "query": "os", "value": "Fedora"}),
        (
            "Y:G@selinux:enabled",
            {"query_method": "grains.get", "query": "selinux:enabled", "value": True},
        ),
        (
            "Y:G::@selinux:enabled",
            {"query_method": "grains.get", "query": "selinux:enabled", "value": True},
        ),
        (
            "Y:G:!@selinux!enabled",
            {"query_method": "grains.get", "query": "selinux!enabled", "value": True},
        ),
        ("C@nonexistent", {"query_method": "config.get", "query": "nonexistent", "value": []}),
        ("I@nonexistent", {"query_method": "pillar.get", "query": "nonexistent", "value": []}),
        ("G@nonexistent", {"query_method": "grains.get", "query": "nonexistent", "value": []}),
    ),
)
def test_render_matcher(matcher, expected):
    res = map_mod._render_matcher(matcher)
    for param, val in expected.items():
        assert res[param] == val


def test_data_configuration_override(context, cp_get_template):
    default_formula_config = {
        "sources": ["Y:C@foo"],
        "parameter_dirs": ["tplroot/params"],
        # The following 3 were queried via salt["config.get"](f"{tplroot}:(strategy|merge_lists)")
        # in libmapstack.jinja. The merge strategy was used in both
        # config.get and slsutil.merge.
        "config_get_strategy": "merge",
        "default_merge_strategy": "overwrite",
        "default_merge_lists": True,
        "post_map": "post_map.py",
        "post_map_template": "py",
        "cache": False,
    }
    with patch("saltext.formula.modules.map.stack", autospec=True) as stack:
        stack.side_effect = ({"values": default_formula_config}, {"values": {}})
        res = map_mod.data("tplroot/foo/bar", config_get_strategy="foobar")

    assert res == {"map_jinja": default_formula_config}
    assert stack.call_count == 2
    # Ensure the passed config_get_strategy is used in the first call to stack
    assert stack.call_args_list[0].kwargs["config_get_strategy"] == "foobar"
    for param, val in default_formula_config.items():
        if param in ("post_map", "post_map_template", "cache"):
            continue
        assert stack.call_args_list[1].kwargs[param] == val
    cp_get_template.assert_called_once()
    assert (
        cp_get_template.call_args.args[0] == f"salt://tplroot/{default_formula_config['post_map']}"
    )
    assert (
        cp_get_template.call_args.kwargs["template"] == default_formula_config["post_map_template"]
    )
    # Ensure disabling cache works
    assert not context[map_mod.CKEY]


@pytest.fixture
def stack_mock():
    def _stack(*args, default_values=None, **kwargs):  # pylint: disable=unused-argument
        return {"values": default_values or {}}

    with patch("saltext.formula.modules.map.stack", autospec=True, side_effect=_stack) as stack:
        yield stack


@pytest.mark.usefixtures("stack_mock")
def test_data_no_post_map(cp_get_template):
    map_mod.data("tplroot/foo/bar", post_map=False)
    cp_get_template.assert_not_called()


@pytest.mark.usefixtures("stack_mock")
def test_data_no_duplicate_defaults_yaml():
    res = map_mod.data("tplroot/foo/bar", sources=["Y:G@os", "defaults.yaml", "foobar"])
    assert res["map_jinja"]["sources"].count("defaults.yaml") == 1
