"""
Provide helpers to render layered formula configuration.

This is heavily based on the excellent work done in the `template-formula <https://github.com/saltstack-formulas/template-formula>`_.
"""

import logging
from collections import ChainMap
from itertools import chain
from pathlib import Path

import salt.loader
import salt.utils.yaml
from salt.utils.data import traverse_dict_and_list as traverse
from salt.utils.dictupdate import merge
from salt.utils.immutabletypes import freeze

DEFAULT_MATCHERS = (
    "Y:G@osarch",
    "Y:G@os_family",
    "Y:G@os",
    "Y:G@osfinger",
    "C@{tplroot}",
    "Y:G@id",
)

DEFAULT_PARAM_DIRS_MAPDATA = ("{tplroot}/parameters",)

DEFAULT_PARAM_DIRS_MAPSTACK = (
    "parameters",
    "{tplroot}/parameters",
)

MATCHER_DEFAULTS = freeze(
    {
        "type": "Y",
        "query_type": "C",
        "query_delimiter": ":",
    }
)

QUERY_MAP = freeze(
    {
        "C": "config.get",
        "G": "grains.get",
        "I": "pillar.get",
    }
)

CKEY = "_formula_mapdata"

log = logging.getLogger(__name__)

__virtualname__ = "map"


def __virtual__():
    return __virtualname__


def data(
    tpldir,
    sources=None,
    parameter_dirs=None,
    config_get_strategy=None,
    default_merge_strategy=None,
    default_merge_lists=False,
    post_map="post-map.jinja",
    post_map_template="jinja",
    cache=True,
):
    """
    Render formula configuration.

    .. note::

        This function is intended to be called from templates during the rendering
        of states, but it can be used for debugging/information purposes as well.

    CLI Example:

    .. code-block:: bash

        salt '*' map.data openssh

    tpldir
        Pass ``tpldir`` from the state file. Used to derive the
        ``tplroot``, which is currently always the first part of the path.

    sources
        A list of default :ref:`data source definitions <matcher-def-target>`.
        Can be overridden globally or per-formula.

        Defaults to:

        .. code-block:: yaml

            - defaults.yaml
            - Y:G@osarch
            - Y:G@os_family
            - Y:G@os
            - Y:G@osfinger
            - C@{tplroot}
            - Y:G@id

        .. important::
            ``defaults.yaml`` is always prepended to the list, you don't need to include it.

    parameter_dirs
        A list of default parameter directories to look up YAML parameter files in.
        Can be overridden globally or per-formula.

        Defaults to ``[{tplroot}/parameters]``, where ``tplroot`` is the
        first part of ``tpldir``.

    config_get_strategy
        A ``merge`` strategy used in calls to :py:func:`config.get <salt.modules.config.get>`.
        Can be overridden globally or per-formula.
        Defaults to None.

    default_merge_strategy
        A default merge strategy for this formula.
        See :py:func:`slsutil.merge <salt.modules.slsutil.merge>` for available ones.
        Can be overridden globally or per-formula.
        Defaults to `smart`.

    default_merge_lists
        Whether to merge lists by default in this formula.
        Can be overridden globally or per-formula.
        Defaults to false.

    post_map
        Allow a template with this path relative to the formula root directory
        to modify the final result before returning.
        See :ref:`post-map.jinja <post-map-jinja-target>` for details.
        Can be overridden globally or per-formula.
        Defaults to ``post-map.jinja``. ``False`` disables this behavior.

    post_map_template
        The renderer required for the template specified in ``post_map``.
        Can be overridden globally or per-formula.
        Defaults to ``jinja``.

    cache
        Whether to cache the result for subsequent calls with the same arguments.
        Can be overridden globally or per-formula.
        Enabled by default.
    """
    # Effectively, this function is a wrapper around stack that handles
    #   - retrieving stack configuration (matchers, defaults when merging)
    #   - providing sane defaults for formula configuration
    #   - caching of results when rendering multiple templates
    tplroot = tpldir.split("/")[0]
    if sources is None:
        sources = [src.format(tplroot=tplroot) for src in DEFAULT_MATCHERS]
    if parameter_dirs is None:
        parameter_dirs = [pdir.format(tplroot=tplroot) for pdir in DEFAULT_PARAM_DIRS_MAPDATA]
    sources = tuple(sources)
    parameter_dirs = tuple(parameter_dirs)
    res_ckey = (
        tplroot,
        sources,
        parameter_dirs,
        config_get_strategy,
        default_merge_strategy,
        default_merge_lists,
        post_map,
    )

    if cache and CKEY not in __context__:
        __context__[CKEY] = {}

    if not cache or res_ckey not in __context__[CKEY]:
        default_formula_config = {
            "sources": list(sources),
            "parameter_dirs": list(parameter_dirs),
            # The following 3 were queried via salt["config.get"](f"{tplroot}:(strategy|merge_lists)")
            # in libmapstack.jinja. The merge strategy was used in both
            # config.get and slsutil.merge.
            "config_get_strategy": config_get_strategy,
            "default_merge_strategy": default_merge_strategy,
            "default_merge_lists": default_merge_lists,
            "post_map": post_map,
            "post_map_template": post_map_template,
            "cache": cache,
        }
        # Discover mapstack configuration for this formula.
        # Searches for salt://parameters/map_jinja.yaml[.jinja] and
        # salt://{tplroot}/parameters/map_jinja.yaml[.jinja]
        map_config = stack(
            tplroot,
            sources=["map_jinja.yaml"],
            default_values=default_formula_config,
            config_get_strategy=config_get_strategy,
        )["values"]

        if "defaults.yaml" not in map_config["sources"]:
            map_config["sources"].insert(0, "defaults.yaml")

        # Generate formula configuration based on the config above.
        formula_config = stack(
            tplroot,
            sources=map_config["sources"],
            parameter_dirs=map_config["parameter_dirs"],
            default_merge_strategy=map_config["default_merge_strategy"],
            default_merge_lists=map_config["default_merge_lists"],
            config_get_strategy=map_config["config_get_strategy"],
        )["values"]

        # Ensure mapdata allows to track the map_jinja configuration
        formula_config["map_jinja"] = map_config
        if map_config["post_map"] is not False:
            # Just rendering the template propagates its changes to mapdata.
            # We don't care about its output.
            __salt__["cp.get_template"](
                f"salt://{tplroot}/{map_config['post_map']}",
                "",
                template=map_config["post_map_template"],
                tpldir=tpldir,
                tplroot=tplroot,
                mapdata=formula_config,
            )
        if not map_config["cache"]:
            return formula_config
        # Cache the result to speed up state runs where more than one ``.sls`` file is rendered
        __context__[CKEY][res_ckey] = formula_config

    return __context__[CKEY][res_ckey]


def stack(
    tpldir,
    sources,
    parameter_dirs=None,
    default_values=None,
    default_merge_strategy=None,
    default_merge_lists=None,
    config_get_strategy=None,
):
    """
    Takes a list of matcher definitions and renders the resulting layered
    configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' map.stack openssh '[defaults.yaml, Y@G:os]'

    tpldir
        Pass ``tpldir`` from the state file.

    sources
        A list of data source (matcher) definitions.

    parameter_dirs
        A list of parameter directories to look up YAML files in.
        Defaults to ``[{tplroot}/parameters, parameters]``, where ``tplroot``
        is the first part of ``tpldir``.

    default_values
        Provide default values.

    default_merge_strategy
        Provide a default value for ``merge_strategy`` when merging results into the stack.

    default_merge_lists
        Provide a default value for merge_lists when merging results into the stack.

    config_get_strategy
        A ``merge`` strategy used in calls to :py:func:`config.get <salt.modules.config.get>`.
        Defaults to None.
    """
    tplroot = tpldir.split("/")[0]
    if parameter_dirs is None:
        parameter_dirs = [pdir.format(tplroot=tplroot) for pdir in DEFAULT_PARAM_DIRS_MAPSTACK]
    res = {"values": default_values or {}}
    if default_merge_strategy is not None:
        res["merge_strategy"] = default_merge_strategy
    if default_merge_lists is not None:
        res["merge_lists"] = default_merge_lists

    matchers = _render_matchers(sources, config_get_strategy=config_get_strategy)

    for matcher in matchers:
        if matcher["type"] in QUERY_MAP:
            stack_config = ChainMap(matcher["value"], res)
            strategy = traverse(stack_config, "strategy", default="smart")
            merge_lists = traverse(stack_config, "merge_lists", default=False)
            value = matcher["value"] or {}
            if matcher["option"] == "SUB":
                # Cut :lookup if we're subkeying the result.
                # I'm unsure if this should be kept, need to look into the reasoning
                # why it was done that way in the original mapstack implementation.
                value = {
                    (
                        matcher["query"]
                        if not matcher["query"].endswith(":lookup")
                        else matcher["query"][:-7]
                    ): value
                }
            res["values"] = merge(res["values"], value, strategy=strategy, merge_lists=merge_lists)
        else:
            # YAML via Y@
            yaml_dirname = matcher["query"]
            yaml_names = matcher["value"]
            if matcher["value"] is ...:
                # A static filename was specified.
                file_path = Path(matcher["query"])
                yaml_dirname, yaml_names = str(file_path.parent), file_path.name
            if isinstance(yaml_names, str):
                yaml_names = [yaml_names]
            else:
                try:
                    yaml_names = [str(name) for name in yaml_names]
                except TypeError:
                    yaml_names = [str(yaml_names)]
            all_yaml_names = []
            for name in yaml_names:
                file_ext = Path(name).suffix
                if file_ext not in (".yaml", ".jinja"):
                    all_yaml_names.extend((f"{name}.yaml", f"{name}.yaml.jinja"))
                elif file_ext == ".yaml":
                    all_yaml_names.extend((name, f"{name}.jinja"))
                else:
                    all_yaml_names.append(name)
            for param_dir in parameter_dirs:
                for yaml_name in all_yaml_names:
                    yaml_path = Path(param_dir, yaml_dirname, yaml_name)
                    yaml_cached = __salt__["cp.get_template"](
                        f"salt://{yaml_path}",
                        "",
                        tpldir=tpldir,
                        tplroot=tplroot,
                        mapdata=res["values"],
                    )
                    if not yaml_cached:
                        continue
                    with salt.utils.files.fopen(yaml_cached, "r") as ptr:
                        yaml_values = salt.utils.yaml.safe_load(ptr)
                    stack_config = ChainMap(yaml_values, res)
                    strategy = traverse(stack_config, "strategy", default="smart")
                    merge_lists = traverse(stack_config, "merge_lists", default=False)
                    res["values"] = merge(
                        res["values"],
                        traverse(yaml_values, "values", default={}),
                        strategy=strategy,
                        merge_lists=merge_lists,
                    )

    return res


def _render_matchers(matchers, config_get_strategy=None):
    """
    Normalize a list of matcher definitions and query their values.

    matchers
        A list of matcher definitions.

    config_get_strategy
        When a ``config.get`` matcher (type ``C``) is specified,
        override the default merge strategy.
    """
    parsed_matchers = []
    for matcher in matchers:
        parsed_matchers.append(_render_matcher(matcher, config_get_strategy=config_get_strategy))

    return parsed_matchers


def _render_matcher(matcher, config_get_strategy=None):
    """
    Normalize a matcher definition and execute the query.

    matcher
        A matcher definition.

    config_get_strategy
        When a ``config.get`` matcher (type ``C``) is specified,
        override the default merge strategy.
    """
    query, *key = matcher.split("@")
    if key:
        typ, option, delimiter, *rest = chain(query.split(":"), [None] * 2)
        if rest and rest[0] == "":
            # colon as delimiter was explicitly specified via Y:C::@roles
            delimiter = ":"
        parsed = {
            "type": typ,
            "option": option or ("C" if typ == "Y" else None),
            "query_delimiter": delimiter or ":",
            "query": key[0],
        }
    elif query.endswith((".yaml", ".jinja")):
        # Static file path like defaults.yaml
        parsed = {
            "type": "Y",
            "option": None,
            "query_delimiter": None,
            "query_method": None,
            "query": query,
            "value": ...,
        }
    else:
        # Configuration without @, example: mysql.
        # Interpret it as a YAML source with config.get query.
        parsed = {
            "type": "Y",
            "option": "C",
            "query_delimiter": ":",
            "query": query,
        }

    if "query_method" not in parsed:
        parsed["query_method"] = QUERY_MAP.get(parsed["type"]) or QUERY_MAP[parsed["option"]]
    query_opts = {"delimiter": parsed["query_delimiter"]}
    if parsed["query_method"] == "config.get" and config_get_strategy:
        query_opts["merge"] = config_get_strategy
    if "value" not in parsed:
        parsed["value"] = __salt__[parsed["query_method"]](
            parsed["query"], default=[], **query_opts
        )

    return parsed
