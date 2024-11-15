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
        "id": "testminion",
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
            "roles_opts",
            {
                "query_method": "config.get",
                "query": "roles_opts",
                "value": ["opts_role_a", "opts_role_b"],
            },
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
        ("Y:G@os", {"query_method": "grains.get", "query": "os", "value": ["Fedora"]}),
        (
            "Y:G@selinux:enabled",
            {"query_method": "grains.get", "query": "selinux:enabled", "value": ["True"]},
        ),
        (
            "Y:G::@selinux:enabled",
            {"query_method": "grains.get", "query": "selinux:enabled", "value": ["True"]},
        ),
        (
            "Y:G:!@selinux!enabled",
            {"query_method": "grains.get", "query": "selinux!enabled", "value": ["True"]},
        ),
        (
            "C@nonexistent",
            {"query_method": "config.get", "query": "nonexistent", "value": map_mod.UNSET},
        ),
        (
            "I@nonexistent",
            {"query_method": "pillar.get", "query": "nonexistent", "value": map_mod.UNSET},
        ),
        (
            "G@nonexistent",
            {"query_method": "grains.get", "query": "nonexistent", "value": map_mod.UNSET},
        ),
    ),
)
def test_render_matcher(matcher, expected):
    res = map_mod._render_matcher(matcher)
    for param, val in expected.items():
        if param == "value" and val is map_mod.UNSET:
            assert res[param] is val
        else:
            assert res[param] == val


@pytest.mark.parametrize(
    "matcher,expected",
    (
        ("roles_opts", ["opts_role_a", "opts_role_b"]),
        ("selinux", ["enabled", "enforced"]),
        ("selinux:enabled", ["True"]),
        ("C::!@selinux!enabled", ["True"]),
    ),
)
def test_render_matcher_for_path_rendering(matcher, expected):
    res = map_mod._render_matcher(matcher, for_path_rendering=True)
    assert res["query_method"] == "config.get"
    assert res["type"] == "C"
    assert res["query"] == matcher.split("@")[-1]
    assert res["value"] == expected


@pytest.mark.parametrize("matcher", ("defaults.yaml", "Y:C@roles_opts"))
def test_render_matcher_for_path_rendering_yaml_disallowed(matcher):
    with pytest.raises(ValueError, match=f".*not allowed in this context.*{matcher}$"):
        map_mod._render_matcher(matcher, for_path_rendering=True)


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


@pytest.mark.usefixtures("stack_mock")
@pytest.mark.parametrize(
    "matchers,path_prefix,files_dir,default_dir,use_subpath,include_query,expected",
    (
        (
            None,
            None,
            None,
            None,
            False,
            True,
            [
                "tplroot/files/id/testminion/foo",
                "tplroot/files/id/testminion/foo.jinja",
                "tplroot/files/os_family/RedHat/foo",
                "tplroot/files/os_family/RedHat/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            ["os_family", ""],
            None,
            None,
            None,
            False,
            True,
            [
                "tplroot/files/os_family/RedHat/foo",
                "tplroot/files/os_family/RedHat/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            ["os_family"],
            None,
            None,
            None,
            False,
            False,
            [
                "tplroot/files/RedHat/foo",
                "tplroot/files/RedHat/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            ["os_family"],
            None,
            None,
            None,
            False,
            True,
            [
                "tplroot/files/os_family/RedHat/foo",
                "tplroot/files/os_family/RedHat/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            ["selinux:enabled"],
            None,
            None,
            None,
            False,
            True,
            [
                "tplroot/files/selinux:enabled/True/foo",
                "tplroot/files/selinux:enabled/True/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            ["C@selinux:enabled"],
            None,
            None,
            None,
            False,
            True,
            [
                "tplroot/files/selinux:enabled/True/foo",
                "tplroot/files/selinux:enabled/True/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            ["C::!@selinux!enabled"],
            None,
            None,
            None,
            False,
            True,
            [
                "tplroot/files/selinux!enabled/True/foo",
                "tplroot/files/selinux!enabled/True/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            ["I@roles_pillar"],
            None,
            None,
            None,
            False,
            True,
            [
                "tplroot/files/roles_pillar/pillar_role_a/foo",
                "tplroot/files/roles_pillar/pillar_role_b/foo",
                "tplroot/files/roles_pillar/pillar_role_a/foo.jinja",
                "tplroot/files/roles_pillar/pillar_role_b/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            ["I@roles_pillar"],
            None,
            None,
            None,
            False,
            False,
            [
                "tplroot/files/pillar_role_a/foo",
                "tplroot/files/pillar_role_b/foo",
                "tplroot/files/pillar_role_a/foo.jinja",
                "tplroot/files/pillar_role_b/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            ["I@roles_grains"],
            None,
            None,
            None,
            False,
            True,
            [
                "tplroot/files/roles_grains/foo",
                "tplroot/files/roles_grains/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            None,
            None,
            None,
            None,
            True,
            True,
            [
                "tplroot/foo/bar/files/id/testminion/foo",
                "tplroot/foo/bar/files/id/testminion/foo.jinja",
                "tplroot/foo/bar/files/os_family/RedHat/foo",
                "tplroot/foo/bar/files/os_family/RedHat/foo.jinja",
                "tplroot/foo/bar/files/default/foo",
                "tplroot/foo/bar/files/default/foo.jinja",
                "tplroot/foo/files/id/testminion/foo",
                "tplroot/foo/files/id/testminion/foo.jinja",
                "tplroot/foo/files/os_family/RedHat/foo",
                "tplroot/foo/files/os_family/RedHat/foo.jinja",
                "tplroot/foo/files/default/foo",
                "tplroot/foo/files/default/foo.jinja",
                "tplroot/files/id/testminion/foo",
                "tplroot/files/id/testminion/foo.jinja",
                "tplroot/files/os_family/RedHat/foo",
                "tplroot/files/os_family/RedHat/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            None,
            "altprefix",
            None,
            None,
            False,
            True,
            [
                "altprefix/files/id/testminion/foo",
                "altprefix/files/id/testminion/foo.jinja",
                "altprefix/files/os_family/RedHat/foo",
                "altprefix/files/os_family/RedHat/foo.jinja",
                "altprefix/files/default/foo",
                "altprefix/files/default/foo.jinja",
            ],
        ),
        (
            None,
            None,
            "alt_files",
            None,
            False,
            True,
            [
                "tplroot/alt_files/id/testminion/foo",
                "tplroot/alt_files/id/testminion/foo.jinja",
                "tplroot/alt_files/os_family/RedHat/foo",
                "tplroot/alt_files/os_family/RedHat/foo.jinja",
                "tplroot/alt_files/default/foo",
                "tplroot/alt_files/default/foo.jinja",
            ],
        ),
        (
            None,
            None,
            None,
            "alt_default",
            False,
            True,
            [
                "tplroot/files/id/testminion/foo",
                "tplroot/files/id/testminion/foo.jinja",
                "tplroot/files/os_family/RedHat/foo",
                "tplroot/files/os_family/RedHat/foo.jinja",
                "tplroot/files/alt_default/foo",
                "tplroot/files/alt_default/foo.jinja",
            ],
        ),
        (
            None,
            "alt_prefix",
            "alt_files",
            "alt_default",
            False,
            True,
            [
                "alt_prefix/alt_files/id/testminion/foo",
                "alt_prefix/alt_files/id/testminion/foo.jinja",
                "alt_prefix/alt_files/os_family/RedHat/foo",
                "alt_prefix/alt_files/os_family/RedHat/foo.jinja",
                "alt_prefix/alt_files/alt_default/foo",
                "alt_prefix/alt_files/alt_default/foo.jinja",
            ],
        ),
        (
            None,
            "global_files",
            "",
            None,
            False,
            True,
            [
                "global_files/id/testminion/foo",
                "global_files/id/testminion/foo.jinja",
                "global_files/os_family/RedHat/foo",
                "global_files/os_family/RedHat/foo.jinja",
                "global_files/default/foo",
                "global_files/default/foo.jinja",
            ],
        ),
        (
            ["a/static/path"],
            None,
            None,
            None,
            False,
            True,
            [
                "tplroot/files/a/static/path/foo",
                "tplroot/files/a/static/path/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
        (
            ["/an/absolute/static/path/"],
            None,
            None,
            None,
            False,
            True,
            [
                "tplroot/files/an/absolute/static/path/foo",
                "tplroot/files/an/absolute/static/path/foo.jinja",
                "tplroot/files/default/foo",
                "tplroot/files/default/foo.jinja",
            ],
        ),
    ),
)
def test_tofs(matchers, path_prefix, files_dir, default_dir, use_subpath, include_query, expected):
    res = map_mod.tofs(
        "tplroot/foo/bar",
        ["foo", "foo.jinja"],
        default_matchers=matchers,
        include_query=include_query,
        use_subpath=use_subpath,
        path_prefix=path_prefix,
        files_dir=files_dir if files_dir is not None else "files",
        default_dir=default_dir if default_dir is not None else "default",
    )
    expected = [f"salt://{path}" for path in expected]
    assert res == expected


@pytest.mark.usefixtures("stack_mock")
def test_tofs_absolute_sources():
    res = map_mod.tofs(
        "tplroot/foo/bar",
        ["/etc/foo"],
    )
    assert res == [
        "salt://tplroot/files/id/testminion/etc/foo",
        "salt://tplroot/files/os_family/RedHat/etc/foo",
        "salt://tplroot/files/default/etc/foo",
    ]


@pytest.mark.parametrize(
    "overrides,expected",
    (
        (
            {
                "path_prefix": "alt_root",
                "files_switch": ["os"],
                "include_query": False,
                "dirs": {
                    "default": "alt_default",
                    "files": "alt_files",
                },
            },
            [
                "alt_root/alt_files/Fedora/foo",
                "alt_root/alt_files/Fedora/foo.jinja",
                "alt_root/alt_files/alt_default/foo",
                "alt_root/alt_files/alt_default/foo.jinja",
            ],
        ),
        (
            {
                "path_prefix": "alt_root",
                "files_switch": ["os"],
                "include_query": False,
                "dirs": {
                    "default": "alt_default",
                },
            },
            [
                "alt_root/base_files/Fedora/foo",
                "alt_root/base_files/Fedora/foo.jinja",
                "alt_root/base_files/alt_default/foo",
                "alt_root/base_files/alt_default/foo.jinja",
            ],
        ),
        (
            {
                "path_prefix": "alt_root",
                "files_switch": ["os"],
                "include_query": False,
                "dirs": {
                    "files": "alt_files",
                },
            },
            [
                "alt_root/alt_files/Fedora/foo",
                "alt_root/alt_files/Fedora/foo.jinja",
                "alt_root/alt_files/base_default/foo",
                "alt_root/alt_files/base_default/foo.jinja",
            ],
        ),
        (
            {"files_switch": ["os_family"], "source_files": {"foo-managed": ["alt_foo"]}},
            [
                "base_root/base_files/os_family/RedHat/alt_foo",
                "base_root/base_files/os_family/RedHat/foo",
                "base_root/base_files/os_family/RedHat/foo.jinja",
                "base_root/base_files/base_default/alt_foo",
                "base_root/base_files/base_default/foo",
                "base_root/base_files/base_default/foo.jinja",
            ],
        ),
    ),
)
def test_tofs_override(overrides, expected):
    res = map_mod.tofs(
        "tplroot/foo/bar",
        ["foo", "foo.jinja"],
        default_matchers=("id", "os_family"),
        include_query=True,
        use_subpath=False,
        config={"tofs": overrides, "map_jinja": {"config_get_strategy": None}},
        lookup="foo-managed",
        path_prefix="base_root",
        files_dir="base_files",
        default_dir="base_default",
    )
    expected = [f"salt://{path}" for path in expected]
    assert res == expected


def test_subpath_matcher_override():
    config = {
        "tofs": {
            "files_switch": ["id"],
            "source_files": {
                "foo-managed": ["alt_foo"],
            },
        },
        "files_switch": ["os_family"],
        "foo": {
            "files_switch": ["osarch"],
            "bar": {
                "files_switch": ["os"],
            },
        },
        "map_jinja": {
            "config_get_strategy": None,
        },
    }
    res = map_mod.tofs(
        "tplroot/foo/bar/baz",
        ["foo", "foo.jinja"],
        use_subpath=True,
        config=config,
        path_prefix="alt_root",
        files_dir="base_files",
        default_dir="base_default",
    )
    assert res == [
        "salt://alt_root/foo/bar/baz/base_files/id/testminion/foo",
        "salt://alt_root/foo/bar/baz/base_files/id/testminion/foo.jinja",
        "salt://alt_root/foo/bar/baz/base_files/base_default/foo",
        "salt://alt_root/foo/bar/baz/base_files/base_default/foo.jinja",
        "salt://alt_root/foo/bar/base_files/os/Fedora/foo",
        "salt://alt_root/foo/bar/base_files/os/Fedora/foo.jinja",
        "salt://alt_root/foo/bar/base_files/base_default/foo",
        "salt://alt_root/foo/bar/base_files/base_default/foo.jinja",
        "salt://alt_root/foo/base_files/osarch/x86_64/foo",
        "salt://alt_root/foo/base_files/osarch/x86_64/foo.jinja",
        "salt://alt_root/foo/base_files/base_default/foo",
        "salt://alt_root/foo/base_files/base_default/foo.jinja",
        "salt://alt_root/base_files/os_family/RedHat/foo",
        "salt://alt_root/base_files/os_family/RedHat/foo.jinja",
        "salt://alt_root/base_files/base_default/foo",
        "salt://alt_root/base_files/base_default/foo.jinja",
    ]
