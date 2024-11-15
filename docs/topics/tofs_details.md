# TOFS Details

## Configuration
{py:func}`map.tofs <saltext.formula.modules.map.tofs>` relies on {py:func}`map.data <saltext.formula.modules.map.data>`
to render the formula configuration, meaning its configuration can be set in any mapstack source.

The following keys influence the rendered file paths:

### `tofs`
The top-level `tofs` key overrides the default values that are passed when calling `map.tofs`.
It also provides additional settings.

`tofs:dirs:default`
:   The name of the directory serving as a fallback.

`tofs:dirs:files`
:   The name of the directory containing the files.

`tofs:files_switch`
:   A list of matcher definitions that are considered when rendering possible sources.

`tofs:include_query`
:   Include the query part of the matcher definition in file paths.

`tofs:path_prefix`
:   Provide an alternative prefix for all rendered file paths.

`tofs:source_files`
:   When `map.tofs` is invoked with a `lookup` parameter, its value is looked up here.
    Users can provide alternative file names that are prepended to the default ones.

All options with defaults:

```yaml
tofs:
  dirs:
    default: default
    files: files
  files_switch:
    - id
    - os_family
  include_query: true
  path_prefix: '{{ tplroot }}'
  source_files: {}
```

### `files_switch`
When a formula contains multiple `files` directories (`use_subpath=true`), it's possible to provide different
matcher lists for each one. The configuration key mirrors its path relative to the formula root directory.

For example, if your formula has a `formula/subcomponent/config/files` directory specifically for states in `formula/subcomponent/config`,
its matchers could be overridden in `subcomponent:config:files_switch`.
