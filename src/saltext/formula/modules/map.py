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

# Use an object instance to track whether a query was successful or not
UNSET = frozenset()

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
        Earlier entries have a **lower** priority (later ones are merged on top).

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
            # We don't care about its output, so we don't need to ensure
            # the path is converted in Salt-SSH either by calling _get_template.
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
        if matcher["value"] is UNSET:
            continue
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
                yaml_dirname, yaml_names = str(file_path.parent), [file_path.name]

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
                    yaml_cached = _get_template(
                        yaml_path,
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


def tofs(
    tpldir,
    source_files,
    lookup=None,
    default_matchers=None,
    use_subpath=False,
    include_query=True,
    path_prefix=None,
    files_dir="files",
    default_dir="default",
    config=None,
):
    """
    Render a list of TOFS patterns to be used as an input to states that
    allow to specify multiple ``sources``, such as ``file.managed``.

    .. note::

        This function is intended to be called from templates during the rendering
        of states, but it can be used for debugging/information purposes as well.

    CLI Example:

    .. code-block:: bash

        salt '*' map.tofs openssh '[salt.conf, salt.conf.jinja]'
        salt '*' map.tofs openssh '[etc/salt/master, etc/salt/master.j2]'

    tpldir
        Pass ``tpldir`` from the state file.

    source_files
        A list of relative paths to render relative to all TOFS sources.
        Earlier entries have a **higher** priority (they are searched first).
        Required.

    lookup
        Allow users to specify alternate file names in the formula configuration
        that are prepended to the default ``source_files`` (in ``tofs:source_files:<lookup>``).

    default_matchers
        A list of data source (matcher) definitions. Can be overridden
        in ``tofs:files_switch``, which itself can also be overridden
        per subpath (eg ``sub/path``), including the root one,
        in ``<sub>:<path>:files_switch``.

    use_subpath
        When called from a state inside a nested directory, e.g. ``salt://salt/minion/config/init.sls``,
        also try ``files_dir`` relative to each parent
        (``salt/minion/config/files``,  ``salt/minion/files``, ``salt/files``).
        Defaults to false.

    include_query
        Include the matcher query in the path. Defaults to true.
        When true:  ``G@os`` -> ``files/os/Fedora/salt.conf``
        When false: ``G@os`` -> ``files/Fedora/salt.conf``

    path_prefix
        The path prefix containing the ``files_dir``. Defaults to the first
        part of ``tpldir``.

    files_dir
        The directory relative to ``path_prefix`` containing possible files.
        Defaults to ``files``.

    default_dir
        The name of the directory that is used as a fallback. Defaults to ``default``.

    config
        If you have rendered the formula configuration, you can pass it here.
        If not passed, calls :py:func:`map.data <saltext.formula.modules.map.data`
        to fetch it.
    """
    tplroot = tpldir.split("/", maxsplit=1)[0]
    if config is None:
        config = data(tpldir)
    if default_matchers is None:
        default_matchers = ("id", "os_family")
    if path_prefix is None:
        path_prefix = tplroot

    subpaths = []

    # In case this was called from within a nested dir, search all parent directories
    # for the `files_dir`.
    if use_subpath and tplroot != tpldir:
        for par in (Path(tpldir), *Path(tpldir).parents):
            parent = "/".join(par.parts[1:])
            if parent:
                subpaths.append(f"/{parent}")
    subpaths.append("")

    default_config = {
        "files_switch": default_matchers,
        "path_prefix": path_prefix,
        "dirs": {
            "default": default_dir,
            "files": files_dir,
        },
        "source_files": {},
        "include_query": include_query,
    }
    tofs_config = ChainMap(config.get("tofs", {}), default_config)

    if lookup is not None:
        source_files = traverse(tofs_config, f"source_files:{lookup}", []) + source_files

    base_prefix = tofs_config["path_prefix"]
    files_dir = traverse(tofs_config, "dirs:files", files_dir)
    default_matchers = tofs_config["files_switch"]
    include_query = tofs_config["include_query"]

    res = []
    for subpath in subpaths:
        override_path = "/".join(part for part in (subpath.strip("/"), "files_switch") if part)
        matchers = traverse(config, override_path, list(default_matchers), delimiter="/")
        if "" not in matchers:
            matchers.append("")

        for matcher in matchers:
            if matcher:
                matcher_res = _render_matcher(
                    matcher,
                    config_get_strategy=config["map_jinja"]["config_get_strategy"],
                    for_path_rendering=True,
                )
                matched_values = matcher_res["value"]
                query = matcher_res["query"]
                if matched_values is UNSET:
                    matched_values = [matcher_res["query"]]
                    query = ""
            else:
                matched_values = [str(traverse(tofs_config, "dirs:default", default_dir))]
                query = ""

            for src_file in source_files:
                for matched_value in matched_values:
                    url = "/".join(
                        part.strip("/")
                        for part in (
                            base_prefix,
                            subpath,
                            files_dir,
                            query if include_query else "",
                            matched_value,
                            src_file,
                        )
                        if part.strip("/")
                    )
                    res.append(f"salt://{url}")
    return res


def _render_matchers(matchers, *, config_get_strategy=None, for_path_rendering=False):
    """
    Normalize a list of matcher definitions and query their values.

    matchers
        A list of matcher definitions.

    config_get_strategy
        When a ``config.get`` matcher (type ``C``) is specified,
        override the default merge strategy.

    for_path_rendering
        Ensure returned query results can be used as path segments.
        This means the YAML matcher (``Y``) is disabled and query
        results are cast to a list of strings.
        Defaults to false.
    """
    parsed_matchers = []
    for matcher in matchers:
        parsed_matchers.append(
            _render_matcher(
                matcher,
                config_get_strategy=config_get_strategy,
                for_path_rendering=for_path_rendering,
            )
        )

    return parsed_matchers


def _render_matcher(matcher, *, config_get_strategy=None, for_path_rendering=False):
    """
    Normalize a matcher definition and execute the query.

    matcher
        A matcher definition.

    config_get_strategy
        When a ``config.get`` matcher (type ``C``) is specified,
        override the default merge strategy.

    for_path_rendering
        Ensure returned query results can be used as path segments.
        This means the YAML matcher (``Y``) is disabled and query
        results are cast to a list of strings.
        Defaults to false.
    """
    query, *key = matcher.split("@")
    if key:
        typ, option, delimiter, *rest = chain(query.split(":"), [None] * 2)
        if rest and rest[0] == "":
            # colon as delimiter was explicitly specified via Y:C::@roles
            delimiter = ":"
        if typ == "Y" and for_path_rendering:
            raise ValueError(f"YAML type is not allowed in this context. Got: {matcher}")
        parsed = {
            "type": typ,
            "option": option or ("C" if typ == "Y" else None),
            "query_delimiter": delimiter or ":",
            "query": key[0],
        }
    elif query.endswith((".yaml", ".jinja")):
        if for_path_rendering:
            raise ValueError(f"YAML type is not allowed in this context. Got: {matcher}")
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
            "type": "Y" if not for_path_rendering else "C",
            "option": "C" if not for_path_rendering else None,
            "query_delimiter": ":",
            "query": query,
        }

    if "query_method" not in parsed:
        parsed["query_method"] = QUERY_MAP.get(parsed["type"]) or QUERY_MAP[parsed["option"]]
    query_opts = {"delimiter": parsed["query_delimiter"]}
    if parsed["query_method"] == "config.get" and config_get_strategy:
        query_opts["merge"] = config_get_strategy
    if "value" not in parsed:
        query_result = __salt__[parsed["query_method"]](
            parsed["query"], default=UNSET, **query_opts
        )
        if query_result is not UNSET and (parsed["type"] == "Y" or for_path_rendering):
            # Ensure we always return a list of string values when rendering paths
            if isinstance(query_result, str):
                query_result = [query_result]
            else:
                try:
                    query_result = [str(name) for name in query_result]
                except TypeError:
                    query_result = [str(query_result)]
        parsed["value"] = query_result

    return parsed


def _get_template(path, **kwargs):
    return __salt__["cp.get_template"](
        f"salt://{path}",
        "",
        **kwargs,
    )
