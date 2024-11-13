# Installation

Generally, extensions need to be installed into the same Python environment Salt uses.

:::{tab} State
```yaml
Install Salt Formula extension:
  pip.installed:
    - name: saltext-formula
```
:::

:::{tab} Onedir installation
```bash
salt-pip install saltext-formula
```
:::

:::{tab} Regular installation
```bash
pip install saltext-formula
```
:::

:::{hint}
Saltexts are not distributed automatically via the fileserver like custom modules, they need to be installed
on each node you want them to be available on.
:::
