# :coding: utf-8

import functools
import os

import wiz
import wiz.environ
import wiz.exception
import wiz.symbol
import wiz.utility

import qip.logging

#: Common namespace for all :term:`Wiz` definition.
NAMESPACE = "library"


def export(
    path, mapping, output_path, editable_mode=False, definition_mapping=None
):
    """Export :term:`Wiz` definition to *path* for package *mapping*.

    :param path: destination path for the :term:`Wiz` definition.

    :param mapping: mapping of the python package built as returned by
        :func:`qip.package.install`.

    :param output_path: root destination path for Python packages installation.

    :param editable_mode: indicate whether the Python package location should
        target the source installation package. Default is False.

    :param definition_mapping: None or mapping regrouping all available
        definitions. Default is None.

    """
    # Retrieve definition from installation package path if possible.
    definition = qip.definition.retrieve(mapping)

    # Extract previous namespace or set default.
    namespace = definition.namespace if definition else NAMESPACE

    # Extract additional variants from existing definition if possible.
    additional_variants = None

    if definition_mapping is not None:
        try:
            _definition = wiz.fetch_definition(
                "{}::{}=={}".format(
                    namespace, mapping["key"], mapping["version"]
                ),
                definition_mapping
            )
            additional_variants = [v.data() for v in _definition.variants]
        except wiz.exception.RequestNotFound:
            pass

    # Update definition or create a new definition.
    if definition is not None:
        definition = qip.definition.update(
            definition, mapping, output_path,
            editable_mode=editable_mode,
            additional_variants=additional_variants,
        )

    else:
        definition = qip.definition.create(
            mapping, output_path,
            editable_mode=editable_mode,
            additional_variants=additional_variants
        )

    wiz.export_definition(path, definition, overwrite=True)


def retrieve(mapping):
    """Retrieve :term:`Wiz` definition from package *mapping* installed.

    Return the :term:`Wiz` definition extracted from a
    :file:`package_data/wiz.json` file found within the package installation
    *path*.

    :param mapping: mapping of the python package built as returned by
        :func:`qip.package.install`.

    :raise wiz.exception.WizError: if the :term:`Wiz` definition found is
        incorrect.

    :return: None if no definition was found, otherwise return the
        :class:`wiz.definition.Definition` instance.

    Example::

        >>> retrieve(mapping)
        Definition({
            "identifier": "foo"
            "definition-location": '/location/foo/package_data/wiz.json',
            ...
        })

    """
    logger = qip.logging.Logger(__name__ + ".retrieve")

    definition_path = os.path.join(
        mapping["location"], mapping["module_name"], "package_data", "wiz.json"
    )

    if os.path.exists(definition_path):
        definition = wiz.load_definition(definition_path)
        logger.info(
            "\tWiz definition extracted from '{}'.".format(
                mapping["identifier"]
            )
        )
        return definition


def create(mapping, output_path, editable_mode=False, additional_variants=None):
    """Create :term:`Wiz` definition for package *mapping*.

    :param mapping: mapping of the python package built as returned by
        :func:`qip.package.install`.

    :param output_path: root destination path for Python packages installation.

    :param editable_mode: indicate whether the Python package location should
        target the source installation package. Default is False.

    :param additional_variants: None or list of variant mappings that should be
        added to the definition created. Default is None.

    :return: :class:`wiz.definition.Definition` instance created.

    """
    logger = qip.logging.Logger(__name__ + ".create")

    definition_data = {
        "identifier": mapping["key"],
        "version": mapping["version"],
        "description": mapping["description"],
        "namespace": NAMESPACE,
        "environ": {
            "PYTHONPATH": "${{{}}}:${{PYTHONPATH}}".format(
                wiz.symbol.INSTALL_LOCATION
            )
        }
    }

    # Add commands mapping.
    if "command" in mapping.keys():
        definition_data["command"] = mapping["command"]

    # Add system constraint if necessary.
    if "system" in mapping.keys():
        definition_data["system"] = _process_system_mapping(mapping)

    # Target package location if the installation is in editable mode.
    location_path = mapping.get("location", "")

    if not editable_mode:
        definition_data["install-root"] = output_path
        location_path = os.path.join(
            "${{{}}}".format(wiz.symbol.INSTALL_ROOT), mapping["target"],
            mapping["python"]["library-path"]
        )

    # Update and set variant for python version.
    variants = []

    if additional_variants is not None:
        variants = sorted(
            additional_variants,
            key=functools.cmp_to_key(_compare_variants)
        )

    _update_variants(variants, mapping, location_path)

    definition_data["variants"] = variants

    definition = wiz.definition.Definition(definition_data)
    logger.info(
        "\tWiz definition created for '{}'.".format(mapping["identifier"])
    )
    return definition


def update(
    definition, mapping, output_path, editable_mode=False,
    additional_variants=None
):
    """Update *definition* with *mapping*.

    :param definition: :class:`wiz.definition.Definition` instance.

    :param mapping: mapping of the python package built as returned by
        :func:`qip.package.install`.

    :param output_path: root destination path for Python packages installation.

    :param editable_mode: indicate whether the Python package location should
        target the source installation package. Default is False.

    :param additional_variants: None or list of variant mappings that should be
        added to the definition updated. Default is None.

    :return: Updated :class:`wiz.definition.Definition` instance.

    """
    if not definition.description:
        definition = definition.set("description", mapping["description"])

    if not definition.version:
        definition = definition.set("version", mapping["version"])

    if not definition.namespace:
        definition = definition.set("namespace", NAMESPACE)

    if not definition.system and mapping.get("system"):
        definition = definition.set(
            "system", _process_system_mapping(mapping)
        )

    if mapping.get("command"):
        definition = definition.update("command", mapping["command"])

    # Update environ mapping
    environ_mapping = {
        "PYTHONPATH": "${{{}}}:${{PYTHONPATH}}".format(
            wiz.symbol.INSTALL_LOCATION
        )
    }

    python_path = definition.environ.get("PYTHONPATH")
    if python_path:
        environ_mapping["PYTHONPATH"] = wiz.environ.substitute(
            environ_mapping["PYTHONPATH"], {"PYTHONPATH": python_path}
        )

    definition = definition.update("environ", environ_mapping)

    # Target package location if the installation is in editable mode.
    package_path = mapping.get("location", "")

    if not editable_mode:
        definition = definition.set("install-root", output_path)
        package_path = os.path.join(
            "${{{}}}".format(wiz.symbol.INSTALL_ROOT), mapping["target"],
            mapping["python"]["library-path"]
        )

    variants = definition.variants

    if additional_variants is not None:
        variants = sorted(
            variants + additional_variants,
            key=functools.cmp_to_key(_compare_variants)
        )

    _update_variants(variants, mapping, package_path)

    return definition.set("variants", variants)


def _update_variants(variants, mapping, path):
    """Add variant corresponding to *identifier* to the *variant* list.

    Update existing variant if necessary or add new variant corresponding to the
    python version required. If a new variant is added, it will be inserted
    to the variant list so that the highest Python version is always first.

    :param variants: list of variant mappings to update.

    :param mapping: mapping of the python package built as returned by
        :func:`qip.package.install`.

    :param path: path where python package has been installed.

    :return: None.

    .. note::

        The *variants* list will be mutated.

    """
    identifier = mapping["python"]["identifier"]
    python_request = mapping["python"]["request"]

    # Process all requirements to detect duplication.
    requirements = _process_requirements(mapping, python_request)

    # Index of new variant if necessary.
    _index = 0

    for index, variant in enumerate(variants):
        if variant["identifier"] != identifier:

            # Update index for new variant.
            if _compare_variants({"identifier": identifier}, variant) > 0:
                _index = index + 1

            continue

        variant["install-location"] = path

        # Add requirements that are not already in the definition.
        variant.setdefault("requirements", [])
        variant["requirements"] += [
            req for req in requirements
            if not any(
                req.replace(" ", "") == _req.replace(" ", "")
                for _req in variant["requirements"]
            )
        ]

        del variants[index]
        variants.insert(index, variant)
        return

    # If no variant has been updated, create a new variant.
    variant = {
        "identifier": identifier,
        "install-location": path,
        "requirements": requirements
    }

    variants.insert(_index, variant)


def _compare_variants(variant1, variant2):
    """Compare identifier values from variant mappings.

    Both identifiers will be converted into a negative float if possible (e.g.
    "2.7" will become -2.7). If one or both identifiers cannot be converted, the
    string value  is kept.

    If both identifiers are of the same type:

    * Return -1 if *identifier2* if higher than *identifier1*.
    * Return 1 if *identifier1* if higher than *identifier2*.
    * Return 0 if *identifier1* if higher than *identifier2*.

    If only *identifier1* is converted into a negative float, -1 is returned.

    If only *identifier2* is converted into a negative float, 1 is returned.

    :param variant1: Variant reference mapping.

    :param variant2: Variant reference mapping to compare *variant1* with.

    :return: Numerical value following the rules above (-1, 1 or 0).

    """
    try:
        identifier1 = -float(variant1["identifier"])
    except ValueError:
        identifier1 = variant1["identifier"]

    try:
        identifier2 = -float(variant2["identifier"])
    except ValueError:
        identifier2 = variant2["identifier"]

    if type(identifier1) == type(identifier2):
        if identifier1 == identifier2:
            return 0
        return -1 if identifier1 < identifier2 else 1

    elif isinstance(identifier1, float):
        return -1
    return 1


def _process_system_mapping(mapping):
    """Compute 'system' keyword for the :term:`Wiz` definition from *mapping*.

    :param mapping: mapping of the python package built as returned by
        :func:`qip.package.install`.

    :return: system mapping.

    """
    major_version = mapping["system"]["os"]["major_version"]
    return {
        "platform": mapping["system"]["platform"],
        "arch": mapping["system"]["arch"],
        "os": (
            "{name} >= {min_version}, < {max_version}".format(
                name=mapping["system"]["os"]["name"],
                min_version=major_version,
                max_version=major_version + 1,
            )
        )
    }


def _process_requirements(mapping, python_request):
    """Compute 'requirements' keyword for the :term:`Wiz` definition.

    :param mapping: mapping of the python package built as returned by
        :func:`qip.package.install`.

    :param python_request: Python version requirement (e.g.
        "python >=2.7, <2.8")

    :return: requirements list.

    """
    requests = [python_request]

    # Add the library namespace for all requirements fetched.
    for request in mapping.get("requirements", []):
        request = "{}::{}".format(NAMESPACE, request)
        requirement = wiz.utility.get_requirement(request)
        requirement.extras = {mapping["python"]["identifier"]}
        requests.append(str(requirement))

    return requests
