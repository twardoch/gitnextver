# this_file: src/gitnextver/__init__.py
"""gitnextver - Automatically bump semantic version tags in Git repositories."""

try:
    from gitnextver.__version__ import __version__
except ImportError:
    from importlib.metadata import version, PackageNotFoundError

    try:
        __version__ = version("gitnextver")
    except PackageNotFoundError:
        __version__ = "0.0.0"
