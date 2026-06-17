"""Lib - Device Library Package


.. figure:: images/lib.png
    :width: 800px
    :align: center

    **Lib Class Diagram**


This is the core utility library used across the project. This package
collects small, well-tested modules that provide common functionality
such as:

- configuration and environment helpers
- logging and diagnostics wrappers
- data transformation and validation utilities
- file and resource loaders

The package is intentionally lightweight and dependency-minimal so it
can be imported from command-line tools, tests, and other packages
without side-effects. Import individual submodules or symbols to keep
startup fast.

"""