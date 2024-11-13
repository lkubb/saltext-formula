"""
SSH wrapper for the :py:mod:`map <saltext.formula.modules.map>` execution module.

See there for documentation.
"""

import logging

from salt.utils.functools import namespaced_function

from saltext.formula.modules.map import _render_matcher
from saltext.formula.modules.map import _render_matchers
from saltext.formula.modules.map import data
from saltext.formula.modules.map import stack

log = logging.getLogger(__name__)

__virtualname__ = "map"


def __virtual__():
    return __virtualname__


data = namespaced_function(data, globals())
stack = namespaced_function(stack, globals())
_render_matcher = namespaced_function(_render_matcher, globals())
_render_matchers = namespaced_function(_render_matchers, globals())
