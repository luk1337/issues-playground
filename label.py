#!/usr/bin/env python3
import json
import os
import re
from contextlib import suppress
from dataclasses import dataclass

import requests
from github import Auth, Github, GithubException


@dataclass
class IssueBody:
    device: str
    version: str
    date: str
    kernel: str
    baseband: str
    mods: str
    expected: str
    current: str
    solution: str
    reproduce: str
    directions: str

    def __init__(self, issue_body: json):
        self.device = issue_body['device']
        self.version = issue_body['version']
        self.date = issue_body['date']
        self.kernel = issue_body['kernel']
        self.baseband = issue_body['baseband']
        self.mods = issue_body['mods']
        self.expected = issue_body['expected']
        self.current = issue_body['current']
        self.solution = issue_body['solution']
        self.reproduce = issue_body['reproduce']
        self.directions = issue_body['directions']

        # Let's be friendly...
        if x := re.findall(r'^lineage-(\d+)\.(\d+)', self.version):
            # lineage-20.0.* -> lineage-20.0
            self.version = f'lineage-{".".join(x[0])}'
        elif x := re.findall(r'^lineage-(\d+)', self.version):
            # lineage-20.* -> lineage-20.0
            self.version = f'{x[0]}.0'
        elif x := re.findall(r'^(\d+)$', self.version):
            # 20 -> lineage-20.0
            self.version = f'lineage-{x[0]}.0'
        elif x := re.findall(r'^(\d+)\.(\d+)$', self.version):
            # 20.0 -> lineage-20.0
            self.version = f'lineage-{".".join(x[0])}'


def device_list() -> dict:
    ret = {}

    for line in requests.get(
            'https://raw.githubusercontent.com/LineageOS/hudson/main/lineage-build-targets',
            timeout=5,
    ).text.splitlines():
        if ' lineage-' in line:
            codename, _, version, _ = line.split()
            ret[codename] = version

    return ret


def issue_errors(issue: IssueBody) -> list:
    ret = []

    # Load supported devices list
    devices = device_list()

    if issue.device not in devices:
        ret.append(
            f'Device "{issue.device}" is not a valid device codename. Supported values are: {", ".join(devices.keys())}'
        )

    if device_version := devices.get(issue.device, None):
        if issue.version != device_version:
            ret.append(
                f'LineageOS version "{issue.version}" is not a valid LineageOS version. Supported value is: {device_version}'
            )

    if not re.findall(r'^\d{8}$', issue.date):
        ret.append(f'Build date "{issue.date}" is not a valid date. Valid date format is YYYYMMDD')

    return ret


def main() -> None:
    # Auth to GitHub
    github = Github(auth=Auth.Token(os.environ.get('GITHUB_TOKEN')))

    # Get repo and issue
    repo = github.get_repo(os.environ.get('GITHUB_REPOSITORY'))
    issue = repo.get_issue(number=int(os.environ.get('ISSUE_NUMBER')))

    # Don't touch already labeled issue
    if issue.get_labels().totalCount > 0:
        print('Labels count > 0, exiting.')
        return

    # Parse issue body
    issue_body = IssueBody(json.loads(os.environ.get('ISSUE_BODY')))

    # Close issue if there are any errors
    if errors := issue_errors(issue_body):
        issue.create_comment('\n'.join([
            "Hi! It appears you didn't read or follow the provided issue template.",
            "Please edit your issue to include the requested fields and follow the provided template, then reopen it.",
            "For more information please see https://wiki.lineageos.org/how-to/bugreport.",
            "",
            "Problems:",
            "",
            *[f'* {x}' for x in errors],
            "",
            "(this action was performed by a bot)",
        ]))
        issue.edit(state='closed')
        return

    # Label issue
    for label, color in [
        [f'device:{issue_body.device}', '0075ca'],
        [issue_body.version, '008672'],
    ]:
        with suppress(GithubException):
            repo.create_label(label, color)  # just in case
        issue.add_to_labels(repo.get_label(label))


if __name__ == "__main__":
    main()
