import contextlib
import json
from unittest.mock import patch

import pytest

from saltext.formula.modules import map as _map_mod


@pytest.fixture(scope="module")
def minion_config_overrides():
    return {
        "tplroot": {
            "data_source": "opts",
            "config_data_source": "opts",
            "opts": True,
        },
        "nested": {
            "query": {
                "nested_data_source": "opts",
                "nested_opts": True,
            }
        },
        "test": {
            "lookup": {
                "lookup_data_source": "opts",
                "lookup_opts": True,
            }
        },
        "grains": {
            "tplroot": {
                "data_source": "grains",
                "config_data_source": "grains",
                "grains": True,
            },
            "nested": {
                "query": {
                    "nested_data_source": "grains",
                    "nested_grains": True,
                }
            },
            "test": {
                "lookup": {
                    "lookup_data_source": "grains",
                    "lookup_grains": True,
                }
            },
        },
        "opts_roles": ["db", "db_master"],
        "boolean": False,
        "integer": 4,
        "boolean_list": [False, True],
        "integer_list": [4, 2],
    }


@pytest.fixture(scope="module", autouse=True)
def pillar(loaders):
    pillar = {
        "roles": ["db", "db_master"],
        "nested": {
            "query": {
                "nested_data_source": "pillar",
                "nested_pillar": True,
            },
            "roles": ["db", "db_master"],
        },
        "test": {
            "lookup": {
                "lookup_data_source": "pillar",
                "lookup_pillar": True,
            }
        },
        "tplroot": {
            "data_source": "pillar",
            "config_data_source": "pillar",
            "pillar": True,
        },
    }
    # We're patching the loaded pillar itself since reloading
    # it in functional tests does not work reliably (and takes more time
    # when it works).
    with patch.dict(loaders.modules.pillar.loader.pack, {"__pillar__": pillar}):
        yield pillar


@pytest.fixture
def param_dir(state_tree):
    return state_tree / "tplroot" / "parameters"


@pytest.fixture
def defaults_yaml(param_dir, request):
    if getattr(request, "param", None) is False:
        ctx = contextlib.nullcontext()
    else:
        contents = {
            "values": {
                "data_source": "defaults_yaml",
                "yaml_data_source": "defaults_yaml",
                "defaults_yaml": True,
            }
        }
        ctx = pytest.helpers.temp_file("defaults.yaml", json.dumps(contents), param_dir)
    with ctx:
        yield


@pytest.fixture
def defaults_yaml_jinja(param_dir):
    contents = {
        "values": {
            "data_source": "defaults_yaml_jinja",
            "yaml_data_source": "defaults_yaml_jinja",
            "defaults_yaml_jinja": True,
        }
    }
    with pytest.helpers.temp_file("defaults.yaml.jinja", json.dumps(contents), param_dir):
        yield


@pytest.fixture
def global_defaults_yaml(state_tree, request):
    if getattr(request, "param", None) is False:
        ctx = contextlib.nullcontext()
    else:
        contents = {
            "values": {
                "data_source": "global_defaults_yaml",
                "yaml_data_source": "global_defaults_yaml",
                "global_defaults_yaml": True,
            }
        }
        ctx = pytest.helpers.temp_file(
            "defaults.yaml", json.dumps(contents), state_tree / "parameters"
        )
    with ctx:
        yield


@pytest.fixture(params=(True,))
def grains_os(param_dir, modules, request):
    if request.param:
        os = modules.grains.get("os")
    else:
        os = "foobar"

    contents = {
        "values": {
            "data_source": "grains_os",
            "yaml_data_source": "grains_os",
            "grains_os": True,
        }
    }
    with pytest.helpers.temp_file(f"{os}.yaml", json.dumps(contents), param_dir / "os"):
        yield request.param


@pytest.fixture(params=(True,))
def pillar_roles(param_dir, request):
    if request.param:
        role = "db"
    else:
        role = "foobar"
    contents = {
        "values": {
            "data_source": "pillar_roles",
            "yaml_data_source": "pillar_roles",
            "pillar_roles": True,
        }
    }
    with pytest.helpers.temp_file(f"{role}.yaml", json.dumps(contents), param_dir / "roles"):
        yield request.param


@pytest.fixture(params=(True,))
def global_pillar_roles(state_tree, request):
    if request.param:
        role = "db"
    else:
        role = "foobar"
    contents = {
        "values": {
            "data_source": "global_pillar_roles",
            "yaml_data_source": "global_pillar_roles",
            "global_pillar_roles": True,
        }
    }
    with pytest.helpers.temp_file(
        f"{role}.yaml", json.dumps(contents), state_tree / "parameters" / "roles"
    ):
        yield request.param


@pytest.fixture(params=(True,))
def opts_roles(param_dir, request):
    if request.param:
        role = "db"
    else:
        role = "foobar"
    contents = {
        "values": {
            "data_source": "opts_roles",
            "yaml_data_source": "opts_roles",
            "opts_roles": True,
        }
    }
    with pytest.helpers.temp_file(f"{role}.yaml", json.dumps(contents), param_dir / "opts_roles"):
        yield request.param


@pytest.fixture(params=(True,))
def pillar_roles_nested(param_dir, request):
    if request.param:
        role = "db"
    else:
        role = "foobar"
    contents = {
        "values": {
            "data_source": "pillar_roles",
            "yaml_data_source": "pillar_roles",
            "pillar_roles": True,
        }
    }
    with pytest.helpers.temp_file(f"{role}.yaml", json.dumps(contents), param_dir / "nested!roles"):
        yield request.param


@pytest.fixture(params=(True,))
def grains_id(param_dir, minion_id, request):
    if request.param:
        mid = minion_id
    else:
        mid = "foobar"
    contents = {
        "values": {
            "data_source": "grains_id",
            "yaml_data_source": "grains_id",
            "grains_id": True,
        }
    }
    with pytest.helpers.temp_file(f"{mid}.yaml", json.dumps(contents), param_dir / "id"):
        yield request.param


@pytest.fixture
def sources(request):
    return getattr(request, "param", None)


@pytest.fixture
def map_jinja_yaml(param_dir, sources):
    config = {}
    if sources is not None:
        config["sources"] = sources
    with pytest.helpers.temp_file("map_jinja.yaml", json.dumps({"values": config}), param_dir):
        yield


@pytest.fixture
def non_string_yaml(param_dir):
    files = []
    for boolean in (False, True):
        for src in ("boolean", "boolean_list"):
            contents = {
                "values": {
                    "data_source": src,
                    "yaml_data_source": src,
                    src: boolean,
                }
            }
            files.append(
                pytest.helpers.temp_file(f"{boolean}.yaml", json.dumps(contents), param_dir / src)
            )
    for integer in (4, 2):
        for src in ("integer", "integer_list"):
            contents = {
                "values": {
                    "data_source": src,
                    "yaml_data_source": src,
                    src: integer,
                }
            }
            files.append(
                pytest.helpers.temp_file(f"{integer}.yaml", json.dumps(contents), param_dir / src)
            )

    with contextlib.ExitStack() as stack:
        for file in files:
            stack.enter_context(file)
        yield


@pytest.fixture
def map_mod(modules):
    return modules.map


@pytest.mark.parametrize(
    "matchers,expected",
    (
        (["C@tplroot"], {"config_data_source": "opts", "data_source": "opts", "opts": True}),
        (["I@tplroot"], {"config_data_source": "pillar", "data_source": "pillar", "pillar": True}),
        (["G@tplroot"], {"config_data_source": "grains", "data_source": "grains", "grains": True}),
        (
            ["C:SUB@tplroot"],
            {"tplroot": {"config_data_source": "opts", "data_source": "opts", "opts": True}},
        ),
        (
            ["I:SUB@tplroot"],
            {"tplroot": {"config_data_source": "pillar", "data_source": "pillar", "pillar": True}},
        ),
        (
            ["G:SUB@tplroot"],
            {"tplroot": {"config_data_source": "grains", "data_source": "grains", "grains": True}},
        ),
        (
            ["C@tplroot", "I@tplroot"],
            {"config_data_source": "pillar", "data_source": "pillar", "pillar": True, "opts": True},
        ),
        (
            ["I@tplroot", "C@tplroot"],
            {"config_data_source": "opts", "data_source": "opts", "pillar": True, "opts": True},
        ),
        (
            ["I:SUB@tplroot", "C@tplroot"],
            {
                "config_data_source": "opts",
                "data_source": "opts",
                "opts": True,
                "tplroot": {
                    "config_data_source": "pillar",
                    "data_source": "pillar",
                    "pillar": True,
                },
            },
        ),
        (
            ["I@tplroot", "C:SUB@tplroot"],
            {
                "config_data_source": "pillar",
                "data_source": "pillar",
                "pillar": True,
                "tplroot": {"config_data_source": "opts", "data_source": "opts", "opts": True},
            },
        ),
        (
            ["G:SUB@tplroot", "I:SUB@tplroot", "C:SUB@tplroot"],
            {
                "tplroot": {
                    "config_data_source": "opts",
                    "data_source": "opts",
                    "grains": True,
                    "pillar": True,
                    "opts": True,
                }
            },
        ),
        (["C@nested:query"], {"nested_data_source": "opts", "nested_opts": True}),
        (["I@nested:query"], {"nested_data_source": "pillar", "nested_pillar": True}),
        (["G@nested:query"], {"nested_data_source": "grains", "nested_grains": True}),
        (
            ["G:SUB@nested:query", "I:SUB@nested:query", "C:SUB@nested:query"],
            {
                "nested:query": {
                    "nested_data_source": "opts",
                    "nested_grains": True,
                    "nested_pillar": True,
                    "nested_opts": True,
                }
            },
        ),
        (
            ["G:SUB:!@nested!query", "I:SUB:!@nested!query", "C:SUB:!@nested!query"],
            {
                "nested!query": {
                    "nested_data_source": "opts",
                    "nested_grains": True,
                    "nested_pillar": True,
                    "nested_opts": True,
                }
            },
        ),
        (["C@test:lookup"], {"lookup_data_source": "opts", "lookup_opts": True}),
        (["I@test:lookup"], {"lookup_data_source": "pillar", "lookup_pillar": True}),
        (["G@test:lookup"], {"lookup_data_source": "grains", "lookup_grains": True}),
        # :lookup was stripped here by the original mapstack. Unsure if sensible.
        (["C:SUB@test:lookup"], {"test": {"lookup_data_source": "opts", "lookup_opts": True}}),
        (["I:SUB@test:lookup"], {"test": {"lookup_data_source": "pillar", "lookup_pillar": True}}),
        (["G:SUB@test:lookup"], {"test": {"lookup_data_source": "grains", "lookup_grains": True}}),
        (["C@nonexistent"], {}),
        (["I@nonexistent"], {}),
        (["G@nonexistent"], {}),
        (
            ["C@nonexistent", "C@tplroot"],
            {"config_data_source": "opts", "data_source": "opts", "opts": True},
        ),
        (
            ["I@nonexistent", "I@tplroot"],
            {"config_data_source": "pillar", "data_source": "pillar", "pillar": True},
        ),
        (
            ["G@nonexistent", "G@tplroot"],
            {"config_data_source": "grains", "data_source": "grains", "grains": True},
        ),
    ),
)
def test_stack_query(matchers, expected, map_mod):
    res = map_mod.stack("tplroot/foo/bar", matchers)
    assert res == {"values": expected}


@pytest.mark.usefixtures(
    "defaults_yaml",
    "defaults_yaml_jinja",
    "pillar_roles",
    "pillar_roles_nested",
    "grains_os",
    "non_string_yaml",
    "opts_roles",
)
@pytest.mark.parametrize(
    "matchers,expected",
    (
        (
            ["defaults.yaml"],
            {
                "data_source": "defaults_yaml_jinja",
                "yaml_data_source": "defaults_yaml_jinja",
                "defaults_yaml": True,
                "defaults_yaml_jinja": True,
            },
        ),
        (
            ["defaults.yaml", "Y:G@kernel", "C@tplroot"],
            {
                "data_source": "opts",
                "yaml_data_source": "defaults_yaml_jinja",
                "defaults_yaml": True,
                "defaults_yaml_jinja": True,
                "opts": True,
                "config_data_source": "opts",
            },
        ),
        (
            ["defaults.yaml.jinja"],
            {
                "data_source": "defaults_yaml_jinja",
                "yaml_data_source": "defaults_yaml_jinja",
                "defaults_yaml_jinja": True,
            },
        ),
        (
            ["roles"],
            {
                "data_source": "pillar_roles",
                "yaml_data_source": "pillar_roles",
                "pillar_roles": True,
            },
        ),
        (
            ["Y:G@os"],
            {"data_source": "grains_os", "yaml_data_source": "grains_os", "grains_os": True},
        ),
        (
            ["Y:C@opts_roles"],
            {"data_source": "opts_roles", "yaml_data_source": "opts_roles", "opts_roles": True},
        ),
        (
            ["Y:I@roles"],
            {
                "data_source": "pillar_roles",
                "yaml_data_source": "pillar_roles",
                "pillar_roles": True,
            },
        ),
        (
            ["Y:I:!@nested!roles"],
            {
                "data_source": "pillar_roles",
                "yaml_data_source": "pillar_roles",
                "pillar_roles": True,
            },
        ),
        (
            ["Y:I:!@roles"],
            {
                "data_source": "pillar_roles",
                "yaml_data_source": "pillar_roles",
                "pillar_roles": True,
            },
        ),
        (
            ["Y:C@boolean"],
            {"data_source": "boolean", "yaml_data_source": "boolean", "boolean": False},
        ),
        (
            ["Y:C@boolean_list"],
            {
                "data_source": "boolean_list",
                "yaml_data_source": "boolean_list",
                "boolean_list": True,
            },
        ),
        (["Y:C@integer"], {"data_source": "integer", "yaml_data_source": "integer", "integer": 4}),
        (
            ["Y:C@integer_list"],
            {"data_source": "integer_list", "yaml_data_source": "integer_list", "integer_list": 2},
        ),
    ),
)
def test_stack_yaml_and_query(matchers, expected, map_mod):
    res = map_mod.stack("tplroot/foo/bar", matchers)
    assert res == {"values": expected}


@pytest.mark.parametrize("config_get_strategy", (None, "merge"))
def test_stack_yaml_config_get_strategy(config_get_strategy, map_mod):
    res = map_mod.stack("tplroot/foo/bar", ["C@tplroot"], config_get_strategy=config_get_strategy)[
        "values"
    ]
    assert res["config_data_source"] == "opts"

    config_sources = (
        ("opts", True),  # C@tplroot only returns opts by default
        ("grains", bool(config_get_strategy)),
        ("pillar", bool(config_get_strategy)),
    )

    for source, expected in config_sources:
        assert (source in res) is expected


@pytest.mark.usefixtures(
    "defaults_yaml", "global_defaults_yaml", "pillar_roles", "global_pillar_roles"
)
@pytest.mark.parametrize(
    "dirs,matchers,defaults_yaml,global_defaults_yaml,pillar_roles,global_pillar_roles,expected",
    (
        (
            ["tplroot/parameters"],
            ["defaults.yaml"],
            True,
            True,
            False,
            False,
            {
                "data_source": "defaults_yaml",
                "yaml_data_source": "defaults_yaml",
                "defaults_yaml": True,
            },
        ),
        (
            ["parameters", "tplroot/parameters"],
            ["defaults.yaml"],
            True,
            True,
            False,
            False,
            {
                "data_source": "defaults_yaml",
                "yaml_data_source": "defaults_yaml",
                "defaults_yaml": True,
                "global_defaults_yaml": True,
            },
        ),
        (
            ["tplroot/parameters", "parameters"],
            ["defaults.yaml"],
            True,
            True,
            False,
            False,
            {
                "data_source": "global_defaults_yaml",
                "yaml_data_source": "global_defaults_yaml",
                "defaults_yaml": True,
                "global_defaults_yaml": True,
            },
        ),
        (
            ["parameters", "tplroot/parameters"],
            ["defaults.yaml", "Y:I@roles"],
            True,
            True,
            True,
            True,
            {
                "data_source": "pillar_roles",
                "yaml_data_source": "pillar_roles",
                "defaults_yaml": True,
                "global_defaults_yaml": True,
                "pillar_roles": True,
                "global_pillar_roles": True,
            },
        ),
        (
            ["tplroot/parameters", "parameters"],
            ["defaults.yaml", "Y:I@roles"],
            True,
            True,
            True,
            True,
            {
                "data_source": "global_pillar_roles",
                "yaml_data_source": "global_pillar_roles",
                "defaults_yaml": True,
                "global_defaults_yaml": True,
                "pillar_roles": True,
                "global_pillar_roles": True,
            },
        ),
        (
            ["parameters", "tplroot/parameters"],
            ["defaults.yaml", "Y:I@roles"],
            True,
            False,
            False,
            True,
            {
                "data_source": "global_pillar_roles",
                "yaml_data_source": "global_pillar_roles",
                "defaults_yaml": True,
                "global_pillar_roles": True,
            },
        ),
    ),
    indirect=("defaults_yaml", "global_defaults_yaml", "pillar_roles", "global_pillar_roles"),
)
def test_stack_yaml_multiple_parameter_dirs(map_mod, dirs, matchers, expected):
    res = map_mod.stack("tplroot/foo/bar", matchers, parameter_dirs=dirs)
    assert res["values"] == expected


def test_stack_yaml_jinja_context(map_mod, param_dir):
    tpldir = "tplroot/foo/bar"
    contents_defaults = {"tpldir": "{{ tpldir }}", "tplroot": "{{ tplroot }}", "setting": "foo"}
    contents_roles = {"mapdata_available": "{{ mapdata.get('setting') == 'foo'}}"}
    with pytest.helpers.temp_file(
        "defaults.yaml.jinja", json.dumps({"values": contents_defaults}), param_dir
    ):
        with pytest.helpers.temp_file(
            "db.yaml.jinja", json.dumps({"values": contents_roles}), param_dir / "roles"
        ):
            res = map_mod.stack(tpldir, ["defaults.yaml", "Y:I@roles"])
    assert res["values"] == {
        "tpldir": tpldir,
        "tplroot": tpldir.split("/", maxsplit=1)[0],
        "setting": "foo",
        "mapdata_available": "True",
    }


@pytest.mark.parametrize("merge_strategy", ("smart", "overwrite"))
@pytest.mark.parametrize("default_merge_strategy", (None, "smart", "overwrite"))
def test_stack_yaml_meta_strategy(map_mod, param_dir, merge_strategy, default_merge_strategy):
    contents_defaults = {
        "nested": {
            "value": True,
            "default": True,
        },
    }
    contents_roles = {
        "nested": {
            "value": False,
        }
    }
    with pytest.helpers.temp_file(
        "defaults.yaml.jinja", json.dumps({"values": contents_defaults}), param_dir
    ):
        with pytest.helpers.temp_file(
            "db.yaml.jinja",
            json.dumps({"strategy": merge_strategy, "values": contents_roles}),
            param_dir / "roles",
        ):
            res = map_mod.stack(
                "tplroot/foo/bar",
                ["defaults.yaml", "Y:I@roles"],
                default_merge_strategy=default_merge_strategy,
            )
    if merge_strategy == "overwrite":
        assert res["values"] == {"nested": {"value": False}}
    else:
        assert res["values"] == {"nested": {"value": False, "default": True}}


@pytest.mark.parametrize("merge_lists", (False, True))
@pytest.mark.parametrize("default_merge_lists", (None, False, True))
def test_stack_yaml_meta_merge_lists(map_mod, param_dir, merge_lists, default_merge_lists):
    contents_defaults = {
        "list": ["foo", "bar"],
    }
    contents_roles = {
        "list": ["baz"],
    }
    with pytest.helpers.temp_file(
        "defaults.yaml.jinja", json.dumps({"values": contents_defaults}), param_dir
    ):
        with pytest.helpers.temp_file(
            "db.yaml.jinja",
            json.dumps({"merge_lists": merge_lists, "values": contents_roles}),
            param_dir / "roles",
        ):
            res = map_mod.stack(
                "tplroot/foo/bar",
                ["defaults.yaml", "Y:I@roles"],
                default_merge_lists=default_merge_lists,
            )
    if merge_lists:
        assert res["values"] == {"list": ["foo", "bar", "baz"]}
    else:
        assert res["values"] == {"list": ["baz"]}


@pytest.mark.usefixtures("defaults_yaml", "pillar_roles")
@pytest.mark.parametrize("grains_os", (False, True), indirect=True)
@pytest.mark.parametrize("pillar_roles", (False, True), indirect=True)
@pytest.mark.parametrize("grains_id", (False, True), indirect=True)
@pytest.mark.parametrize("config_get_strategy", (None, "merge"))
def test_data_defaults(grains_os, grains_id, config_get_strategy, map_mod):
    res = map_mod.data("tplroot/foo/bar", config_get_strategy=config_get_strategy)
    yaml_sources = (
        ("defaults_yaml", True),
        ("grains_os", grains_os),
        ("pillar_roles", False),
        ("grains_id", grains_id),
    )
    config_sources = (
        ("opts", True),  # C@tplroot only returns opts by default
        ("grains", bool(config_get_strategy)),
        ("pillar", bool(config_get_strategy)),
    )

    for source, expected in yaml_sources:
        assert (source in res) is expected
    for source, expected in reversed(yaml_sources):
        if not expected:
            continue
        assert res["yaml_data_source"] == source
        break
    for source, expected in config_sources:
        assert (source in res) is expected
    assert res["config_data_source"] == "opts"
    assert res["map_jinja"] == {
        "cache": True,
        "config_get_strategy": config_get_strategy,
        "default_merge_lists": False,
        "default_merge_strategy": None,
        "parameter_dirs": [
            "tplroot/parameters",
        ],
        "post_map": "post-map.jinja",
        "post_map_template": "jinja",
        "sources": [
            "defaults.yaml",
            "Y:G@osarch",
            "Y:G@os_family",
            "Y:G@os",
            "Y:G@osfinger",
            "C@tplroot",
            "Y:G@id",
        ],
    }


@pytest.mark.usefixtures("defaults_yaml")
def test_data_post_map(map_mod, state_tree):
    contents = """\
        {% do mapdata.update({"data_source": "post_map", "foo": "bar"}) %}
        """
    with pytest.helpers.temp_file("post-map.jinja", contents, state_tree / "tplroot"):
        res = map_mod.data("tplroot/foo/bar")
    for param, val in (
        ("data_source", "post_map"),
        ("defaults_yaml", True),
        ("foo", "bar"),
    ):
        assert param in res
        assert res[param] == val


@pytest.mark.usefixtures("defaults_yaml")
def test_data_post_map_template(map_mod, state_tree):
    contents = """\
        def run():
            mapdata.update({"data_source": "post_map", "foo": "bar"})
        """
    with pytest.helpers.temp_file("post-map.py", contents, state_tree / "tplroot"):
        res = map_mod.data("tplroot/foo/bar", post_map="post-map.py", post_map_template="py")
    for param, val in (
        ("data_source", "post_map"),
        ("defaults_yaml", True),
        ("foo", "bar"),
    ):
        assert param in res
        assert res[param] == val


@pytest.mark.usefixtures("defaults_yaml")
@pytest.mark.parametrize("cache", (False, True))
def test_data_cache(map_mod, cache):
    res = map_mod.data("tplroot/foo/bar", cache=cache)
    res2 = map_mod.data("tplroot/foo/bar", cache=cache)
    assert (res2 is res) is cache
    sources = [matcher.format(tplroot="tplroot") for matcher in _map_mod.DEFAULT_MATCHERS]
    res3 = map_mod.data("tplroot/foo/bar", sources=sources, cache=cache)
    assert (res3 is res) is cache
    parameter_dirs = [
        pdir.format(tplroot="tplroot") for pdir in _map_mod.DEFAULT_PARAM_DIRS_MAPDATA
    ]
    res4 = map_mod.data("tplroot/foo/bar", parameter_dirs=parameter_dirs, cache=cache)
    assert (res4 is res) is cache
    res5 = map_mod.data(
        "tplroot/foo/bar",
        sources=sources,
        parameter_dirs=parameter_dirs,
        cache=cache,
    )
    assert (res5 is res) is cache
    res6 = map_mod.data("tplroot/foo/bar", sources=["defaults.yaml"], cache=cache)
    assert res6 is not res
    res7 = map_mod.data("tplroot/foo/bar", parameter_dirs=["foobar/parameters"], cache=cache)
    assert res7 is not res
    res8 = map_mod.data(
        "tplroot/foo/bar",
        sources=["defaults.yaml"],
        parameter_dirs=["foobar/parameters"],
        cache=cache,
    )
    assert res8 is not res
    assert res8 is not res6
    assert res8 is not res7
    res9 = map_mod.data("tplroot/foo/bar", cache=cache)
    assert (res9 is res) is cache
