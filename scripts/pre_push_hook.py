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

'''Pre-push hook that executes the Python/JS linters on all files that
deviate from develop.
(By providing the list of files to `scripts/pre_commit_linter.py`)
To install the hook manually simply execute this script from the oppia root dir
with the `--install` flag.
To bypass the validation upon `git push` use the following command:
`git push REMOTE BRANCH --no-verify`

This hook works only on Unix like systems as of now.
On Vagrant under Windows it will still copy the hook to the .git/hooks dir
but it will have no effect.
'''

# Pylint has issues with the import order of argparse.
# pylint: disable=wrong-import-order
import os
import sys
import subprocess
import collections
import pprint
import argparse
import shutil
# pylint: enable=wrong-import-order


GitRef = collections.namedtuple('GitRef', ['local_ref', 'local_sha1',
                                           'remote_ref', 'remote_sha1'])
FileDiff = collections.namedtuple('FileDiff', ['status', 'name'])

# git hash of /dev/null, refers to an 'empty' commit
GIT_NULL_COMMIT = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'


# caution, __file__ is here *OPPiA/.git/hooks* and not in *OPPIA/scripts*
FILE_DIR = os.path.abspath(os.path.dirname(__file__))
OPPIA_DIR = os.path.join(FILE_DIR, os.pardir, os.pardir)
SCRIPTS_DIR = os.path.join(OPPIA_DIR, 'scripts')
LINTER_SCRIPT = 'pre_commit_linter.py'
LINTER_FILE_FLAG = '--files'
PYTHON_CMD = 'python'
FRONTEND_TEST_SCRIPT = 'run_frontend_tests.sh'


def _start_subprocess_for_result(cmd):
    '''Starts subprocess and returns (stdout, stderr)'''
    task = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = task.communicate()
    return out, err


def _git_diff_name_status(left, right, diff_filter=''):
    '''Compare two branches/commits etc with git.
    Parameter:
        left: the lefthand comperator
        right: the righthand comperator
        diff_filter: arguments given to --diff-filter (ACMRTD...)
    Returns:
        List of FileDiffs (tuple with name/status)
    Raises:
        ValueError if git command fails
    '''
    git_cmd = ['git', 'diff', '--name-status']
    if diff_filter:
        git_cmd.append('--diff-filter={}'.format(diff_filter))
    git_cmd.extend([left, right])
    out, err = _start_subprocess_for_result(git_cmd)
    if not err:
        # 1st char is status, 2nd char is a tab, rest is filename
        file_list = [FileDiff(line[0], line[2:]) for line in out.splitlines()]
        return file_list
    else:
        raise ValueError(err)


def _compare_to_remote(remote, local_branch, remote_branch=None):
    '''Compare local with remote branch with git diff.
    Parameter:
        remote: Git remote being pushed to
        local_branch: Git branch being pushed to
        remote_branch: The branch on the remote to test against. If None same
            as local branch.
    Returns:
        List of file names that are modified, changed, renamed or added
        but not deleted
    Raises:
        ValueError if git command fails
    '''
    remote_branch = remote_branch if remote_branch else local_branch
    git_remote = '%s/%s' % (remote, remote_branch)
    return _git_diff_name_status(git_remote, local_branch)


def _extract_files_to_lint(file_diffs):
    '''Grab only files out of a list of FileDiffs that have a ACMRT status'''
    if not file_diffs:
        return []
    lint_files = [f.name for f in file_diffs
                  if f.status.upper() in 'ACMRT']
    return lint_files


def _collect_files_being_pushed(ref_list, remote):
    '''Collect modified files and filter those that need linting.
    Parameter:
        ref_list: list of references to parse (provided by git in stdin)
        remote: the remote being pushed to
    Returns:
        Tuple of lists of changed_files, files_to_lint
    '''
    if not ref_list:
        return [], []
    # get branch name from e.g. local_ref='refs/heads/lint_hook'
    branches = [ref.local_ref.split('/')[-1] for ref in ref_list]
    hashes = [ref.local_sha1 for ref in ref_list]
    remote_hashes = [ref.remote_sha1 for ref in ref_list]
    modified_files = set()
    files_to_lint = set()
    for branch, sha1, remote_sha1 in zip(branches, hashes, remote_hashes):
        # git reports the following for an empty / non existing branch
        # sha1: '0000000000000000000000000000000000000000'
        if set(sha1) == {'0'}:
            # We are deleting a branch, nothing to do
            continue
        elif set(remote_sha1) != {'0'}:
            try:
                file_diffs = _compare_to_remote(remote, branch)
            except ValueError as e:
                print e.message
                sys.exit(1)
            else:
                modified_files.update(file_diffs)
                files_to_lint.update(_extract_files_to_lint(modified_files))
        else:
            # Get the difference to origin/develop instead
            try:
                file_diffs = _compare_to_remote(remote, branch,
                                                remote_branch='develop')
            except ValueError:
                # give up, return all files in repo
                try:
                    files = _git_diff_name_status(GIT_NULL_COMMIT, sha1)
                except ValueError as e:
                    print e.message
                    sys.exit(1)
                else:
                    modified_files.update(files)
                    files_to_lint.update(_extract_files_to_lint(files))
            else:
                modified_files.update(file_diffs)
                files_to_lint.update(_extract_files_to_lint(modified_files))

    if modified_files:
        print '\nModified files:'
        pprint.pprint(modified_files)
        print '\nFiles to lint:'
        pprint.pprint(files_to_lint)
        modified_files = [f.name for f in modified_files]
    else:
        modified_files = []
    return modified_files, list(files_to_lint)


def _get_refs():
    # Git provides refs in STDIN
    ref_list = [GitRef(*ref_str.split()) for ref_str in sys.stdin]
    if ref_list:
        print 'ref_list:'
        pprint.pprint(ref_list)
    return ref_list


def _start_linter(files):
    script = os.path.join(SCRIPTS_DIR, LINTER_SCRIPT)
    task = subprocess.Popen([PYTHON_CMD, script, LINTER_FILE_FLAG] + files)
    task.communicate()
    return task.returncode


def _start_sh_script(scriptname):
    cmd = ['bash', os.path.join(SCRIPTS_DIR, scriptname)]
    task = subprocess.Popen(cmd)
    task.communicate()
    return task.returncode


def _install_hook():
    # install script ensures that oppia is root
    oppia_dir = os.getcwd()
    hooks_dir = os.path.join(oppia_dir, '.git', 'hooks')
    pre_push_file = os.path.join(hooks_dir, 'pre-push')
    if os.path.islink(pre_push_file):
        print 'Symlink already exists'
        return
    try:
        os.symlink(os.path.abspath(__file__), pre_push_file)
        print 'Created symlink in .git/hooks directory'
    # raises AttributeError on windows, OSError added as failsafe
    except (OSError, AttributeError):
        shutil.copy(__file__, pre_push_file)
        print 'Copied file to .git/hooks directory'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('remote', nargs='?', help='provided by git before push')
    parser.add_argument('url', nargs='?', help='provided by git before push')
    parser.add_argument('--install', action='store_true', default=False,
                        help='Install pre_push_hook to the .git/hooks dir')
    args = parser.parse_args()
    remote = args.remote
    if args.install:
        _install_hook()
        sys.exit(0)
    refs = _get_refs()
    modified_files, files_to_lint = _collect_files_being_pushed(refs, remote)
    if not modified_files and not files_to_lint:
        sys.exit(0)
    if files_to_lint:
        lint_status = _start_linter(files_to_lint)
        if lint_status != 0:
            print 'Push failed, please correct the linting issues above'
            sys.exit(1)
    frontend_status = _start_sh_script(FRONTEND_TEST_SCRIPT)
    if frontend_status != 0:
        print 'Push aborted due to failing frontend tests.'
        sys.exit(1)


if __name__ == '__main__':
    main()
