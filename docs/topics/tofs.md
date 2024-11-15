# TOFS Overview

The Template Override/Files Switch pattern (TOFS) is an analog to Mapstack for managing files. It allows formula authors to provide possible file `sources` to states that are matched to minion metadata. The first URL that actually exists on the fileserver is selected. A formula can therefore provide environment-specific default files that users can easily override.

## Example
For example, an `nginx` formula could provide the following files:

- `salt://nginx/files/os_family/Debian/nginx.conf.j2`
- `salt://nginx/files/os_family/RedHat/nginx.conf.j2`
- `salt://nginx/files/default/nginx.conf.j2`

The following state would then render different file contents, depending on which OS it's rendered on, while giving users the option to override the source for a specific minion:

```sls
# For simplicity, we're not using mapstack in this example.

Manage nginx.conf:
  file.managed:
    - name: /etc/nginx/nginx.conf
    - sources:
      - salt://nginx/files/id/{{ grains.id }}/nginx.conf
      - salt://nginx/files/id/{{ grains.id }}/nginx.conf.j2
      - salt://nginx/files/os_family/{{ grains.os_family }}/nginx.conf
      - salt://nginx/files/os_family/{{ grains.os_family }}/nginx.conf.j2
      - salt://nginx/files/default/nginx.conf
      - salt://nginx/files/default/nginx.conf.j2
```

Since hardcoding all possible sources in state files reduces flexibility and is repetitive, {py:func}`map.tofs <saltext.formula.modules.map.tofs>` provides a flexible and user-influencable way to generate the `sources` list.

## How
```sls
Manage nginx.conf:
  file.managed:
    - name: /etc/nginx/nginx.conf
    - sources: {{ salt["map.tofs"](tpldir, ["nginx.conf", "nginx.conf.j2"]) | json }}
```

## Differences to `libtofs.jinja`
* By default, includes the query in file paths (`files/os_family/Debian` instead of `files/Debian`). This can be disabled via the `include_query` parameter.
* Reads `tofs` configuration from all Mapstack sources (including YAML). Previously, this configuration could only be set in pillars/grains/opts.
* Accepts matcher definitions for file paths in the [same style as Mapstack](matcher-def-target) (excluding `Y@`).

## Reference
This overview is currently very basic. For details, see the [original description][tofs-pattern].

[tofs-pattern]: https://github.com/saltstack-formulas/template-formula/blob/master/docs/TOFS_pattern.rst
