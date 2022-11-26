import json
import os
from pathlib import Path
from unittest import mock

import pytest
import responses

from main import EOL_PYTHON_VERSIONS_URL, GHA_PYTHON_VERSIONS_URL, main

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

    print('run workflows')
    env, output = github_env
    result_json = json.dumps(result)
    assert env.read_text() == f'LATEST_PYTHON_VERSIONS={result_json}'
    assert output.read_text() == f'latest-python-versions={result_json}'
