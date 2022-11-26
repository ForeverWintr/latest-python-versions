import datetime
import json
import os
import sys
from collections import defaultdict
from distutils.util import strtobool
from typing import NamedTuple

import requests
from packaging import version as semver

GHA_PYTHON_VERSIONS_URL = 'https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json'
EOL_PYTHON_VERSIONS_URL = 'https://endoflife.date/api/python.json'


class Platform(NamedTuple):
    name: str
    arch: str
    version: str = ''

    def __str__(self) -> str:
        name = self.name
        if self.version:
            name = f'{name}-{self.version}'
        return f'{name}-{self.arch}'


def get_platform_to_version(stable_versions: dict) -> dict:
    platform_to_version = defaultdict(set)
    for version_object in stable_versions:
        parsed_version = semver.parse(version_object['version'])

        for file_object in version_object['files']:
            p = Platform(
                name=file_object['platform'],
                version=file_object.get('platform_version', ''),
                arch=file_object['arch'],
            )
            platform_to_version[p].add(parsed_version)
    return platform_to_version


def main(min_version: str, max_version: str, include_prereleases: str) -> None:
    """
    Set a LATEST_PYTHON_VERSIONS environment variable, and a latest-python-versions output,
    containing the latest Python versions found within the specified bounds.

    :param min_version: The major.minor version lower bound or 'EOL'.
    :param max_version: The major.minor version upper bound or 'latest'.
    :param include_prereleases: Whether to include pre-releases. Defaults to false on an action level.
    """
    if min_version.upper() == 'EOL':
        future = datetime.date.today() + datetime.timedelta(3650)
        for release in requests.get(EOL_PYTHON_VERSIONS_URL).json():
            if (
                datetime.date.today() < datetime.date.fromisoformat(release['eol'])
                and datetime.date.fromisoformat(release['eol']) < future
            ):
                future = datetime.date.fromisoformat(release['eol'])
                min_version = semver.parse(release['cycle'])
    else:
        min_version = semver.parse(min_version)
    max_version = semver.parse(max_version) if max_version != 'latest' else semver.parse('4.0')
    parsed_include_prereleases = strtobool(include_prereleases) == 1

    stable_versions = requests.get(GHA_PYTHON_VERSIONS_URL).json()

    versions = {}
    platform_versions = get_platform_to_version(stable_versions)
    all_versions = sorted({v for versions in platform_versions.values() for v in versions}, reverse=True)
    for version in all_versions:

        if not parsed_include_prereleases:
            if version.is_prerelease:
                continue

        breakpoint()
        if (major_minor := semver.parse('.'.join(str(version).split('.')[:2]))) not in versions:
            if min_version <= major_minor <= max_version:
                versions[major_minor] = version

    breakpoint()

    version_json = json.dumps(list(versions.values()))

    with open(os.environ['GITHUB_ENV'], 'a') as f:
        f.write(f'LATEST_PYTHON_VERSIONS={version_json}')

    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f'latest-python-versions={version_json}')

    print(version_json)


if __name__ == '__main__':
    main(*sys.argv[1:])
