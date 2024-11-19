(details-target)=
# Mapstack Details

(yaml-data-source-target)=
## YAML data source

### Structure
When a single YAML file is loaded, it should return a configuration dictionary structured as follows:

* `values` provides the actual formula configuration, representing a layer
* `strategy` (optional) allows to influence how this layer is merged with the previous ones. Please see {py:func}`slsutil.merge <salt.modules.slsutil.merge>` for available values.
* `merge_lists` (optional) specifies whether lists in this layer should be appended to lists from previous layers or override them.

```yaml
# A YAML data source showcasing defaults.
strategy: smart
merge_lists: false
values: {}
```

### Templating
YAML data sources are always rendered using the `jinja` renderer, meaning you have full access to all of Salt's functionality.

Additionally, the following variables are provided:

* `tplroot`: The formula root directory relative to the Salt fileserver root.
* `mapdata`: Merged configuration from the previous layers.
* `custom_data`: A custom mapping passed by the caller and used by the `U@` matcher.

(post-map-jinja-target)=
## `post-map.jinja`
This template, relative to the formula root, is executed before returning the layered configuration. It should modify `mapdata` in place.

Suppose a formula installs `borg` from GitHub releases. It allows to set the `version` to `latest`, but must know which specific version corresponds `latest` to correctly identify needed changes. A `salt://borg/post-map.jinja` file could check whether `mapdata.version` is set to `latest`, and if it is, query the GitHub API to discover the specific version and replace `latest` with it:

```jinja
{%- if mapdata.version == "latest" %}
{%-   set latest_version = salt["http.query"](mapdata.lookup.latest_release_uri, decode=True, decode_type="json").dict.latest.version %}
{%-   do mapdata.update({"version": latest_version}) %}
{%- endif %}
```

## Meta configuration

Formula authors and users can influence many aspects of the layering process:

* Default layering configuration can be passed to {py:func}`map.data <saltext.formula.modules.map.data>` directly.
* Formulae can provide custom [`map_jinja.yaml`](map-jinja-yaml-target) files.
* Users can add custom formula-specific or global [`map_jinja.yaml`](map-jinja-yaml-target) files.

(map-jinja-yaml-target)=
### `map_jinja.yaml`
Before starting the configuration layering process, meta configuration is loaded using the
same process. By default, a formula named `vault` would aggregate the following paths
into the meta configuration:

* `salt://parameters/map_jinja.yaml`
* `salt://parameters/map_jinja.yaml.jinja`
* `salt://vault/parameters/map_jinja.yaml`
* `salt://vault/parameters/map_jinja.yaml.jinja`

Since it uses the regular layering process, the root structure should follow the [YAML data source format](yaml-data-source-target).
Inside `values`, all optional parameters to {py:func}`saltext.formula.modules.map.data` can be overridden.

```sls
# A map_jinja.yaml file showcasing defaults.
strategy: smart
merge_lists: false
values:
  config_get_strategy: null
  default_merge_strategy: null
  default_merge_lists: false
  parameter_dirs:
    - {{ tplroot }}/parameters
  post_map: post-map.jinja
  post_map_template: jinja
  sources:
    - Y!G@osarch
    - Y!G@os_family
    - Y!G@os
    - Y!G@osfinger
    - C@{{ tplroot }}
    - Y!G@id
```

(matcher-def-target)=
## Data source definition

Configuration source layers are specified usig a list of matcher definitions
that decide where to pull the configuration from.

.. versionadded:: 0.3.0
    These matcher definitions can each represent a chain, as shown in [Data source chains](data-source-chains-target).

### Spec (chain)
A chain consists of one or more single matcher definitions: `[Y!]<single_def_0>[|<single_def_1>[|...]]`

`Y!` prefix
:   Indicates that the returns of the following matchers should be used
    to render paths to parameter files. They are rendered using Jinja and loaded as YAML.

`single_def`
:   A [single matcher definition](spec-single-target). Multiple ones are separated by a `|`.

(spec-single-target)=
### Spec (single)

Matcher definitions are structured like the following: `[<type>[:<option>[:<delimiter>]]@]<query>`

type
:   The layer's configuration data source.

    `C`
    :   Query {py:func}`config.get <salt.modules.config.get>` and use its
        return as this layer's configuration.

    `G`
    :   Query {py:func}`grains.get <salt.modules.grains.get>` and use its
        return as this layer's configuration.

    `I`
    :   Query {py:func}`pillar.get <salt.modules.pillar.get>` and use its
        return as this layer's configuration.

    `P`
    :   Specify that this query is a static one (represents a static path).

    `M`
    :   Traverse the currently rendered configuration. Mostly useful in chains.

    `U`
    :   Traverse the dictionary passed by the caller as `custom_dict`. Useful in chains or when
        enforcing specific overrides.

option
:   An option, valid values depend on the `type`.

    This can be set to `SUB`, which nests the result inside the key defined by `query`
    instead of merging it into the stack root.

delimiter
:   Define a different delimiter for the query. This can be important on Windows
    when loading YAML files since the path contains the `query` value and the default
    delimiter is disallowed in paths on Windows. Defaults to `:`.

query
:   The value to look up with `type`.

### Examples

`I@mysql`
:   Run `salt["pillar.get"]("mysql")` and merge the resulting dictionary into the stack.

`Y!roles`
:   Run `salt["config.get"]("roles")`, build a list of paths, render and load
    the files and merge the resulting dictionary into the stack.

    Shorthand: `roles`

    For example, if a minion has a pillar value `roles` containing `[db, db_master]`,
    the following files relative to configurable directories are tried:

    - `roles/db.yaml`
    - `roles/db.yaml.jinja`
    - `roles/db_master.yaml`
    - `roles/db_master.yaml.jinja`

    :::{note}
    Notice how lists are expanded into separate paths. The same works for dictionary keys.
    :::

`Y!I@roles`
:   Does the same as `Y!roles`, but restricts the value source to the pillar.

`Y!P@defaults.yaml`
:   Don't query metadata, always load this static path as a YAML data source.

`Y!G::!@selinux!enabled`
:   Run `salt["`{py:func}`config.get <salt.modules.config.get>``"]("selinux!enabled", delimiter="!")`, build a list of paths, render and load
    the files and merge the resulting dictionary into the stack.
    If SELinux is enabled on the minion, the tried paths are:

    - `selinux!enabled/True.yaml`
    - `selinux!enabled/True.yaml.jinja`

`Y!G@os_family|I@roles`
:   See [YAML chaining](data-source-chains-yaml-target).

`C@tplroot:variant_defaults|M@variant`
:   See [raw chaining](data-source-chains-raw-target).

## Differences to `template-formula` with `libmapstack.jinja`
### Breaking
* The default `slsutil.merge` and `config.get` merge strategy was looked up via `salt["config.get"]("{tplroot}:strategy")`. This behavior was dropped in favor of configuring this in `map_jinja.yaml` only. This keeps formula configuration in one place and allows to specify both strategies separately from each other.

### Added features
* Cached configuration, reducing rendering times significantly
* All meta configuration parameters are read from `map_jinja.yaml`
* The name of `post-map.jinja` and its template language are configurable
* Added `U` (custom data)/`P` (static path)/`M` (mapdata) matchers
* Allowed to chain multiple matchers to load parameter paths that vary in two or more variables
* Allowed to chain multiple matchers to filter raw (non-YAML) matcher returns

### Changed
* An obvious file data source like `defaults.yaml` was first tried via `salt["config.get"]`. This has been removed.
* If a data source query did not yield any results, it was tried as a YAML file path instead. This has been removed.
* The `Y:` type matcher has been deprecated. The `Y!` prefix should be used instead.
