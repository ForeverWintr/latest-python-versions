import json
import os
from pathlib import Path
from unittest import mock

import pytest
import responses
from packaging.version import Version

from main import (
    EOL_PYTHON_VERSIONS_URL,
    GHA_PYTHON_VERSIONS_URL,
    Platform,
    get_platform_to_version,
    latest_minor_versions,
    main,
)

data = [
    [('3.4', 'latest', 'false'), ['3.9.6', '3.8.11', '3.7.11', '3.6.14', '3.5.10', '3.4.10']],
    [('3.5', 'latest', 'false'), ['3.9.6', '3.8.11', '3.7.11', '3.6.14', '3.5.10']],
    [('3.5', '3.8', 'false'), ['3.8.11', '3.7.11', '3.6.14', '3.5.10']],
    [('3.5', '3.8', 'true'), ['3.8.11', '3.7.11', '3.6.14', '3.5.10']],
    [('3.5', 'latest', 'true'), ['3.10.0-rc.1', '3.9.6', '3.8.11', '3.7.11', '3.6.14', '3.5.10']],
    [('EOL', 'latest', 'true'), ['3.10.0-rc.1', '3.9.6', '3.8.11', '3.7.11']],
]


@pytest.fixture
def github_env(tmp_path):
    env_fp = tmp_path / 'env'
    output_fp = tmp_path / 'output'
    with mock.patch.dict(os.environ, {'GITHUB_ENV': str(env_fp), 'GITHUB_OUTPUT': str(output_fp)}):
        yield env_fp, output_fp


@responses.activate
@pytest.mark.parametrize('args, result', data)
def test_main_without_max_version(capsys, args, result, github_env):
    root_dir = Path(__file__).parent.parent
    with open(root_dir / 'versions.json') as f:
        responses.add(responses.Response(method='GET', url=GHA_PYTHON_VERSIONS_URL, json=json.load(f)))
    with open(root_dir / 'eol.json') as f:
        responses.add(responses.Response(method='GET', url=EOL_PYTHON_VERSIONS_URL, json=json.load(f)))
    main(*args)
    captured = capsys.readouterr()
    assert json.loads(captured.out) == result

    env, output = github_env
    result_json = json.dumps(result)
    assert env.read_text() == f'LATEST_PYTHON_VERSIONS={result_json}'
    assert output.read_text() == f'latest-python-versions={result_json}'


def test_get_platform_to_version():
    data = [
        {
            'version': '3.10.0-beta.2',
            'files': [
                {'arch': 'x64', 'platform': 'darwin'},
                {'arch': 'x64', 'platform': 'linux', 'platform_version': '20.04'},
                {'arch': 'x64', 'platform': 'win32'},
            ],
        },
        {
            'version': '3.6.7',
            'files': [
                {'arch': 'x64', 'platform': 'darwin'},
                {'arch': 'x64', 'platform': 'linux', 'platform_version': '20.04'},
                {'arch': 'x86', 'platform': 'win32'},
            ],
        },
    ]
    r = get_platform_to_version(data, min_version=Version('3.0'), max_version=Version('4.0'), include_prereleases=True)
    assert r == {
        Platform(name='darwin', arch='x64', version=''): {Version('3.6.7'), Version('3.10.0b2')},
        Platform(name='linux', arch='x64', version='20.04'): {Version('3.6.7'), Version('3.10.0b2')},
        Platform(name='win32', arch='x64', version=''): {Version('3.10.0b2')},
        Platform(name='win32', arch='x86', version=''): {Version('3.6.7')},
    }
    r = get_platform_to_version(data, min_version=Version('3.8'), max_version=Version('4.0'), include_prereleases=True)
    assert r == {
        Platform(name='darwin', arch='x64', version=''): {Version('3.10.0b2')},
        Platform(name='linux', arch='x64', version='20.04'): {Version('3.10.0b2')},
        Platform(name='win32', arch='x64', version=''): {Version('3.10.0b2')},
    }

    r = get_platform_to_version(data, min_version=Version('3.0'), max_version=Version('3.8'), include_prereleases=True)
    assert r == {
        Platform(name='darwin', arch='x64', version=''): {Version('3.6.7')},
        Platform(name='linux', arch='x64', version='20.04'): {Version('3.6.7')},
        Platform(name='win32', arch='x86', version=''): {Version('3.6.7')},
    }
    r = get_platform_to_version(data, min_version=Version('3.0'), max_version=Version('4.0'), include_prereleases=False)
    assert r == {
        Platform(name='darwin', arch='x64', version=''): {Version('3.6.7')},
        Platform(name='linux', arch='x64', version='20.04'): {Version('3.6.7')},
        Platform(name='win32', arch='x86', version=''): {Version('3.6.7')},
    }


def test_latest_minor_versions():
    assert latest_minor_versions([Version('3.5.1'), Version('3.5.2'), Version('3.5'), Version('3.6')]) == [
        Version('3.5.2'),
        Version('3.6'),
    ]
