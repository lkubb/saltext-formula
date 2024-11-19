"""
Provide helpers to render layered formula configuration.

This is heavily based on the excellent work done in the `template-formula <https://github.com/saltstack-formulas/template-formula>`_.
"""

import itertools
import logging
import pickle
from collections import ChainMap
from collections.abc import Iterable
from collections.abc import Sequence
from itertools import chain
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Optional
from typing import Union

import salt.loader
import salt.utils.yaml
from salt.utils.data import traverse_dict_and_list as traverse
from salt.utils.dictupdate import merge
from salt.utils.immutabletypes import freeze

try:
    from types import EllipsisType
except ImportError:
    # Python <3.10
    EllipsisType = type(Ellipsis)  # type: ignore


DEFAULT_MATCHERS = (
    "Y!G@osarch",
    "Y!G@os_family",
    "Y!G@os",
    "Y!G@osfinger",
    "C@{tplroot}",
    "Y!G@id",
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
    custom_data=None,
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

            - Y!P@defaults.yaml
            - Y!G@osarch
            - Y!G@os_family
            - Y!G@os
            - Y!G@osfinger
            - C@{tplroot}
            - Y!G@id

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

    custom_data
        .. versionadded:: 0.3.0

        A custom dictionary that can provide values for the ``U`` matcher.
        Must be picklable.
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
        pickle.dumps(custom_data),
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
        )

        if not any(
            defaults_repr in map_config["sources"]
            for defaults_repr in ("defaults.yaml", "Y!defaults.yaml", "Y!P@defaults.yaml")
        ):
            map_config["sources"].insert(0, "Y!P@defaults.yaml")

        # Generate formula configuration based on the config above.
        formula_config = stack(
            tplroot,
            sources=map_config["sources"],
            parameter_dirs=map_config["parameter_dirs"],
            default_merge_strategy=map_config["default_merge_strategy"],
            default_merge_lists=map_config["default_merge_lists"],
            config_get_strategy=map_config["config_get_strategy"],
        )

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
    custom_data=None,
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

    custom_data
        .. versionadded:: 0.3.0

        A custom dictionary that can provide values for the ``U`` matcher.
    """
    tplroot = tpldir.split("/")[0]
    if parameter_dirs is None:
        parameter_dirs = [pdir.format(tplroot=tplroot) for pdir in DEFAULT_PARAM_DIRS_MAPSTACK]

    render_context = RenderContext(
        stack=default_values or {},
        tplroot=tplroot,
        tpldir=tpldir,
        base_dirs=parameter_dirs,
        custom_data=custom_data,
        config_get_strategy=config_get_strategy,
        merge_strategy=default_merge_strategy,
        merge_lists=default_merge_lists,
    )
    for matcher_chain in sources:
        renderer = _render_matcher_chain(matcher_chain, render_context)
        renderer.render()
    return render_context.stack


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
    custom_data=None,
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

    custom_data
        .. versionadded:: 0.3.0

        A custom dictionary that can provide values for the ``U`` matcher.
    """
    tplroot = tpldir.split("/", maxsplit=1)[0]
    if config is None:
        config = data(tpldir)
    if default_matchers is None:
        default_matchers = ("G@id", "G@os_family")
    if path_prefix is None:
        path_prefix = tplroot

    subpaths = []

    # In case this was called from within a nested dir, search all parent directories
    # for the `files_dir`.
    if use_subpath and tplroot != tpldir:
        for par in (Path(tpldir), *Path(tpldir).parents):
            parent = _concat_parts(par.parts[1:])
            if parent:
                subpaths.append(parent)
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
    render_context = RenderContext(
        stack=config,
        tplroot=tplroot,
        tpldir=tpldir,
        base_dirs=[],
        custom_data=custom_data,
        config_get_strategy=config["map_jinja"]["config_get_strategy"],
    )

    for subpath in subpaths:
        override_path = _concat_parts(subpath, "files_switch")
        matchers = traverse(config, override_path, list(default_matchers), delimiter="/")
        if "" not in matchers:
            matchers.append("")
        default_dir = str(traverse(tofs_config, "dirs:default", default_dir))
        matchers = [matcher if matcher else f"P@{default_dir}" for matcher in matchers]

        for matcher_chain in matchers:
            renderer = _render_matcher_chain(matcher_chain, render_context, for_path_rendering=True)
            results = renderer.render_path(
                include_query=include_query,
                base_dirs=[_concat_parts(base_prefix, subpath, files_dir)],
                fallback_to_query=True,
            )
            for src_file in source_files:
                for result in results:
                    res.append(f"salt://{_concat_parts(result, src_file)}")

    return res


class SlotsReprTrait:
    __slots__: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {repr({slot: getattr(self, slot) for slot in self.__slots__})}"


class MatcherListResult(SlotsReprTrait):
    __slots__ = ("query", "values")

    query: str
    values: Union[list[str], EllipsisType]

    def __init__(
        self,
        query: str,
        values: Any = ...,
    ):
        self.query = query
        if values is ...:
            pass
        # Ensure we always return a list of string values when rendering paths
        elif isinstance(values, str):
            values = [values]
        else:
            try:
                values = [str(name) for name in values]
            except TypeError:
                values = [str(values)]
        self.values = values

    def __bool__(self) -> bool:
        return self.values is not ...


class MatcherResult(SlotsReprTrait):
    __slots__ = ("query", "values", "merge_strategy", "merge_lists")

    query: str
    values: Union[dict[Any, Any], EllipsisType]
    merge_strategy: Optional[str]
    merge_lists: Optional[bool]

    def __init__(
        self,
        query: str,
        values: Union[dict[Any, Any], EllipsisType] = ...,
        strategy: Optional[str] = None,
        merge_lists: Optional[bool] = None,
    ):
        self.query = query
        self.values = values
        self.merge_strategy = strategy
        self.merge_lists = merge_lists

    def __bool__(self) -> bool:
        return self.values is not ...

    @classmethod
    def from_bare(cls, query, bare):
        try:
            merge_strategy = bare.pop("strategy", None)
            merge_lists = bare.pop("merge_lists", None)
        except (AttributeError, TypeError):
            merge_strategy = merge_lists = None
        return cls(query=query, values=bare, strategy=merge_strategy, merge_lists=merge_lists)


class RenderContext(SlotsReprTrait):
    __slots__ = (
        "stack",
        "base_dirs",
        "custom_data",
        "tpldir",
        "tplroot",
        "config_get_strategy",
        "merge_strategy",
        "merge_lists",
    )

    stack: dict
    base_dirs: tuple[str, ...]
    custom_data: dict[str, Union[list[str], dict]]
    tpldir: str
    tplroot: str
    config_get_strategy: Optional[str]
    merge_strategy: str
    merge_lists: bool

    def __init__(
        self,
        stack: dict,  # pylint: disable = redefined-outer-name
        base_dirs: tuple[str, ...],
        tpldir: str,
        tplroot: str,
        custom_data: Optional[dict[str, Union[list[str], dict]]] = None,
        config_get_strategy: Optional[str] = None,
        merge_strategy: Optional[str] = "smart",
        merge_lists: Optional[bool] = False,
    ):
        self.stack = stack
        self.base_dirs = tuple(base_dirs)
        self.tpldir = tpldir
        self.tplroot = tplroot
        self.custom_data = custom_data or {}
        self.config_get_strategy = config_get_strategy
        self.merge_strategy = merge_strategy or "smart"
        self.merge_lists = merge_lists if merge_lists is not None else False

    def merge_result(self, result: MatcherResult) -> None:
        if not result:  # pragma: no cover
            return
        strategy = (
            result.merge_strategy if result.merge_strategy is not None else self.merge_strategy
        )
        merge_lists = result.merge_lists if result.merge_lists is not None else self.merge_lists
        self.stack = merge(
            self.stack,
            result.values,
            strategy=strategy,
            merge_lists=merge_lists,
        )


class Matcher(SlotsReprTrait):
    __slots__ = ("query", "options", "delimiter")

    query: str
    options: tuple[str, ...]
    delimiter: str

    def __init__(
        self, query: str, options: Sequence[str] = (), delimiter: Optional[str] = ":", **_
    ):
        self.query = query
        self.delimiter = delimiter or ":"
        if not options or options == ("",):
            self.options = ()
        else:
            self.options = tuple(options) if not isinstance(options, str) else (options,)

    def value(self, **kwargs) -> MatcherResult:
        res = self._fetch(**kwargs)
        if not res:
            return res
        if "SUB" in self.options:
            if self.query.endswith(f"{self.delimiter}lookup"):
                res.values = {self.query[:-7]: res.values}
            else:
                res.values = {self.query: res.values}
        return res

    def value_list(self, **kwargs) -> MatcherListResult:
        res = self._fetch(**kwargs)
        return MatcherListResult(query=res.query, values=res.values)

    def _fetch(self, **_):
        raise NotImplementedError


class ConfigMatcher(Matcher):
    __slots__ = ("_config_get",)

    _config_get: Callable

    def __init__(self, *args, __salt__, **kwargs):
        super().__init__(*args, __salt__=__salt__, **kwargs)
        # This is used in the wrapper as well, where the methods
        # don't have access to the loader dunders.
        self._config_get = __salt__["config.get"]

    def _fetch(self, *, render_context, **_):  # pylint: disable=arguments-differ
        values = self._config_get(
            self.query, ..., merge=render_context.config_get_strategy, delimiter=self.delimiter
        )
        return MatcherResult.from_bare(self.query, values)


class GrainsMatcher(Matcher):
    __slots__ = ("_grains_get",)

    _grains_get: Callable

    def __init__(self, *args, __salt__, **kwargs):
        super().__init__(*args, __salt__=__salt__, **kwargs)
        # This is used in the wrapper as well, where the methods
        # don't have access to the loader dunders.
        self._grains_get = __salt__["grains.get"]

    def _fetch(self, **_):
        values = self._grains_get(self.query, ..., delimiter=self.delimiter)
        return MatcherResult.from_bare(self.query, values)


class PillarMatcher(Matcher):
    __slots__ = ("_pillar_get",)

    _pillar_get: Callable

    def __init__(self, *args, __salt__, **kwargs):
        super().__init__(*args, __salt__=__salt__, **kwargs)
        # This is used in the wrapper as well, where the methods
        # don't have access to the loader dunders.
        self._pillar_get = __salt__["pillar.get"]

    def _fetch(self, **_):
        values = self._pillar_get(self.query, ..., delimiter=self.delimiter)
        return MatcherResult.from_bare(self.query, values)


class MapdataMatcher(Matcher):
    def _fetch(self, *, render_context, **_):  # pylint: disable=arguments-differ
        values = traverse(render_context.stack, self.query, ..., delimiter=self.delimiter)
        return MatcherResult.from_bare(self.query, values)


class CustomMatcher(Matcher):
    def _fetch(self, *, render_context, **_):  # pylint: disable=arguments-differ
        values = traverse(render_context.custom_data, self.query, ..., delimiter=self.delimiter)
        return MatcherResult.from_bare(self.query, values)


class StaticMatcher(Matcher):
    def value(self, **kwargs):
        raise NotImplementedError("The StaticMatcher cannot be used for querying data")

    def value_list(self, **kwargs):
        return MatcherListResult(query="", values=[self.query])

    def is_file_name(self):
        return Path(self.query).suffix != ""


class Renderer(SlotsReprTrait):
    __slots__ = ("_matchers", "render_context", "chain_finished")

    _matchers: list[Matcher]
    render_context: RenderContext
    chain_finished: bool

    def __init__(self, render_context: RenderContext):
        self.render_context = render_context
        self._matchers = []
        self.chain_finished = False

    def add_matcher(self, matcher: Matcher) -> None:
        if self.chain_finished:
            raise ValueError(
                f"Cannot append other matchers after `{self._matchers[-1]}`: {matcher}"
            )
        try:
            if matcher.is_file_name():  # type: ignore
                self.chain_finished = True
        except AttributeError:
            pass

        self._matchers.append(matcher)

    def render(self) -> RenderContext:
        res = None
        default_merge_strategy = merge_strategy = self.render_context.merge_strategy
        default_merge_lists = merge_lists = self.render_context.merge_lists

        for matcher in self._matchers:
            if res is None:
                res = matcher.value(render_context=self.render_context)
                if not res:
                    return self.render_context
                merge_strategy = (
                    res.merge_strategy if res.merge_strategy is not None else default_merge_strategy
                )
                merge_lists = (
                    res.merge_lists if res.merge_lists is not None else default_merge_lists
                )
                continue
            intermittent = {}
            metadata = matcher.value_list(render_context=self.render_context)
            if not metadata:
                return {}
            for lookup in metadata.values:
                intermittent = merge(
                    intermittent,
                    traverse(res.values, lookup, {}),
                    strategy=merge_strategy,
                    merge_lists=merge_lists,
                )
            res.values = intermittent

        self.render_context.merge_result(res)  # type: ignore
        return self.render_context

    def render_path(
        self,
        include_query: bool = True,
        base_dirs: Optional[list[str]] = None,
        fallback_to_query: bool = False,
    ) -> list[str]:
        relative_parts = []
        for matcher in self._matchers:
            res = matcher.value_list(render_context=self.render_context)
            if not res:
                if not fallback_to_query:
                    return []
                relative_parts.append([res.query])
            elif include_query:
                relative_parts.append([_concat_parts(res.query, r) for r in res.values])  # type: ignore
            else:
                relative_parts.append(res.values)  # type: ignore
        relative_paths = [_concat_parts(rel) for rel in itertools.product(*relative_parts)]
        absolute_paths = [
            _concat_parts(absolute)
            for absolute in itertools.product(
                base_dirs or self.render_context.base_dirs, relative_paths
            )
        ]
        return absolute_paths


class YAMLRenderer(Renderer):
    __slots__ = ("_get_template",)

    _get_template: Callable

    def __init__(self, render_context: RenderContext, _get_template: Callable):
        super().__init__(render_context)
        self._get_template = _get_template

    def render(self) -> RenderContext:
        for path in self.render_path():
            for yaml_result in self._load_yaml(path):
                self.render_context.merge_result(yaml_result)

        return self.render_context

    def _load_yaml(self, path: str):
        file_ext = Path(path).suffix
        ext_paths: list[str] = []
        if file_ext not in (".yaml", ".jinja"):
            ext_paths.extend((f"{path}.yaml", f"{path}.yaml.jinja"))
        elif file_ext == ".yaml":
            ext_paths.extend((path, f"{path}.jinja"))
        else:
            ext_paths.append(path)
        res = []
        for ext_path in ext_paths:
            yaml_cached = self._get_template(
                ext_path,
                tpldir=self.render_context.tpldir,
                tplroot=self.render_context.tplroot,
                mapdata=self.render_context.stack,
                custom_data=self.render_context.custom_data,
            )
            if not yaml_cached:
                continue
            with salt.utils.files.fopen(yaml_cached, "r") as ptr:
                yaml_values = salt.utils.yaml.safe_load(ptr)
            try:
                res.append(MatcherResult(**yaml_values, query=""))
            except TypeError as err:
                raise TypeError(f"Got invalid data from salt://{ext_path}: {err}") from err

        return res


def _concat_parts(*parts: Union[str, Iterable[str]]) -> str:
    # We don't want to account for the OS-specific path separator
    return "/".join(
        chain.from_iterable(
            (
                (ppart.strip("/") for ppart in part if ppart)
                if isinstance(part, Iterable) and not isinstance(part, str)
                else [part.strip("/")]
            )
            for part in parts
            if part
        )
    )


TYP_CLS_MAP: dict[str, type[Matcher]] = {
    "G": GrainsMatcher,
    "I": PillarMatcher,
    "C": ConfigMatcher,
    "M": MapdataMatcher,
    "U": CustomMatcher,
    "P": StaticMatcher,
}


def _render_matcher_chain(
    mchain: str, render_context: RenderContext, for_path_rendering: bool = False
) -> Renderer:
    """
    Parse a [chain of] matcher definitions into a Renderer, which can be used
    to render the result.

    .. note::
        In the context of mapstack/tofs configuration, this parses a single item
        of ``sources``/``files_switch``, which are allowed to contain a series
        of matchers.

    mchain
        A matcher definition, which can contain a chain of multiple single ones.

    render_context
        A RenderContext instance providing data necessary for rendering.

    for_path_rendering
        Disable YAML file loading and use different defaults when no matcher is specified.
        [Given ``os``; false: ``Y!C@os``; true: ``C@os``]
        Defaults to false.
    """
    yaml_renderer = mchain.startswith("Y!")
    if yaml_renderer:
        if for_path_rendering:
            raise ValueError(f"Cannot use YAML renderer for path rendering: {mchain}")
        mchain = mchain[2:]

    matcher_chain = mchain.split("|")
    initial_matcher, is_yaml = _render_matcher(
        matcher_chain[0], for_path_rendering=for_path_rendering
    )
    if yaml_renderer or is_yaml:
        renderer: Renderer = YAMLRenderer(render_context, _get_template)
    else:
        renderer = Renderer(render_context)
    renderer.add_matcher(initial_matcher)
    for single in matcher_chain[1:]:
        matcher, is_yaml = _render_matcher(single, for_path_rendering=for_path_rendering)
        if is_yaml:
            raise ValueError(f"Cannot use YAML matcher in query chains: `{chain}`")
        renderer.add_matcher(matcher)
    return renderer


def _render_matcher(matcher: str, for_path_rendering=False) -> tuple[Matcher, bool]:
    """
    Parse a single matcher definition into a Matcher and indicate whether its
    result should be parsed by loading a YAML file or directly.

    matcher
        A matcher definition for a single matcher.

    for_path_rendering
        Disable YAML file loading and use different defaults when no matcher is specified.
        [Given ``os``; false: ``Y!C@os``; true: ``C@os``]
        Defaults to false.
    """
    query, *key = matcher.split("@")
    if key:
        typ, option, delimiter, *rest = chain(query.split(":"), [None] * 2)
        if rest and rest[0] == "":
            # colon as delimiter was explicitly specified via Y:C::@roles
            delimiter = ":"
        if typ == "Y":
            if for_path_rendering:
                raise ValueError(f"YAML type is not allowed in this context. Got: {matcher}")
            subtyp = option or "C"
            return TYP_CLS_MAP[subtyp](query=key[0], delimiter=delimiter, __salt__=__salt__), True

        return (
            TYP_CLS_MAP[typ](  # type: ignore
                query=key[0],
                options=tuple((option or "").split(",")),
                delimiter=delimiter,
                __salt__=__salt__,
            ),
            False,
        )
    if query.endswith((".yaml", ".jinja")):
        if for_path_rendering:
            raise ValueError(f"YAML type is not allowed in this context. Got: {matcher}")
        # Static file path like defaults.yaml
        return StaticMatcher(query=query, options=()), True
    # Configuration without @, example: mysql.
    return TYP_CLS_MAP["C"](query=query, __salt__=__salt__), not for_path_rendering


def _get_template(path, **kwargs):
    return __salt__["cp.get_template"](
        f"salt://{path}",
        "",
        **kwargs,
    )
