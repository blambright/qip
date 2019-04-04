# :coding: utf-8

from __future__ import print_function

import os
import tempfile
import shutil
try:
    import queue as _queue
except ImportError:
    import Queue as _queue

import click
import mlog

import qip.definition
import qip.package
import qip.filesystem
import qip.environ
import qip.symbol

from ._version import __version__


def install(
    requests, output_path, definition_path=None, overwrite=False,
    no_dependencies=False, editable_mode=False, python_target="python==2.7.*",
    definition_mapping=None
):
    """Install packages to *output_path* from *requests*.

    :param requests: list of packages to be installed

        A request can be one of::

            ["."]
            ["/path/to/foo/"]
            ["foo", "bar"]
            ["foo==0.1.0"]
            ["foo >= 7, < 8"]
            ["git@gitlab:rnd/foo.git"]
            ["git@gitlab:rnd/foo.git@0.1.0"]
            ["git@gitlab:rnd/foo.git@dev"]

    :param output_path: root destination path for Python packages installation.
    :param definition_path: :term:`Wiz` definition extraction path. Default is
        None, which means that :term:`Wiz` definitions are not extracted.
    :param overwrite: indicate whether packages already installed and
        corresponding :term:`Wiz` definitions should be overwritten. If None, a
        user confirmation will be prompted. Default is False.
    :param no_dependencies: indicate whether package dependencies should be
        skipped. Default is False.
    :param editable_mode: indicate whether the Python package location should
        target the source installation package. Default is False.
    :param python_target: Target a specific Python version via a Wiz request or
        a path to a Python executable (e.g. "python==2.7.*" or
        "/path/to/bin/python"). Default is "python==2.7.*".
    :param definition_mapping: None or mapping regrouping all available
        :term:`Wiz` definitions. Default is None.

    :return: Boolean value.

    """
    logger = mlog.Logger(__name__ + ".install")

    qip.filesystem.ensure_directory(output_path)
    if definition_path is not None:
        qip.filesystem.ensure_directory(definition_path)

    # Setup temporary folder for package installation.
    cache_path = tempfile.mkdtemp()
    package_path = tempfile.mkdtemp()

    try:
        # Fetch environment mapping and installation path.
        context_mapping = fetch_context_mapping(package_path, python_target)
        library_path = context_mapping["environ"]["PYTHONPATH"]

        # Needed for the editable mode.
        qip.filesystem.ensure_directory(library_path)

        # Record requests and package installed to prevent duplications.
        installed_packages = set()
        installed_requests = set()

        # Fill up queue with requirements extracted from requests.
        queue = _queue.Queue()

        for request in requests:
            queue.put(request)

        while not queue.empty():
            request = queue.get()
            if request in installed_requests:
                continue

            # Clean up before installation.
            logger.debug("Clean up directory content before installation")
            qip.filesystem.remove_directory_content(package_path)

            try:
                package_mapping = qip.package.install(
                    request, package_path, context_mapping, cache_path,
                    editable_mode=editable_mode
                )

            except RuntimeError as error:
                logger.error(str(error))
                continue

            if package_mapping["identifier"] in installed_packages:
                continue

            installed_packages.add(package_mapping["identifier"])
            installed_requests.add(request)

            # Install package to destination.
            success, overwrite = copy_to_destination(
                package_mapping,
                package_path,
                output_path,
                overwrite=overwrite
            )

            if not success:
                continue

            # Extract a wiz definition is requested.
            if definition_path is not None:
                qip.definition.export(
                    definition_path,
                    package_mapping,
                    output_path,
                    editable_mode=editable_mode,
                    definition_mapping=definition_mapping
                )

            # Reset editable mode to False for requirements.
            editable_mode = False

            # Fill up queue with requirements extracted from package
            # dependencies.
            if not no_dependencies:
                for request in package_mapping.get("requirements", []):
                    queue.put(request)

    finally:
        shutil.rmtree(package_path)
        shutil.rmtree(cache_path)


def copy_to_destination(
    mapping, source_path, destination_path, overwrite=False
):
    """Copy package from *source_path* to *destination_path*.

    :param mapping: mapping of the python package built as returned by
        :func:`qip.package.install`.
    :param source_path: path where the package was built.
    :param destination_path: path to install to.
    :param overwrite: indicate whether packages already installed should be
        overwritten. If None, a user confirmation will be prompted. Default is
        False.

    :return: tuple with one boolean value indicating whether the copy has been
        done and one indicating a new value for the *overwrite* option.

    """
    logger = mlog.Logger(__name__ + ".copy_to_destination")

    identifier = mapping["identifier"]
    target = os.path.join(destination_path, mapping["target"])

    # By default, future overwrite request will the same as the present one.
    overwrite_next = overwrite

    if os.path.isdir(target):
        if overwrite is None:
            overwrite, overwrite_next = _confirm_overwrite(identifier)

        if overwrite:
            logger.warning(
                "Overwrite '{}' which is already installed.".format(identifier)
            )
            shutil.rmtree(target)

        else:
            logger.warning(
                "Skip '{}' which is already installed.".format(identifier)
            )

            return False, overwrite_next

    qip.filesystem.ensure_directory(os.path.dirname(target))
    shutil.copytree(source_path, target)
    logger.debug("Source copied to '{}'".format(target))

    logger.info("Installed '{}'.".format(identifier))

    return True, overwrite_next


def _confirm_overwrite(identifier):
    """Package overwrite confirmation prompt for *identifier*

    Return a tuple with one boolean value indicating whether *identifier* should
    be overwritten and one boolean indicating whether future packages should
    also be overwritten.

    """
    message = (
        "Overwrite '{}'? ([y]es, [n]o, [ya] yes to all, [na] no to all)"
        .format(identifier)
    )

    answer = click.prompt(
        message,
        type=click.Choice(["y", "n", "ya", "na"]),
        default="n",
        show_choices=False,
        show_default=False
    )

    overwrite = answer[0] == "y"
    overwrite_next = overwrite if "a" in answer else None
    return overwrite, overwrite_next


def fetch_context_mapping(path, python_target):
    """Return context mapping containing environment and python mapping.

    :param path: path where python package has been installed.
    :param python_target: Target a specific Python version via a Wiz request or
        a path to a Python executable (e.g. "python==2.7.*" or
        "/path/to/bin/python").

    :return: Context mapping.

        It should be in the form of::

            {
                "environ": {
                    "PATH": "/path/to/bin",
                    "PYTHONPATH": "/path/to/lib/python2.7/site-packages",
                },
                "python": {
                    "identifier": "2.7",
                    "request": "python >= 2.7, < 2.8",
                    "installation-target": "lib/python2.7/site-packages"
                }
            }

    """
    environ_mapping = qip.environ.fetch(
        python_target, mapping={"PYTHONWARNINGS": "ignore:DEPRECATION"}
    )

    # Fetch Python version mapping from environment
    python_mapping = qip.environ.fetch_python_mapping(environ_mapping)

    # Compute the installation path and add it to PYTHONPATH
    install_path = os.path.join(path, python_mapping["library-path"])
    environ_mapping["PYTHONPATH"] = install_path

    return {
        "environ": environ_mapping,
        "python": python_mapping
    }
