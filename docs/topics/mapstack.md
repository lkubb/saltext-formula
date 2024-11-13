# Mapstack Overview

This Salt extension, specifically its {py:func}`map.data function <saltext.formula.modules.map.data>`, is designed to streamline formula development while providing users an easy and precise way to override configuration defaults. Traditionally, Salt formulae rely heavily on Jinja templating to handle diverse environments and use the pillar as a configuration source. However, this approach can lead to complicated state files and take a toll on the master.

An existing Jinja-based layered configuration model called `mapstack` provides a different approach to handle formula configuration requirements. This extension improves upon the Jinja-based implementation by rewriting it in Python and allowing to cache the rendered configuration when rendering multiple state files, which reduces rendering time significantly. It's also much easier to test and improve.

## Benefits of the Layered Approach

Layered configuration enables a systematic way to manage configurations that need to vary across systems, environments or other factors (e.g. user-defined roles). This approach brings several advantages:

- **Reduced Master Load**: By sourcing non-sensitive configuration data from YAML files rather than pillars, the load on the Salt master is reduced, as pillars are resource-intensive to render.

- **Modularity and Scalability**: Layered configuration supports modular management by allowing configurations to adapt to specific system attributes. For example, users can specify overrides for configurations based on OS, version, custom role, or DNS domain.

- **Easy Customizability**: The structure separates configuration logic from state templates, making it easier to supply configuration or customize behavior without directly modifying Salt state files. You will never need to hardcode your calls to `vault.read_secret` again!

- **Ease of Maintenance**: The decoupled structure also makes it easier to update and maintain formulae by improving clarity.

In essence, this extension simplifies managing diverse system configurations by enabling easy adjustments across a range of parameters, without sacrificing performance.

## Key concepts

:::{note}
This describes basics only. Many aspects of the layering process are highly configurable, see [Details](details-target)
:::

### Data sources

Each [data source](matcher-def-target) provides a single configuration layer. Usually, data sources are YAML files in a formula's `parameters` directory that are associated with minions based on grain (`Y:G@os`) or pillar (`Y:I@roles`) variables.

:::{hint}
As you might have noticed, this takes significant inspiration from Salt's pillar top files.
:::

A data source can also be one of the inbuilt global configuration dictionaries directly, mimicing the usual pillar-based configuration (`I@formula_name`).

Based on their hierarchy, all data source returns are merged into a single configuration dictionary.

#### Default behavior

The following data sources are used by default:

```yaml
- defaults.yaml
- Y:G@osarch
- Y:G@os_family
- Y:G@os
- Y:G@osfinger
- C@{{ tplroot }}
- Y:G@id
```

A `vault` formula being executed on a Rocky Linux 9 minion called `vault1`, running on an x86-64 architecture, would thus try the following data sources in order and merge later results on top of previous ones:

- `salt://borgmatic/parameters/defaults.yaml`
- `salt://borgmatic/parameters/defaults.yaml.jinja`
- `salt://borgmatic/parameters/osarch/x86_64.yaml`
- `salt://borgmatic/parameters/osarch/x86_64.yaml.jinja`
- `salt://borgmatic/parameters/os_family/RedHat.yaml`
- `salt://borgmatic/parameters/os_family/RedHat.yaml.jinja`
- `salt://borgmatic/parameters/os/Rocky Linux.yaml`
- `salt://borgmatic/parameters/os/Rocky Linux.yaml.jinja`
- `salt://borgmatic/parameters/osfinger/Rocky Linux-9.yaml`
- `salt://borgmatic/parameters/osfinger/Rocky Linux-9.yaml.jinja`
- `salt["`{py:func}`config.get <salt.modules.config.get>``"]("borgmatic")`
- `salt://borgmatic/parameters/id/vault1.yaml`
- `salt://borgmatic/parameters/id/vault1.yaml.jinja`

### `parameters` directory

Each formula provides its own [YAML data sources](yaml-data-source-target) in a directory called `parameters`, for example, an `openssh` formula would find them in `salt://openssh/parameters/`.

#### `defaults.yaml`
The `parameters/defaults.yaml` file provides the base formula configuration, ensuring sane defaults. It is always loaded.

#### YAML data sources
Inside the `parameters` directory, there are several subdirectories containing YAML configuration. This path structure allows to map minion metadata queries (usually grains/pillar lookups) to their results. For example, if a data source is defined as `Y:G@os`, a `parameters/os` directory should contain files such as `Debian.yaml`, `Fedora.yaml`.

They are rendered as Jinja templates.

#### `map_jinja.yaml`
An optional [`map_jinja.yaml`](map-jinja-yaml-target) is loaded before composing the formula configuration. It can influence the process by providing configuration for the rendering process itself, e.g. [data source definitions](matcher-def-target).

### `post-map.jinja`
An optional [`post-map.jinja`](post-map-jinja-target) file found in the formula root receives the merged configuration and can tweak it in-place before it is returned.

## Example

### Basic

Let's say an `apache` formula needs to install the Apache HTTP server. Usually, the package is called `apache2`, but on RHEL-like systems it's `httpd`. The default web root is always `/var/www`.

A formula could include the following parameter files:

```yaml
# parameters/defaults.yaml
pkg_name: apache2
webroot: /var/www
```

```yaml
# parameters/os_family/RedHat.yaml
pkg_name: httpd
```

A corresponding state file could look like this:

```sls
{%- set apache = salt["map.data"](tpldir) %}

Install Apache:
  pkg.installed:
    - name: {{ apache.pkg_name }}
```

Later, a user wants to override the default web root for Debian systems. To achieve this, they can create their own parameters file in `/srv/salt/apache/parameters/os/Debian.yaml`:

```yaml
webroot: /var/w3
```

Notice how this modification is transparent to the formula, i.e. the user did not need to modify any files in the formula itself. If the formula is served from a git fileserver or a dedicated `file_roots` entry, it's decoupled completely.

### Advanced

:::{important}
This extension is mostly backwards-compatible with formulae based on the [template-formula](https://github.com/saltstack-formulas/template-formula) using `libmapstack.jinja`. The [map.jinja documentation](https://github.com/saltstack-formulas/template-formula/blob/master/docs/map.jinja.rst) there provides some advanced configuration guides.
:::

Suppose we wrote a `borgmatic` formula that installs Borgmatic and configures it to backup important directories and databases. It has a `backup_paths` configuration, which is empty by default:

```yaml
# borgmatic/parameters/defaults.yaml
backup_paths: []
```

Of course, the exact data to backup depends on the software that is running on the node. Which software is installed on your nodes is decided by assigning a `roles` pillar to the minion.

It's possible to configure the `borgmatic` formula to consider your `roles` pillar for configuration layering. You can achieve this by creating a `map_jinja.yaml` file that overrides the default [data sources](matcher-def-target), adding a data source of `Y:I@roles`:

```yaml
# either   salt://borgmatic/parameters/map_jinja.yaml[.jinja]   for formula-specific overrides
# or       salt://parameters/map_jinja.yaml[.jinja]             for all formulae
values:
  sources:
    - Y:G@osarch
    - Y:G@os_family
    - Y:G@os
    - Y:G@osfinger
    - C@{{ tplroot }}
    - Y:I@roles
    - Y:G@id
```

A minion with `pillar["roles"] == ["gitea", "ci"]` would then take the following additional paths into account:

* `salt://borgmatic/parameters/roles/gitea.yaml`
* `salt://borgmatic/parameters/roles/gitea.yaml.jinja`
* `salt://borgmatic/parameters/roles/ci.yaml`
* `salt://borgmatic/parameters/roles/ci.yaml.jinja`

Take these YAML definitions:

```yaml
# salt://borgmatic/parameters/roles/gitea.yaml
merge_lists: true
values:
  backup_paths:
    - /opt/gitea
```

```yaml
# salt://borgmatic/parameters/roles/ci.yaml
merge_lists: true
values:
  backup_paths:
    - /opt/important/path
```

They would be merged transparently into:

```yaml
backup_paths:
  - /opt/gitea
  - /opt/important/path
```

## Tips

### Overriding formula defaults
Most formulae provide a `parameters/defaults.yaml`, which users should not modify. They can however create a custom `parameters/defaults.yaml.jinja`, which is merged on top of `defaults.yaml`. The same is true whan a formula provides other data sources, e.g. `os_family/Debian.yaml`.
