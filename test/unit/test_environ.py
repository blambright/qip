# :coding: utf-8

import os.path

import pytest
import wiz

import qip.environ
import qip.command


@pytest.fixture()
def mocked_os_isfile(mocker):
    """Return mocked 'wiz.resolve_context' function"""
    return mocker.patch.object(os.path, "isfile")


@pytest.fixture()
def mocked_wiz_resolve_context(mocker):
    """Return mocked 'wiz.resolve_context' function"""
    return mocker.patch.object(wiz, "resolve_context")


@pytest.fixture()
def mocked_command_execute(mocker):
    """Return mocked command execute."""
    return mocker.patch.object(qip.command, "execute")


def test_fetch_environ(mocked_wiz_resolve_context):
    """Fetch and return environment mapping."""
    mocked_wiz_resolve_context.return_value = {"environ": "__ENVIRON__"}

    environ = qip.environ.fetch("python==2.7.*")
    assert environ == "__ENVIRON__"

    mocked_wiz_resolve_context.assert_called_once_with(
        ["python==2.7.*"], environ_mapping={}
    )


def test_fetch_environ_with_mapping(mocked_wiz_resolve_context):
    """Fetch and return environment mapping with initial mapping."""
    mocked_wiz_resolve_context.return_value = {"environ": "__ENVIRON__"}

    environ = qip.environ.fetch("python==2.7.*", mapping="__INITIAL_MAPPING__")
    assert environ == "__ENVIRON__"

    mocked_wiz_resolve_context.assert_called_once_with(
        ["python==2.7.*"], environ_mapping="__INITIAL_MAPPING__"
    )


def test_fetch_environ_with_python_path(mocked_wiz_resolve_context):
    """Fetch and return environment mapping with python path."""
    mocked_wiz_resolve_context.return_value = {"environ": "__ENVIRON__"}

    environ = qip.environ.fetch("/bin/python")
    assert environ == {
        "PATH": "/bin:${PATH}"
    }

    mocked_wiz_resolve_context.assert_not_called()


def test_fetch_python_mapping(mocked_command_execute):
    """Fetch and return Python mapping."""
    mocked_command_execute.return_value = "{\"python\": \"__MAPPING__\"}"

    mapping = qip.environ.fetch_python_mapping("__ENVIRON__")
    assert mapping == {"python": "__MAPPING__"}


def test_fetch_python_mapping_error(mocked_command_execute):
    """Fail to fetch and return Python mapping."""
    mocked_command_execute.return_value = "{{{"

    with pytest.raises(RuntimeError):
        qip.environ.fetch_python_mapping("__ENVIRON__")
