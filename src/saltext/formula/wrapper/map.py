"""
SSH wrapper for the :py:mod:`map <saltext.formula.modules.map>` execution module.

See there for documentation.

.. important::
    This wrapper requires the ``cp`` wrapper introduced in Salt 3007.0.
"""

import logging

from salt.utils.functools import namespaced_function

from saltext.formula.modules.map import _render_matcher as _render_matcher_base
from saltext.formula.modules.map import _render_matchers as _render_matchers_base
from saltext.formula.modules.map import data
from saltext.formula.modules.map import stack
from saltext.formula.modules.map import tofs

log = logging.getLogger(__name__)

__virtualname__ = "map"


def __virtual__():
    return __virtualname__


data = namespaced_function(data, globals())
stack = namespaced_function(stack, globals())
tofs = namespaced_function(tofs, globals())
_render_matcher = namespaced_function(_render_matcher_base, globals())
_render_matchers = namespaced_function(_render_matchers_base, globals())


for func, base in (
    (_render_matcher, _render_matcher_base),
    (_render_matchers, _render_matchers_base),
):
    # namespaced_function does not initialize keyword-only argument defaults,
    # making them required arguments.
    # The module functions (data/stack/tofs) cannot use them since
    # Salt does not recognize them when using the CLI to call them.
    # Starting with Python 3.13, it's possible to pass `kwdefaults` to types.FunctionType
    if getattr(base, "__kwdefaults__", None) is not None:
        func.__kwdefaults__ = base.__kwdefaults__.copy()


def _get_template(path, **kwargs):
    res = __salt__["cp.get_template"](
        f"salt://{path}",
        "",
        **kwargs,
    )
    if not res:
        return res
    return __salt__["cp.convert_cache_path"](res)
