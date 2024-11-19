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
    "matcher,cls,exp_yaml,attrs,value",
    (
        (
            "roles_opts",
            map_mod.ConfigMatcher,
            True,
            {
                "query": "roles_opts",
                "options": (),
                "delimiter": ":",
            },
            ["opts_role_a", "opts_role_b"],
        ),
        (
            "C@tplroot_opts",
            map_mod.ConfigMatcher,
            False,
            {"query": "tplroot_opts", "options": (), "delimiter": ":"},
            {"config": "data"},
        ),
        (
            "C@nested:opts:config",
            map_mod.ConfigMatcher,
            False,
            {"query": "nested:opts:config", "options": (), "delimiter": ":"},
            {"data": True},
        ),
        (
            "C:::@nested:opts:config",
            map_mod.ConfigMatcher,
            False,
            {"query": "nested:opts:config", "options": (), "delimiter": ":"},
            {"data": True},
        ),
        (
            "C:SUB@nested:opts:config",
            map_mod.ConfigMatcher,
            False,
            {"query": "nested:opts:config", "options": ("SUB",), "delimiter": ":"},
            {"nested:opts:config": {"data": True}},
        ),
        (
            "C:SUB:!@nested!opts!config",
            map_mod.ConfigMatcher,
            False,
            {"query": "nested!opts!config", "options": ("SUB",), "delimiter": "!"},
            {"nested!opts!config": {"data": True}},
        ),
        (
            "C:SUB::@nested:opts:config",
            map_mod.ConfigMatcher,
            False,
            {"query": "nested:opts:config", "options": ("SUB",), "delimiter": ":"},
            {"nested:opts:config": {"data": True}},
        ),
        (
            "G@tplroot_grains",
            map_mod.GrainsMatcher,
            False,
            {"query": "tplroot_grains", "options": (), "delimiter": ":"},
            {"config": "data"},
        ),
        (
            "I@tplroot_pillar",
            map_mod.PillarMatcher,
            False,
            {"query": "tplroot_pillar", "options": (), "delimiter": ":"},
            {"config": "data"},
        ),
        (
            "defaults.yaml",
            map_mod.StaticMatcher,
            True,
            {"query": "defaults.yaml", "options": (), "delimiter": ":"},
            ["defaults.yaml"],
        ),
        (
            "Y@roles_opts",
            map_mod.ConfigMatcher,
            True,
            {
                "query": "roles_opts",
                "options": (),
                "delimiter": ":",
            },
            ["opts_role_a", "opts_role_b"],
        ),
        (
            "Y:C@roles_opts",
            map_mod.ConfigMatcher,
            True,
            {
                "query": "roles_opts",
                "options": (),
                "delimiter": ":",
            },
            ["opts_role_a", "opts_role_b"],
        ),
        (
            "Y:I@roles_pillar",
            map_mod.PillarMatcher,
            True,
            {
                "query": "roles_pillar",
                "options": (),
                "delimiter": ":",
            },
            ["pillar_role_a", "pillar_role_b"],
        ),
        (
            "Y:G@roles_grain",
            map_mod.GrainsMatcher,
            True,
            {
                "query": "roles_grain",
                "options": (),
                "delimiter": ":",
            },
            ["grain_role_a", "grain_role_b"],
        ),
        (
            "Y:G@os",
            map_mod.GrainsMatcher,
            True,
            {
                "query": "os",
                "options": (),
                "delimiter": ":",
            },
            ["Fedora"],
        ),
        (
            "Y:G@selinux:enabled",
            map_mod.GrainsMatcher,
            True,
            {
                "query": "selinux:enabled",
                "options": (),
                "delimiter": ":",
            },
            ["True"],
        ),
        (
            "Y:G::@selinux:enabled",
            map_mod.GrainsMatcher,
            True,
            {
                "query": "selinux:enabled",
                "options": (),
                "delimiter": ":",
            },
            ["True"],
        ),
        (
            "Y:G:!@selinux!enabled",
            map_mod.GrainsMatcher,
            True,
            {
                "query": "selinux!enabled",
                "options": (),
                "delimiter": "!",
            },
            ["True"],
        ),
        (
            "C@nonexistent",
            map_mod.ConfigMatcher,
            False,
            {
                "query": "nonexistent",
                "options": (),
                "delimiter": ":",
            },
            ...,
        ),
        (
            "I@nonexistent",
            map_mod.PillarMatcher,
            False,
            {
                "query": "nonexistent",
                "options": (),
                "delimiter": ":",
            },
            ...,
        ),
        (
            "G@nonexistent",
            map_mod.GrainsMatcher,
            False,
            {
                "query": "nonexistent",
                "options": (),
                "delimiter": ":",
            },
            ...,
        ),
        (
            "Y:G@nonexistent",
            map_mod.GrainsMatcher,
            True,
            {
                "query": "nonexistent",
                "options": (),
                "delimiter": ":",
            },
            ...,
        ),
        (
            "P@defaults.yaml",
            map_mod.StaticMatcher,
            False,
            {
                "query": "defaults.yaml",
                "options": (),
                "delimiter": ":",
            },
            ["defaults.yaml"],
        ),
        (
            "Y:M@variant",
            map_mod.MapdataMatcher,
            True,
            {
                "query": "variant",
                "options": (),
                "delimiter": ":",
            },
            ["foo"],
        ),
        (
            "Y:U@users",
            map_mod.CustomMatcher,
            True,
            {
                "query": "users",
                "options": (),
                "delimiter": ":",
            },
            ["testuser"],
        ),
        (
            "Y:U@users_str",
            map_mod.CustomMatcher,
            True,
            {
                "query": "users_str",
                "options": (),
                "delimiter": ":",
            },
            ["testuser"],
        ),
    ),
)
def test_render_matcher(matcher, cls, exp_yaml, attrs, value):
    render_context = map_mod.RenderContext(
        stack={"variant": "foo"},
        base_dirs=["tplroot/parameters"],
        tpldir="tplroot/foo/bar",
        tplroot="tplroot",
        custom_data={"users": ["testuser"], "users_str": "testuser"},
    )
    res, is_yaml = map_mod._render_matcher(matcher)
    assert res.__class__ is cls
    assert is_yaml is exp_yaml
    for attr, val in attrs.items():
        assert getattr(res, attr) == val
    if exp_yaml:
        assert res.value_list(render_context=render_context).values == value
    else:
        try:
            assert res.value(render_context=render_context).values == value
        except NotImplementedError:
            assert res.value_list(render_context=render_context).values == value


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
    render_context = map_mod.RenderContext(
        stack={},
        base_dirs=["tplroot/parameters"],
        tpldir="tplroot/foo/bar",
        tplroot="tplroot",
    )
    res, is_yaml = map_mod._render_matcher(matcher, for_path_rendering=True)
    assert is_yaml is False
    assert res.__class__ is map_mod.ConfigMatcher
    assert res.query == matcher.split("@")[-1]
    assert res.value_list(render_context=render_context).values == expected


@pytest.mark.parametrize("matcher", ("defaults.yaml", "Y:C@roles_opts"))
def test_render_matcher_for_path_rendering_yaml_disallowed(matcher):
    with pytest.raises(ValueError, match=f".*not allowed in this context.*{matcher}$"):
        map_mod._render_matcher(matcher, for_path_rendering=True)


@pytest.mark.parametrize(
    "chain,typ,matchers",
    (
        (
            "Y!G@os|C@roles_opts",
            map_mod.YAMLRenderer,
            [
                map_mod.GrainsMatcher(query="os", __salt__={"grains.get": grains_mod.get}),
                map_mod.ConfigMatcher(query="roles_opts", __salt__={"config.get": config_mod.get}),
            ],
        ),
        (
            "Y!roles",
            map_mod.YAMLRenderer,
            [map_mod.ConfigMatcher(query="roles", __salt__={"config.get": config_mod.get})],
        ),
    ),
)
def test_render_matcher_chain(chain, typ, matchers):
    render_context = map_mod.RenderContext(
        stack={"variant": "foo"},
        base_dirs=["tplroot/parameters"],
        tpldir="tplroot/foo/bar",
        tplroot="tplroot",
        custom_data={"users": ["testuser"], "users_str": "testuser"},
    )
    renderer = map_mod._render_matcher_chain(chain, render_context)
    assert isinstance(renderer, typ)
    assert len(renderer._matchers) == len(matchers)
    for actual_matcher, expected_matcher in zip(renderer._matchers, matchers):
        assert isinstance(actual_matcher, type(expected_matcher))
        for slot in expected_matcher.__slots__:
            if slot.startswith("_"):
                continue
            assert getattr(actual_matcher, slot) == getattr(expected_matcher, slot)


@pytest.mark.parametrize(
    "chain,for_path_rendering,msg",
    (
        ("variant_defaults.yaml|M@variant", False, "Cannot append other matchers after.*"),
        ("os|variant_defaults.yaml|M@variant", False, "Cannot use YAML matcher in query chains.*"),
        ("Y!G@os|C@roles_opts", True, "Cannot use YAML renderer for path rendering.*"),
    ),
)
def test_render_matcher_chain_disallowed(chain, for_path_rendering, msg):
    render_context = map_mod.RenderContext(
        stack={},
        base_dirs=["tplroot/parameters"],
        tpldir="tplroot/foo/bar",
        tplroot="tplroot",
    )
    with pytest.raises(ValueError, match=msg):
        map_mod._render_matcher_chain(chain, render_context, for_path_rendering=for_path_rendering)


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
        stack.side_effect = (default_formula_config, {})
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
        return default_values or {}

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
        (
            ["G@os_family|I@roles_pillar|P@foo/bar/baz"],
            None,
            None,
            None,
            False,
            True,
            [
                "tplroot/files/os_family/RedHat/roles_pillar/pillar_role_a/foo/bar/baz/foo",
                "tplroot/files/os_family/RedHat/roles_pillar/pillar_role_b/foo/bar/baz/foo",
                "tplroot/files/os_family/RedHat/roles_pillar/pillar_role_a/foo/bar/baz/foo.jinja",
                "tplroot/files/os_family/RedHat/roles_pillar/pillar_role_b/foo/bar/baz/foo.jinja",
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


def test_tofs_subpath_matcher_override():
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
