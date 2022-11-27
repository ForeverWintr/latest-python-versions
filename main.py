from __future__ import annotations

import datetime
import json
import os
import sys
import typing as tp
from collections import defaultdict
from distutils.util import strtobool

import requests
from packaging import version as semver

GHA_PYTHON_VERSIONS_URL = 'https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json'
EOL_PYTHON_VERSIONS_URL = 'https://endoflife.date/api/python.json'


class Platform(tp.NamedTuple):
    name: str
    arch: str
    version: str = ''

    def __str__(self) -> str:
        name = self.name
        if self.version:
            name = f'{name}-{self.version}'
        return f'{name}-{self.arch}'


def get_platform_to_version(
    stable_versions: list[dict],
    min_version: semver.Version,
    max_version: semver.Version,
    include_prereleases: bool,
) -> dict:
    platform_to_version = defaultdict(set)
    for version_object in stable_versions:
        version_str = version_object['version']
        parsed_version = semver.parse(version_str)
        major_minor = semver.parse('.'.join(version_str.split('.')[:2]))

        if not include_prereleases and parsed_version.is_prerelease:
            continue

        if major_minor > max_version or major_minor < min_version:
            continue

        for file_object in version_object['files']:
            p = Platform(
                name=file_object['platform'],
                version=file_object.get('platform_version', ''),
                arch=file_object['arch'],
            )
            platform_to_version[p].add(parsed_version)
    return platform_to_version


def latest_minor_versions(all_versions: tp.Iterable[semver.Version]) -> list[semver.Version]:
    '''Filter the given list of versions to include only the latest for each minor version. E.g.,
    [3.9.1, 3.9.2] is filtered to [3.9.2]
    '''
    latest_versions: dict[semver.Version, semver.Version] = {}
    for version in all_versions:
        major_minor = semver.parse('.'.join(str(version).split('.')[:2]))

        if not (current := latest_versions.get(major_minor)) or current < version:
            latest_versions[major_minor] = version

    return sorted(latest_versions.values(), reverse=True)


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

    platform_versions = get_platform_to_version(
        stable_versions,
        min_version=min_version,
        max_version=max_version,
        include_prereleases=parsed_include_prereleases,
    )
    semver_to_original = {semver.parse(v['version']): v['version'] for v in stable_versions}
    latest_versions = latest_minor_versions({v for versions in platform_versions.values() for v in versions})

    # latest_versions_per_platform = {k: latest_minor_versions(v) for k, v in platform_versions.items()}
    # pretty = {str(k): v for k, v in latest_versions_per_platform.items()}

    version_json = json.dumps([semver_to_original[v] for v in latest_versions])

    with open(os.environ['GITHUB_ENV'], 'a') as f:
        f.write(f'LATEST_PYTHON_VERSIONS={version_json}')

    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write(f'latest-python-versions={version_json}')

    print(version_json)


if __name__ == '__main__':
    main(*sys.argv[1:])
