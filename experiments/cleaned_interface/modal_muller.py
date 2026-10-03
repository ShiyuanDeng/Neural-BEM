"""Compatibility import for :mod:`bem_inverse.modal_muller`; edit the maintained module there."""
import sys
from importlib import import_module

_implementation = import_module('bem_inverse.modal_muller')

if __name__ in ('__main__', '__mp_main__'):
    _implementation.register()
    if __name__ == '__main__':
        from .__main__ import main
        main()
else:
    sys.modules[__name__] = _implementation
