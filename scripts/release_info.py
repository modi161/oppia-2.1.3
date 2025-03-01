#!/usr/bin/env python
#
# Copyright 2014 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS-IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Script that simplifies releases by collecting various information.
Should be run from the oppia root dir.
"""
import collections
import os
import re
import subprocess
import sys

GIT_CMD_GET_CURRENT_VERSION = 'git describe --abbrev=0'
GIT_CMD_GET_LOGS_FORMAT_STRING = (
    'git log -z --no-color --pretty=format:"%H{0}%aN{0}%aE{0}%B" {1}..{2}')
GIT_CMD_DIFF_NAMES_ONLY_FORMAT_STRING = 'git diff --name-only %s %s'
GIT_CMD_SHOW_FORMAT_STRING = 'git show %s:feconf.py'
ISSUE_URL_FORMAT_STRING = 'https://github.com/oppia/oppia/issues/%s'
ISSUE_REGEX = re.compile(r'#(\d+)')
GROUP_SEP = '\x1D'
VERSION_RE_FORMAT_STRING = r'%s\s*=\s*(\d+|\.)+'
FECONF_VAR_NAMES = ['CURRENT_EXPLORATION_STATES_SCHEMA_VERSION',
                    'CURRENT_COLLECTION_SCHEMA_VERSION']

Log = collections.namedtuple('Log', ['sha1', 'author', 'email', 'message'])


class ChangedBranch(object):
    def __init__(self, new_branch):
        get_branch_cmd = 'git symbolic-ref -q --short HEAD'.split()
        self.old_branch = subprocess.check_output(get_branch_cmd).strip()
        self.new_branch = new_branch
        self.is_same_branch = self.old_branch == self.new_branch

    def __enter__(self):
        if not self.is_same_branch:
            try:
                subprocess.check_output(['git', 'checkout', self.new_branch])
            except subprocess.CalledProcessError:
                print ('\nCould not change to %s. This is most probably because'
                       ' you are in a dirty state' % self.new_branch)
                sys.exit(1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.is_same_branch:
            subprocess.check_output(['git', 'checkout', self.old_branch])


def _run_cmd(cmd_str):
    """Runs the command and returns the output.
    Raises subprocess.CalledProcessError upon failure.

    Args:
        cmd_str (str): The command string to execute

    Returns:
        (str): The output of the command.

    """
    return subprocess.check_output(cmd_str.split(' ')).strip()


def _gather_logs(start, stop='HEAD'):
    """Gathers the logs between the start and endpoint.

    Args:
        start (str): Tag, Branch or SHA1 of start point
        stop (str):  Tag, Branch or SHA1 of end point, defaults to HEAD

    Returns:
        list[Log]: List of Logs

    """
    get_logs_cmd = GIT_CMD_GET_LOGS_FORMAT_STRING.format(GROUP_SEP, start, stop)
    out = _run_cmd(get_logs_cmd).split('\x00')
    if len(out) == 1 and out[0] == '':
        return []
    else:
        return [Log(*line.strip().split(GROUP_SEP)) for line in out]


def _extract_issues(logs):
    """Extract references to issues out of a list of Logs

    Args:
        logs (list[Log]): List of Logs to parse

    Returns:
        set[str]: Set of found issues as links to Github

    """
    issues = ISSUE_REGEX.findall(' '.join([log.message for log in logs]))
    links = {ISSUE_URL_FORMAT_STRING % issue for issue in issues}
    return links


def _check_versions(current_release):
    """Checks if the versions for the exploration or collection schemas have
    changed.

    Args:
        current_release (str): The current release tag to diff against.

    Returns:
        Dictionary consisting of name --> boolean that indicates whether or not
            it has changed.
    """
    feconf_changed_version = {}
    git_show_cmd = (GIT_CMD_SHOW_FORMAT_STRING % current_release)
    old_feconf = _run_cmd(git_show_cmd)
    with open('feconf.py', 'r') as feconf:
        new_feconf = feconf.read()
    for variable in FECONF_VAR_NAMES:
        old_version = re.findall(VERSION_RE_FORMAT_STRING % variable,
                                 old_feconf)[0]
        new_version = re.findall(VERSION_RE_FORMAT_STRING % variable,
                                 new_feconf)[0]
        feconf_changed_version[variable] = old_version != new_version
    return feconf_changed_version


def _git_diff_names_only(left, right='HEAD'):
    """ Get names of changed files from git.

    Args:
        left (str): Lefthand timepoint
        right (str): rightand timepoint

    Returns:
        (list): List of files that are different between the two points.

    """
    diff_cmd = (GIT_CMD_DIFF_NAMES_ONLY_FORMAT_STRING % (left, right))
    return _run_cmd(diff_cmd).splitlines()


def _check_setup_scripts(base_release_tag, changed_only=True):
    """Check if setup scripts have changed.

    Args:
        base_release_tag (str): The current release tag to diff against.
        changed_only (bool): If set to False will return all tested files
            instead of just the changed ones.

    Returns:
        dict consisting of script --> boolean indicating whether or not it has
            changed (filtered by default to those that are modified).
    """
    setup_scripts = ['scripts/%s' % item for item in
                     ['setup.sh', 'setup_gae.sh', 'install_third_party.sh',
                      'install_third_party.py']]
    changed_files = _git_diff_names_only(base_release_tag)
    changes_dict = {script: script in changed_files for script in setup_scripts}
    if changed_only:
        return {name: status for name, status in changes_dict.items() if status}
    else:
        return changes_dict


def _check_storage_models(current_release):
    """Check if files in core/storage have changed and returns them.

    Args:
        current_release: The current release version

    Returns:
        (list): The changed files (if any)

    """
    diff_list = _git_diff_names_only(current_release)
    return [item for item in diff_list if item.startswith('core/storage')]


def main():
    """Collects necessary info and dumps it to disk."""
    with ChangedBranch('develop'):
        current_release = _run_cmd(GIT_CMD_GET_CURRENT_VERSION)
        logs = _gather_logs(current_release)
        issue_links = _extract_issues(logs)
        version_changes = _check_versions(current_release)
        setup_changes = _check_setup_scripts(current_release)
        storage_changes = _check_storage_models(current_release)

    summary_file = os.path.join(os.getcwd(), os.pardir, 'release_summary.md')
    with open(summary_file, 'w') as out:
        out.write('## Collected release information\n')
        out.write('\n### Feconf version changes:\n')
        for var, status in version_changes.items():
            out.write('* %s: %s\n' % (var, status))

        if setup_changes:
            out.write('\n### Changed setup scripts:\n')
            for var in setup_changes.keys():
                out.write('* %s\n' % var)

        if storage_changes:
            out.write('\n### Changed storage models:\n')
            for item in storage_changes:
                out.write('* %s\n' % item)

        out.write('\n### Authors:\n')
        # TODO: duplicate author handling due to email changes
        for name, email in sorted({(log.author, log.email) for log in logs}):
            out.write('%s <%s>  \n' % (name, email))

        out.write('\n### Commit History:\n')
        for name, title in [(log.author, log.message.split('\n\n')[0])
                            for log in logs]:
            out.write('%s: %s  \n' % (name, title))

        if issue_links:
            out.write('\n### Issues mentioned in commits:\n')
            for link in issue_links:
                out.write('* [%s](%s)\n' % (link, link))

    print 'Done. Summary file generated in ../release_summary.md'


if __name__ == '__main__':
    main()
