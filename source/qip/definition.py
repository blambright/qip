import os

import wiz


def create(mapping, path):
    """Create :term:`Wiz` definition for package *mapping*.

    :param mapping: mapping of the python package built
    :param path: path to install the package definition to
    :returns: definition data

    """
    definition_data = {
        "identifier": mapping["key"],
        "version": mapping["version"]
    }

    if "description" in mapping.keys():
        definition_data["description"] = mapping["description"]

    if "system" in mapping.keys():
        major_version = mapping["system"]["os"]["major_version"]
        definition_data["system"] = {
            "platform": mapping["system"]["platform"],
            "arch": mapping["system"]["arch"],
            "os": (
                "{name} >= {min_version}, <{max_version}".format(
                    name=mapping["system"]["os"]["name"],
                    min_version=major_version,
                    max_version=major_version + 1,
                )
            )
        }

    if "requirements" in mapping.keys():
        definition_data["requirements"] = [
            _mapping["request"] for _mapping in mapping["requirements"]
        ]

    lib_path = os.path.join(path, "lib", "python2.7", "site-packages")
    if os.path.isdir(lib_path):
        definition_data.setdefault("environ", {})
        definition_data["environ"]["PYTHONPATH"] = (
            "{}:${{PYTHONPATH}}".format(
                os.path.join(
                    "${INSTALL_LOCATION}", "lib", "python2.7", "site-packages"
                )
            )
        )

    bin_path = os.path.join(path, "bin")
    if os.path.isdir(bin_path):
        definition_data.setdefault("environ", {})
        definition_data["environ"]["PATH"] = (
            "{}:${{PATH}}".format(os.path.join("${INSTALL_LOCATION}", "bin"))
        )

    return definition_data


def retrieve(mapping, path):
    """Retrieve :term:`Wiz` definition from package installed.

    :param mapping: mapping of the python package built
    :param path: path where the package was installed to
    :return: None if no definition was found, otherwise return the definition

    """

    definition_path = os.path.join(
        path, "share", "wiz", mapping["name"], "wiz.json"
    )
    if not os.path.exists(definition_path):
        return None

    return wiz.load_definition(definition_path)
