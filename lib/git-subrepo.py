#!/usr/bin/env python3
"""
git-subrepo - Git Submodule Alternative

Copyright 2026 - Thorsten Klein <thorsten.klein.git@gmail.com>

Python implementation of git-subrepo
"""

import sys
import os
import subprocess
import argparse
import re
import shlex
import shutil
import textwrap
from typing import Optional, List
from dataclasses import dataclass

VERSION = "0.4.9"
REQUIRED_GIT_VERSION = "2.23.0"
EMPTY_TREE_SHA = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
GITREPO_HEADER = textwrap.dedent("""\
    ; DO NOT EDIT (unless you know what you are doing)
    ;
    ; This subdirectory is a git "subrepo", and this file is maintained by the
    ; git-subrepo command. See https://github.com/ingydotnet/git-subrepo#readme
    ;
    """)

os.environ['FILTER_BRANCH_SQUELCH_WARNING'] = '1'


class GitSubrepoError(Exception):
    """Base exception for git-subrepo errors"""

    def __init__(self, message, code=1):
        self.message = message
        self.code = code
        super().__init__(self.message)


@dataclass
class Flags:
    """Command-line flags"""

    all: bool = False
    ALL: bool = False
    force: bool = False
    fetch: bool = False
    squash: bool = False
    update: bool = False
    quiet: bool = False
    verbose: bool = False
    debug: bool = False
    edit: bool = False


@dataclass
class SubrepoConfig:
    """Subrepo configuration from .gitrepo file"""

    remote: str = ''
    branch: str = ''
    commit: str = ''
    parent: str = ''
    former: str = ''
    method: str = 'merge'

    @classmethod
    def from_file(cls, filepath: str, git_runner):
        """Read config from .gitrepo file"""
        if not os.path.isfile(filepath):
            raise GitSubrepoError(f"No '{filepath}' file.")

        config = cls()
        config.remote = git_runner.config_get(filepath, 'subrepo.remote', required=True)
        config.branch = git_runner.config_get(filepath, 'subrepo.branch', required=True)
        config.commit = git_runner.config_get(filepath, 'subrepo.commit', default='')
        config.parent = git_runner.config_get(filepath, 'subrepo.parent', default='')
        method = git_runner.config_get(filepath, 'subrepo.method', default='merge')
        config.method = 'rebase' if method == 'rebase' else 'merge'

        if not config.parent:
            config.former = git_runner.config_get(
                filepath, 'subrepo.former', default=''
            )

        return config


class GitRunner:
    """Simplified git command execution"""

    def __init__(self, verbose=False, debug=False, quiet=False):
        self.verbose = verbose
        self.debug = debug
        self.quiet = quiet

    def run(
        self, args: List[str], capture=False, fail=True, check=False, show=False
    ) -> Optional[str]:
        """Run git command"""
        cmd = ['git'] + args
        if self.debug:
            self.log(f">>> {' '.join(cmd)}")

        try:
            if capture or check:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, check=False
                )
                if result.returncode != 0 and fail:
                    raise GitSubrepoError(
                        f"Command failed: '{' '.join(cmd)}'.\n{result.stderr}"
                    )
                return result.stdout.strip() if check else result.stdout
            elif show:
                result = subprocess.run(cmd, check=False)
                if result.returncode != 0 and fail:
                    raise GitSubrepoError(f"Command failed: '{' '.join(cmd)}'.")
                return None
            else:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, check=False
                )
                if result.returncode != 0 and fail:
                    raise GitSubrepoError(
                        f"Command failed: '{' '.join(cmd)}'.\n{result.stderr}"
                    )
                return None
        except Exception as e:
            if fail:
                raise GitSubrepoError(f"Command failed: '{' '.join(cmd)}'.\n{str(e)}")
            return None

    def config_get(self, filepath: str, key: str, required=False, default='') -> str:
        """Get value from config file"""
        try:
            result = self.run(
                ['config', f'--file={filepath}', key], capture=True, fail=required
            )
            return result.strip() if result else default
        except GitSubrepoError:
            if required:
                raise
            return default

    def config_set(self, filepath: str, key: str, value: str):
        """Set value in config file"""
        self.run(['config', f'--file={filepath}', key, value])

    def rev_exists(self, rev: str) -> bool:
        """Check if revision exists"""
        if not rev:
            return False
        result = subprocess.run(['git', 'rev-list', rev, '-1'], capture_output=True)
        return result.returncode == 0

    def branch_exists(self, branch: str) -> bool:
        """Check if branch exists"""
        return self.rev_exists(f'refs/heads/{branch}')

    def commit_in_rev_list(self, commit: str, list_head: str) -> bool:
        """Check if commit is in rev-list (i.e., is an ancestor)"""
        if not commit:
            return False
        result = subprocess.run(
            ['git', 'merge-base', '--is-ancestor', commit, list_head],
            capture_output=True,
        )
        return result.returncode == 0

    def log(self, msg: str):
        """Print verbose/debug message"""
        if self.verbose:
            print(f"* {msg}")

    def say(self, msg: str):
        """Print message unless quiet"""
        if not self.quiet:
            print(msg)


class GitSubrepo:
    """Main git-subrepo implementation"""

    def __init__(self):
        self.command = None
        self.args = []
        self.flags = Flags()
        self.git = GitRunner()

        # Paths and state
        self.subdir = None
        self.subref = None
        self.gitrepo = None
        self.worktree = None
        self.start_pwd = os.getcwd()
        self.git_tmp = None

        # Commit tracking
        self.original_head_commit = None
        self.original_head_branch = None
        self.upstream_head_commit = None
        self.subrepo_commit_ref = None

        # Subrepo config
        self.config = None
        self.override_remote = None
        self.override_branch = None
        self.join_method = None

        # Commit message
        self.commit_message = None
        self.commit_msg_file = None
        self.commit_msg_args = []

        # Result tracking
        self.ok = True
        self.code = 0

        # Git version
        self.git_version = None

    def main(self, args):
        """Main entry point"""
        # Check environment flags
        for env_var, flag_attr in [
            ('GIT_SUBREPO_QUIET', 'quiet'),
            ('GIT_SUBREPO_VERBOSE', 'verbose'),
            ('GIT_SUBREPO_DEBUG', 'debug'),
        ]:
            if os.getenv(env_var):
                setattr(self.flags, flag_attr, True)

        self.parse_args(args)
        self.check_environment()
        self.check_repository()
        self.init_command()

        # Handle --all flag
        if self.flags.all and self.command not in ['help', 'status']:
            if self.override_branch:
                self.error("options --branch and --all are not compatible")

            subrepos = self.find_all_subrepos()
            saved_args = self.args[:]
            for subdir in subrepos:
                self.prepare_command()
                self.override_remote = None
                self.override_branch = None
                self.args = [subdir] + saved_args
                self.dispatch_command()
        else:
            self.prepare_command()
            self.dispatch_command()

    def parse_args(self, args):
        """Parse command line arguments"""
        # Reorder args: options first, then positionals
        options, positionals = [], []
        i, seen_sep = 0, False
        value_opts = [
            '-b',
            '--branch',
            '-M',
            '--method',
            '-m',
            '--message',
            '--file',
            '-r',
            '--remote',
        ]

        while i < len(args):
            arg = args[i]
            if arg == '--':
                seen_sep = True
                positionals.append(arg)
            elif seen_sep or not arg.startswith('-'):
                positionals.append(arg)
            else:
                options.append(arg)
                if arg in value_opts and i + 1 < len(args):
                    i += 1
                    options.append(args[i])
            i += 1

        parser = self._create_parser()
        try:
            parsed = parser.parse_args(options + positionals)
        except argparse.ArgumentError as e:
            msg = str(e.message) if hasattr(e, 'message') else str(e)
            if 'unrecognized arguments:' in msg:
                arg = msg.split('unrecognized arguments:')[1].strip()
                msg = f"error: unknown option `{arg.lstrip('-')}"
            self.usage_error(msg)

        if parsed.version:
            print(VERSION)
            sys.exit(0)

        # Set flags
        for flag in [
            'all_flag',
            'ALL_flag',
            'force',
            'fetch_flag',
            'squash',
            'update',
            'quiet',
            'verbose',
            'debug',
            'edit',
        ]:
            flag_name = flag.replace('_flag', '') if flag.endswith('_flag') else flag
            if flag == 'all_flag':
                flag_name = 'all'
            elif flag == 'ALL_flag':
                flag_name = 'ALL'
            elif flag == 'fetch_flag':
                flag_name = 'fetch'
            setattr(self.flags, flag_name, getattr(parsed, flag, False) or False)

        if self.flags.ALL:
            self.flags.all = True

        # Update git runner flags
        self.git.verbose = self.flags.verbose
        self.git.debug = self.flags.debug
        self.git.quiet = self.flags.quiet

        # Set options
        if parsed.branch:
            self.override_branch = parsed.branch
            self.commit_msg_args.append(f'--branch={parsed.branch}')
        if parsed.remote:
            self.override_remote = parsed.remote
            self.commit_msg_args.append(f'--remote={parsed.remote}')
        if parsed.force:
            self.commit_msg_args.append('--force')
        if parsed.update:
            self.commit_msg_args.append('--update')
        if parsed.method:
            self.join_method = parsed.method
        if parsed.message:
            if parsed.msg_file:
                self.error("fatal: options '-m' and '--file' cannot be used together")
            self.commit_message = parsed.message
        if parsed.msg_file:
            if parsed.message:
                self.error("fatal: options '-m' and '--file' cannot be used together")
            if not os.path.isfile(parsed.msg_file):
                self.error(f"Commit msg file at {parsed.msg_file} not found")
            self.commit_msg_file = parsed.msg_file

        # Handle help
        if parsed.help_flag and not parsed.command:
            self.command = 'help'
            self.args = []
            return

        # Set command
        self.command = parsed.command
        if not self.command:
            self.usage_error("No command specified. See 'git subrepo help'.")

        valid_commands = [
            'clone',
            'init',
            'pull',
            'push',
            'fetch',
            'branch',
            'commit',
            'status',
            'clean',
            'config',
            'help',
            'version',
            'upgrade',
        ]
        if self.command not in valid_commands:
            self.usage_error(
                f"'{self.command}' is not a command. See 'git subrepo help'."
            )

        self.args = parsed.arguments or []
        if self.args:
            self.args[0] = self.args[0].rstrip('/')
        self.commit_msg_args.extend(self.args)

        self.validate_options()

        if self.flags.update and not (self.override_branch or self.override_remote):
            self.usage_error("Can't use '--update' without '--branch' or '--remote'.")

    def _create_parser(self):
        """Create argument parser"""

        class CustomArgumentParser(argparse.ArgumentParser):
            def error(self, message):
                raise argparse.ArgumentError(None, message)

        parser = CustomArgumentParser(prog='git subrepo', add_help=False)
        parser.add_argument('-h', '--help', action='store_true', dest='help_flag')
        parser.add_argument('--version', action='store_true')
        parser.add_argument('-a', '--all', action='store_true', dest='all_flag')
        parser.add_argument('-A', '--ALL', action='store_true', dest='ALL_flag')
        parser.add_argument('-b', '--branch', dest='branch')
        parser.add_argument('-e', '--edit', action='store_true')
        parser.add_argument('-f', '--force', action='store_true')
        parser.add_argument('-F', '--fetch', action='store_true', dest='fetch_flag')
        parser.add_argument('-M', '--method', dest='method')
        parser.add_argument('-m', '--message', dest='message')
        parser.add_argument('--file', dest='msg_file')
        parser.add_argument('-r', '--remote', dest='remote')
        parser.add_argument('-s', '--squash', action='store_true')
        parser.add_argument('-u', '--update', action='store_true')
        parser.add_argument('-q', '--quiet', action='store_true')
        parser.add_argument('-v', '--verbose', action='store_true')
        parser.add_argument('-d', '--debug', action='store_true')
        parser.add_argument('-x', '--DEBUG', action='store_true')
        parser.add_argument('command', nargs='?')
        parser.add_argument('arguments', nargs='*')
        return parser

    def validate_options(self):
        """Validate options for command"""
        valid_opts = {
            'help': ['all'],
            'branch': ['all', 'fetch', 'force'],
            'clean': ['ALL', 'all', 'force'],
            'clone': ['branch', 'edit', 'force', 'message', 'method'],
            'config': ['force'],
            'commit': ['edit', 'fetch', 'force', 'message'],
            'fetch': ['all', 'branch', 'force', 'remote'],
            'init': ['branch', 'remote', 'method'],
            'pull': ['all', 'branch', 'edit', 'force', 'message', 'remote', 'update'],
            'push': ['all', 'branch', 'force', 'message', 'remote', 'squash', 'update'],
            'status': ['ALL', 'all', 'fetch'],
        }

        opts = valid_opts.get(self.command, [])
        checks = [
            ('all', self.flags.all),
            ('ALL', self.flags.ALL),
            ('edit', self.flags.edit),
            ('fetch', self.flags.fetch),
            ('force', self.flags.force),
            ('squash', self.flags.squash),
            ('branch', self.override_branch is not None),
            ('remote', self.override_remote is not None),
            ('message', self.commit_message or self.commit_msg_file),
            ('update', self.flags.update),
        ]

        for opt, is_set in checks:
            if is_set and opt not in opts:
                self.usage_error(f"Invalid option '--{opt}' for '{self.command}'.")

    def dispatch_command(self):
        """Dispatch to command function"""
        commands = {
            'clone': self.cmd_clone,
            'init': self.cmd_init,
            'pull': self.cmd_pull,
            'push': self.cmd_push,
            'fetch': self.cmd_fetch,
            'branch': self.cmd_branch,
            'commit': self.cmd_commit,
            'status': self.cmd_status,
            'clean': self.cmd_clean,
            'config': self.cmd_config,
            'help': self.cmd_help,
            'version': self.cmd_version,
            'upgrade': self.cmd_upgrade,
        }

        func = commands.get(self.command)
        if func:
            try:
                func()
            except GitSubrepoError as e:
                if e.code != 0:
                    sys.exit(e.code)
        else:
            self.usage_error(f"Unknown command: {self.command}")

    # ===== Commands =====

    def cmd_clone(self):
        """Clone a remote repository into a local subdirectory"""
        self.setup_command(['+subrepo_remote', 'subdir:guess_subdir'])

        up_to_date = self.do_clone()
        if up_to_date:
            self.git.say(f"Subrepo '{self.subdir}' is up to date.")
            return

        prefix = 're' if self.flags.force else ''
        self.git.say(
            f"Subrepo '{self.config.remote}' ({self.config.branch}) {prefix}cloned into '{self.subdir}'."
        )

    def cmd_init(self):
        """Initialize a subdirectory as a subrepo"""
        self.setup_command(['+subdir'])

        default_branch = self.get_default_branch()
        if not self.config.remote:
            self.config.remote = 'none'
        if not self.config.branch:
            self.config.branch = default_branch

        self.do_init()

        if self.ok:
            msg = f"Subrepo created from '{self.subdir}' "
            msg += (
                "(with no remote)."
                if self.config.remote == 'none'
                else f"with remote '{self.config.remote}' ({self.config.branch})."
            )
            self.git.say(msg)
        else:
            self.error(f"Unknown init error code: '{self.code}'")

    def cmd_pull(self):
        """Pull upstream changes to the subrepo"""
        self.setup_command(['+subdir'])
        self.do_pull()

        if self.ok:
            self.git.say(
                f"Subrepo '{self.subdir}' pulled from '{self.config.remote}' ({self.config.branch})."
            )
        elif self.code == -1:
            self.git.say(f"Subrepo '{self.subdir}' is up to date.")
        elif self.code == 1:
            self.print_join_error()
            sys.exit(self.code)
        else:
            self.error(f"Unknown pull error code: '{self.code}'")

    def cmd_push(self):
        """Push local subrepo changes upstream"""
        self.setup_command(['+subdir', 'branch'])
        self.do_push()

        if self.ok:
            self.git.say(
                f"Subrepo '{self.subdir}' pushed to '{self.config.remote}' ({self.config.branch})."
            )
        elif self.code == -2:
            self.git.say(f"Subrepo '{self.subdir}' has no new commits to push.")
        elif self.code == 1:
            self.print_join_error()
            sys.exit(self.code)
        else:
            self.error(f"Unknown push error code: '{self.code}'")

    def cmd_fetch(self):
        """Fetch a subrepo's remote branch"""
        self.setup_command(['+subdir'])

        if self.config.remote == 'none':
            self.git.say(f"Ignored '{self.subdir}', no remote.")
        else:
            self.do_fetch()
            self.git.say(
                f"Fetched '{self.subdir}' from '{self.config.remote}' ({self.config.branch})."
            )

    def cmd_branch(self):
        """Create a branch containing the local subrepo commits"""
        self.setup_command(['+subdir'])

        if self.flags.fetch:
            self.do_fetch()

        branch = f'subrepo/{self.subref}'
        if self.flags.force:
            self.worktree = os.path.join(self.git_tmp, branch)
            self.delete_branch(branch)

        if self.git.branch_exists(branch):
            self.error(f"Branch '{branch}' already exists. Use '--force' to override.")

        self.create_subrepo_branch()
        self.git.say(f"Created branch '{branch}' and worktree '{self.worktree}'.")

    def cmd_commit(self):
        """Commit a merged subrepo branch"""
        self.setup_command(['+subdir', 'subrepo_commit_ref'])

        if self.flags.fetch:
            self.do_fetch()

        refs_fetch = f'refs/subrepo/{self.subref}/fetch'
        if not self.git.rev_exists(refs_fetch):
            self.error(f"Can't find ref '{refs_fetch}'. Try using -F.")

        self.upstream_head_commit = self.git.run(['rev-parse', refs_fetch], check=True)

        if not hasattr(self, 'subrepo_commit_ref') or not self.subrepo_commit_ref:
            self.subrepo_commit_ref = f'subrepo/{self.subref}'

        self.commit_subrepo_branch()
        self.git.say(f"Subrepo commit '{self.subrepo_commit_ref}' committed as")
        self.git.say(
            f"subdir '{self.subdir}/' to branch '{self.original_head_branch}'."
        )

    def cmd_status(self):
        """Get status of a subrepo (or all of them)"""
        output = self.get_status()
        pager = os.getenv('GIT_SUBREPO_PAGER') or os.getenv('PAGER') or 'less -FRX'
        if pager == 'less':
            pager = 'less -FRX'

        try:
            proc = subprocess.Popen(
                shlex.split(pager), stdin=subprocess.PIPE, text=True
            )
            proc.communicate(output)
        except (BrokenPipeError, OSError):
            print(output)

    def cmd_clean(self):
        """Remove branches, remotes and refs for a subrepo"""
        self.setup_command(['+subdir'])
        items = self.do_clean()
        for item in items:
            self.git.say(f"Removed {item}.")

    def cmd_config(self):
        """Get/set subrepo configuration"""
        self.setup_command(['+subdir', '+config_option', 'config_value'])

        self.git.log(
            f"Update '{self.subdir}' configuration with {self.config_option}={getattr(self, 'config_value', '')}"
        )

        valid = ['branch', 'cmdver', 'commit', 'method', 'remote', 'version']
        if self.config_option not in valid:
            self.error(f"Option {self.config_option} not recognized")

        if not hasattr(self, 'config_value') or not self.config_value:
            value = self.git.config_get(
                self.gitrepo, f'subrepo.{self.config_option}', required=True
            )
            self.git.say(
                f"Subrepo '{self.subdir}' option '{self.config_option}' has value '{value}'."
            )
            return

        if not self.flags.force and self.config_option != 'method':
            self.error("This option is autogenerated, use '--force' to override.")

        if self.config_option == 'method' and self.config_value not in [
            'merge',
            'rebase',
        ]:
            self.error("Not a valid method. Valid options are 'merge' or 'rebase'.")

        self.git.config_set(
            self.gitrepo, f'subrepo.{self.config_option}', self.config_value
        )
        self.git.say(
            f"Subrepo '{self.subdir}' option '{self.config_option}' set to '{self.config_value}'."
        )

    def cmd_help(self):
        """Show help documentation"""
        print(
            textwrap.dedent("""
            git subrepo - Git Submodule Alternative

            Commands:
              clone     Clone a remote repository into a local subdirectory
              init      Turn a current subdirectory into a subrepo
              pull      Pull upstream changes to the subrepo
              push      Push local subrepo changes upstream
              fetch     Fetch a subrepo's remote branch (and create a ref for it)
              branch    Create a branch containing the local subrepo commits
              commit    Commit a merged subrepo branch into the mainline
              status    Get status of a subrepo (or all of them)
              clean     Remove branches, remotes and refs for a subrepo
              config    Set subrepo configuration properties
              help      Documentation for git-subrepo
              version   Display git-subrepo version info
              upgrade   Upgrade the git-subrepo software itself

            See 'git help subrepo' for complete documentation.
            """)
        )

    def cmd_version(self):
        """Print version information"""
        print(f"git-subrepo Version: {VERSION}")
        print("Copyright 2013-2020 Ingy döt Net")
        print("https://github.com/ingydotnet/git-subrepo")
        print(os.path.abspath(__file__))
        print(f"Git Version: {self.git_version}")

    def cmd_upgrade(self):
        """Upgrade git-subrepo installation"""
        print("The upgrade command is not implemented for the Python version.")
        print("Please update your git-subrepo installation manually.")

    # ===== Worker Functions =====

    def do_clone(self) -> bool:
        """Clone implementation"""
        # Check if we can clone
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True)
        if result.returncode != 0:
            self.error("You can't clone into an empty repository")

        # Turn off force unless really a reclone
        if self.flags.force and not os.path.isfile(self.gitrepo):
            self.flags.force = False

        if self.flags.force:
            self.git.log("--force indicates a reclone.")
            self.do_fetch()
            if os.path.isfile(self.gitrepo):
                self.read_config()
            self.git.log("Check if we already are up to date.")
            if self.upstream_head_commit == self.config.commit:
                return True

            self.git.log("Remove the old subdir.")
            self.git.run(['rm', '-r', '--', self.subdir])

            if not self.override_branch:
                self.git.log("Determine the upstream head branch.")
                self.config.branch = self.get_upstream_branch()
                self.override_branch = self.config.branch
        else:
            self.check_subdir_empty()
            if not self.config.branch:
                self.git.log("Determine the upstream head branch.")
                self.config.branch = self.get_upstream_branch()

            self.do_fetch()

        self.git.log(f"Make the directory '{self.subdir}/' for the clone.")
        os.makedirs(self.subdir, exist_ok=True)

        self.git.log(f"Commit the new '{self.subdir}/' content.")
        self.subrepo_commit_ref = self.upstream_head_commit
        self.commit_subrepo_branch()

        return False

    def do_init(self):
        """Initialize a subrepo"""
        self.check_subdir_for_init()
        self.subrepo_commit_ref = self.original_head_commit

        self.git.log(f"Put info into '{self.subdir}/.gitrepo' file.")
        self.update_gitrepo_file()

        self.git.log(f"Add the new '{self.subdir}/.gitrepo' file.")
        self.git.run(['add', '-f', '--', self.gitrepo])

        self.git.log(f"Commit new subrepo to the '{self.original_head_branch}' branch.")
        msg = self.build_commit_message()
        self.git.run(['commit', '-m', msg])

        self.git.log(f"Create ref 'refs/subrepo/{self.subref}/commit'.")
        self.make_ref(f'refs/subrepo/{self.subref}/commit', self.subrepo_commit_ref)

    def do_pull(self):
        """Pull implementation"""
        self.do_fetch()

        if self.flags.force:
            self.do_clone()
            return

        if self.upstream_head_commit == self.config.commit and not self.flags.update:
            self.ok = False
            self.code = -1
            return

        branch = f'subrepo/{self.subref}'
        self.delete_branch(branch)
        self.subrepo_commit_ref = branch

        self.git.log(f"Create subrepo branch '{branch}'.")
        self.create_subrepo_branch(branch)

        os.chdir(self.worktree)

        method = self.join_method or self.config.method
        refs_fetch = f'refs/subrepo/{self.subref}/fetch'

        if method == 'rebase':
            self.git.log(f"Rebase changes to {refs_fetch}")
            result = subprocess.run(
                ['git', 'rebase', refs_fetch, branch], capture_output=True, text=True
            )
            if result.returncode != 0:
                self.git.say("The \"git rebase\" command failed:")
                self.git.say("")
                self.git.say("  " + result.stdout.replace('\n', '\n  '))
                self.ok = False
                self.code = 1
                return
        else:
            self.git.log(f"Merge in changes from {refs_fetch}")
            result = subprocess.run(
                ['git', 'merge', refs_fetch], capture_output=True, text=True
            )
            if result.returncode != 0:
                self.git.say("The \"git merge\" command failed:")
                self.git.say("")
                self.git.say("  " + result.stdout.replace('\n', '\n  '))
                self.ok = False
                self.code = 1
                return

        self.git.log(f"Back to {self.start_pwd}")
        os.chdir(self.start_pwd)

        self.git.log(f"Create ref 'refs/subrepo/{self.subref}/branch'.")
        self.make_ref(f'refs/subrepo/{self.subref}/branch', branch)

        self.git.log(f"Commit the new '{self.subrepo_commit_ref}' content.")
        self.commit_subrepo_branch()

    def do_push(self):
        """Push implementation"""
        branch = getattr(self, 'branch', None)
        new_upstream = False
        branch_created = False

        if not branch:
            result = subprocess.run(
                [
                    'git',
                    'fetch',
                    '--no-tags',
                    '--quiet',
                    self.config.remote,
                    self.config.branch,
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                if re.search(
                    r"(^|\n)fatal: couldn't find remote ref ", result.stderr.lower()
                ):
                    self.git.log(
                        f"Pushing to new upstream: {self.config.remote} ({self.config.branch})."
                    )
                    new_upstream = True
                else:
                    self.error(f"Fetch for push failed: {result.stderr}")
            else:
                self.git.log("Check upstream head against .gitrepo commit.")
                if not self.flags.force:
                    upstream = self.git.run(['rev-parse', 'FETCH_HEAD^0'], check=True)
                    if upstream != self.config.commit:
                        self.error(
                            "There are new changes upstream, you need to pull first."
                        )

                self.upstream_head_commit = self.git.run(
                    ['rev-parse', 'FETCH_HEAD^0'], check=True
                )

            branch = f'subrepo/{self.subref}'
            self.worktree = os.path.join(self.git_tmp, branch)
            self.delete_branch(branch)

            if self.flags.squash:
                self.git.log("Squash commits")
                self.config.parent = 'HEAD^'

            self.git.log(f"Create subrepo branch '{branch}'.")
            self.create_subrepo_branch(branch)

            os.chdir(self.worktree)

            method = self.join_method or self.config.method
            if method == 'rebase':
                refs_fetch = f'refs/subrepo/{self.subref}/fetch'
                self.git.log(f"Rebase changes to {refs_fetch}")
                result = subprocess.run(
                    ['git', 'rebase', refs_fetch, branch],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self.git.say("The \"git rebase\" command failed:")
                    self.git.say("")
                    self.git.say("  " + result.stdout.replace('\n', '\n  '))
                    self.ok = False
                    self.code = 1
                    return

            branch_created = True
            os.chdir(self.start_pwd)
        else:
            if self.flags.squash:
                self.error("Squash option (-s) can't be used with branch parameter")

        self.git.log(f"Make sure that '{branch}' exists.")
        if not self.git.branch_exists(branch):
            self.error(f"No subrepo branch '{branch}' to push.")

        self.git.log("Check if we have something to push")
        new_commit = self.git.run(['rev-parse', branch], check=True)
        if not new_upstream and self.upstream_head_commit == new_commit:
            if branch_created:
                self.git.log(f"Remove branch '{branch}'.")
                self.delete_branch(branch)
            self.ok = False
            self.code = -2
            return

        if not self.flags.force and not new_upstream:
            self.git.log(f"Make sure '{branch}' contains the upstream HEAD.")
            if not self.git.commit_in_rev_list(self.upstream_head_commit, branch):
                self.error(
                    f"Can't commit: '{branch}' doesn't contain upstream HEAD: {self.upstream_head_commit}"
                )

        force = ' --force' if self.flags.force else ''
        self.git.log(
            f"Push{force} branch '{branch}' to '{self.config.remote}' ({self.config.branch})."
        )
        cmd = ['push']
        if self.flags.force:
            cmd.append('--force')
        cmd.extend([self.config.remote, f'{branch}:{self.config.branch}'])
        self.git.run(cmd)

        self.git.log(f"Create ref 'refs/subrepo/{self.subref}/push'.")
        self.make_ref(f'refs/subrepo/{self.subref}/push', branch)

        if branch_created:
            self.git.log(f"Remove branch '{branch}'.")
            self.delete_branch(branch)

        self.git.log(f"Put updates into '{self.subdir}/.gitrepo' file.")
        self.upstream_head_commit = new_commit
        self.subrepo_commit_ref = self.upstream_head_commit
        self.update_gitrepo_file()

        msg = self.commit_message or self.build_commit_message()

        if self.commit_msg_file:
            self.git.run(['commit', '--file', self.commit_msg_file])
        else:
            self.git.run(['commit', '-m', msg])

    def do_fetch(self):
        """Fetch upstream content"""
        if self.config.remote == 'none':
            self.error(
                f"Can't fetch subrepo. Remote is 'none' in '{self.subdir}/.gitrepo'."
            )

        branch_info = f"({self.config.branch})" if self.config.branch else ""
        self.git.log(f"Fetch the upstream: {self.config.remote} {branch_info}.")

        cmd = ['fetch', '--no-tags', '--quiet', self.config.remote]
        if self.config.branch:
            cmd.append(self.config.branch)

        self.git.run(cmd)

        self.git.log("Get the upstream subrepo HEAD commit.")
        self.upstream_head_commit = self.git.run(
            ['rev-parse', 'FETCH_HEAD^0'], check=True
        )

        self.git.log(f"Create ref 'refs/subrepo/{self.subref}/fetch'.")
        self.make_ref(f'refs/subrepo/{self.subref}/fetch', 'FETCH_HEAD^0')

    def create_subrepo_branch(self, branch=None):
        """Create a subrepo branch"""
        if branch is None:
            branch = f'subrepo/{self.subref}'

        self.git.log(f"Check if the '{branch}' branch already exists.")
        if self.git.branch_exists(branch):
            return

        self.git.log(f"Subrepo parent: {self.config.parent}")

        first_gitrepo_commit = None
        last_gitrepo_commit = None

        if self.config.parent:
            # Check if parent is ancestor
            result = subprocess.run(
                ['git', 'merge-base', '--is-ancestor', self.config.parent, 'HEAD'],
                capture_output=True,
            )
            if result.returncode != 0:
                prev = self.git.run(
                    ['log', '-1', '-G', 'commit =', '--format=%H', self.gitrepo],
                    capture=True,
                    fail=False,
                )
                if prev:
                    prev = self.git.run(
                        ['log', '-1', '--format=%H', f'{prev.strip()}^'], check=True
                    )
                self.error(
                    textwrap.dedent(f"""\
                    The last sync point (where upstream and the subrepo were equal) is not an ancestor.
                    This is usually caused by a rebase affecting that commit.
                    To recover set the subrepo parent in '{self.gitrepo}'
                    to '{prev}'
                    and validate the subrepo by comparing with 'git subrepo branch {self.subdir}'""")
                )

            # Get commit list
            self.git.log("Create new commits with parents into the subrepo fetch")
            commits = self.git.run(
                [
                    'rev-list',
                    '--reverse',
                    '--ancestry-path',
                    '--topo-order',
                    f'{self.config.parent}..HEAD',
                ],
                check=True,
            ).split('\n')

            prev_commit = None
            ancestor = None

            for commit in commits:
                self.git.log(f"Working on {commit}")

                # Get .gitrepo commit
                gitrepo_commit = self.git.run(
                    [
                        'config',
                        '--blob',
                        f'{commit}:{self.subdir}/.gitrepo',
                        'subrepo.commit',
                    ],
                    capture=True,
                    fail=False,
                )

                if not gitrepo_commit:
                    self.git.log("Ignore commit, no .gitrepo file")
                    continue

                gitrepo_commit = gitrepo_commit.strip()
                self.git.log(f".gitrepo reference commit: {gitrepo_commit}")

                # Check if direct child
                if ancestor:
                    parents = self.git.run(
                        ['show', '-s', '--pretty=format:%P', commit], check=True
                    )
                    if ancestor not in parents:
                        self.git.log(f"Ignore {commit}, it's not in the selected path")
                        continue

                ancestor = commit

                # Check for rebase (only during pull operations)
                self.git.log("Check for rebase")
                refs_fetch = f'refs/subrepo/{self.subref}/fetch'
                if self.git.rev_exists(refs_fetch) and self.command == 'pull':
                    # Check if gitrepo_commit is reachable from refs_fetch
                    result = subprocess.run(
                        [
                            'git',
                            'merge-base',
                            '--is-ancestor',
                            gitrepo_commit,
                            refs_fetch,
                        ],
                        capture_output=True,
                    )
                    if result.returncode != 0:
                        if not self.git.rev_exists(gitrepo_commit):
                            self.error(
                                f"Local repository does not contain {gitrepo_commit}. Try to 'git subrepo fetch {self.subref}' or add the '-F' flag."
                            )
                        else:
                            self.error(
                                f"Upstream history has been rewritten. Commit {gitrepo_commit} is not in the upstream history. Try to 'git subrepo fetch {self.subref}' or add the '-F' flag."
                            )

                # Find parents
                self.git.log("Find parents")
                first_parent = ['-p', prev_commit] if prev_commit else []

                second_parent = []
                if not first_gitrepo_commit:
                    first_gitrepo_commit = gitrepo_commit
                    second_parent = ['-p', gitrepo_commit]

                method = self.join_method or self.config.method
                if method != 'rebase':
                    if gitrepo_commit != last_gitrepo_commit:
                        second_parent = ['-p', gitrepo_commit]
                        last_gitrepo_commit = gitrepo_commit

                # Create new commit
                self.git.log(
                    f"Create a new commit {' '.join(first_parent)} {' '.join(second_parent)}"
                )

                has_content = (
                    subprocess.run(
                        ['git', 'cat-file', '-e', f'{commit}:{self.subdir}'],
                        capture_output=True,
                    ).returncode
                    == 0
                )

                if has_content:
                    self.git.log("Create with content")
                    author_date = self.git.run(
                        ['log', '-1', '--date=default', '--format=%ad', commit],
                        check=True,
                    )
                    author_email = self.git.run(
                        ['log', '-1', '--date=default', '--format=%ae', commit],
                        check=True,
                    )
                    author_name = self.git.run(
                        ['log', '-1', '--date=default', '--format=%an', commit],
                        check=True,
                    )
                    commit_msg = self.git.run(
                        ['log', '-n', '1', '--date=default', '--format=%B', commit],
                        capture=True,
                    )

                    env = os.environ.copy()
                    env.update({
                        'GIT_AUTHOR_DATE': author_date,
                        'GIT_AUTHOR_EMAIL': author_email,
                        'GIT_AUTHOR_NAME': author_name,
                    })

                    tree_cmd = (
                        ['commit-tree', '-F', '-']
                        + first_parent
                        + second_parent
                        + [f'{commit}:{self.subdir}']
                    )
                    proc = subprocess.run(
                        ['git'] + tree_cmd,
                        input=commit_msg,
                        capture_output=True,
                        text=True,
                        env=env,
                    )
                    prev_commit = proc.stdout.strip()
                else:
                    self.git.log("Create empty placeholder")
                    prev_commit = self.git.run(
                        ['commit-tree', '-m', 'EMPTY']
                        + first_parent
                        + second_parent
                        + [EMPTY_TREE_SHA],
                        check=True,
                    )

            self.git.log(
                f"Create branch '{branch}' for this new commit set {prev_commit}."
            )
            self.git.run(['branch', branch, prev_commit])
        else:
            self.git.log("No parent setting, use the subdir content.")
            self.git.run(['branch', branch, 'HEAD'])

            # Filter branch
            cmd = [
                'git',
                'filter-branch',
                '-f',
                '--subdirectory-filter',
                self.subref,
                branch,
            ]
            if self.flags.verbose:
                subprocess.run(cmd, check=False)
            else:
                subprocess.run(cmd, capture_output=True, check=False)

        # Remove .gitrepo file
        self.git.log(
            f"Remove the .gitrepo file from {first_gitrepo_commit or ''}..{branch}"
        )
        filter_range = (
            f'{first_gitrepo_commit}..{branch}' if first_gitrepo_commit else branch
        )

        cmd = [
            'git',
            'filter-branch',
            '-f',
            '--prune-empty',
            '--tree-filter',
            'rm -f .gitrepo',
            '--',
            filter_range,
            '--first-parent',
        ]
        if self.flags.verbose:
            subprocess.run(cmd, check=False)
        else:
            subprocess.run(cmd, capture_output=True, check=False)

        self.create_worktree(branch)

        self.git.log(f"Create ref 'refs/subrepo/{self.subref}/branch'.")
        self.make_ref(f'refs/subrepo/{self.subref}/branch', branch)

    def commit_subrepo_branch(self):
        """Commit a subrepo branch"""
        self.git.log(f"Check that '{self.subrepo_commit_ref}' exists.")
        if not self.git.rev_exists(self.subrepo_commit_ref):
            self.error(f"Commit ref '{self.subrepo_commit_ref}' does not exist.")

        if not self.flags.force:
            self.git.log(
                f"Make sure '{self.subrepo_commit_ref}' contains the upstream HEAD."
            )
            if not self.git.commit_in_rev_list(
                self.upstream_head_commit, self.subrepo_commit_ref
            ):
                self.error(
                    f"Can't commit: '{self.subrepo_commit_ref}' doesn't contain upstream HEAD."
                )

        has_files = self.git.run(
            ['ls-files', '--', self.subdir], capture=True, fail=False
        )
        if has_files.strip():
            self.git.log("Remove old content of the subdir.")
            self.git.run(['rm', '-r', '--', self.subdir])

        self.git.log(f"Put remote subrepo content into '{self.subdir}/'.")
        self.git.run([
            'read-tree',
            f'--prefix={self.subdir}',
            '-u',
            self.subrepo_commit_ref,
        ])

        self.git.log(f"Put info into '{self.subdir}/.gitrepo' file.")
        self.update_gitrepo_file()
        self.git.run(['add', '-f', '--', self.gitrepo])

        msg = self.commit_message or self.build_commit_message()
        edit_flag = ['--edit'] if self.flags.edit else []

        self.git.log(f"Commit to the '{self.original_head_branch}' branch.")
        if self.original_head_commit != 'none':
            if self.commit_msg_file:
                self.git.run(['commit'] + edit_flag + ['--file', self.commit_msg_file])
            else:
                self.git.run(['commit'] + edit_flag + ['-m', msg])
        else:
            tree = self.git.run(['write-tree'], check=True)

            if self.commit_msg_file:
                commit_sha = self.git.run(
                    ['commit-tree']
                    + edit_flag
                    + ['--file', self.commit_msg_file, tree],
                    check=True,
                )
            else:
                commit_sha = self.git.run(
                    ['commit-tree'] + edit_flag + ['-m', msg, tree], check=True
                )

            self.git.run(['reset', '--hard', commit_sha])

        self.remove_worktree()

        self.git.log(f"Create ref 'refs/subrepo/{self.subref}/commit'.")
        self.make_ref(f'refs/subrepo/{self.subref}/commit', self.subrepo_commit_ref)

    def get_status(self) -> str:
        """Get subrepo status"""
        output = []

        if not self.args:
            subrepos = self.find_all_subrepos()
            count = len(subrepos)
            if not self.flags.quiet:
                if count == 0:
                    return "No subrepos.\n"
                s = 's' if count != 1 else ''
                output.append(f"{count} subrepo{s}:\n")
        else:
            subrepos = self.args

        for subdir in subrepos:
            self.subdir = subdir
            self.normalize_subdir()
            self.encode_subdir()

            gitrepo = f'{subdir}/.gitrepo'
            if not os.path.isfile(gitrepo):
                output.append(f"'{subdir}' is not a subrepo\n")
                continue

            refs_fetch = f'refs/subrepo/{self.subref}/fetch'
            upstream_head = self.git.run(
                ['rev-parse', '--short', refs_fetch], capture=True, fail=False
            )

            self.gitrepo = gitrepo
            self.read_config()

            if self.flags.fetch:
                self.do_fetch()

            if self.flags.quiet:
                output.append(f"{subdir}\n")
                continue

            output.append(f"Git subrepo '{subdir}':\n")

            if self.git.branch_exists(f'subrepo/{self.subref}'):
                output.append(f"  Subrepo Branch:  subrepo/{self.subref}\n")

            remote = f'subrepo/{self.subref}'
            url = self.git.run(
                ['config', f'remote.{remote}.url'], capture=True, fail=False
            )
            if url and url.strip():
                output.append(f"  Remote Name:     subrepo/{self.subref}\n")

            output.append(f"  Remote URL:      {self.config.remote}\n")
            if upstream_head and upstream_head.strip():
                output.append(f"  Upstream Ref:    {upstream_head.strip()}\n")
            output.append(f"  Tracking Branch: {self.config.branch}\n")

            if self.config.commit:
                short = self.git.run(
                    ['rev-parse', '--short', self.config.commit], check=True
                )
                output.append(f"  Pulled Commit:   {short}\n")

            if self.config.parent:
                short = self.git.run(
                    ['rev-parse', '--short', self.config.parent], check=True
                )
                output.append(f"  Pull Parent:     {short}\n")

            worktree_list = (
                self.git.run(['worktree', 'list'], capture=True, fail=False) or ''
            )
            for line in worktree_list.split('\n'):
                if f'{self.git_tmp}/subrepo/{subdir}' in line:
                    output.append(f"  Worktree: {line}\n")

            if self.flags.verbose:
                output.append(self.format_refs())

            output.append("\n")

        return ''.join(output)

    def format_refs(self) -> str:
        """Format refs for status"""
        output = []
        show_ref = self.git.run(['show-ref'], capture=True, fail=False) or ''

        for line in show_ref.split('\n'):
            m = re.match(rf'^([0-9a-f]+)\s+refs/subrepo/{self.subref}/([a-z]+)', line)
            if m:
                sha_full = m.group(1)
                sha = self.git.run(['rev-parse', '--short', sha_full], check=True)
                ref_type = m.group(2)
                ref = f'refs/subrepo/{self.subref}/{ref_type}'

                labels = {
                    'branch': 'Branch Ref',
                    'commit': 'Commit Ref',
                    'fetch': 'Fetch Ref',
                    'pull': 'Pull Ref',
                    'push': 'Push Ref',
                }
                if ref_type in labels:
                    output.append(f"    {labels[ref_type]:14} {sha} ({ref})\n")

        if output:
            return "  Refs:\n" + ''.join(output)
        return ""

    def do_clean(self) -> List[str]:
        """Clean subrepo branches and refs"""
        items = []
        branch = f'subrepo/{self.subref}'
        ref = f'refs/heads/{branch}'
        self.worktree = os.path.join(self.git_tmp, branch)

        self.git.log(f"Clean {self.subdir}")
        self.remove_worktree()

        if self.git.branch_exists(branch):
            self.git.log(f"Remove branch '{branch}'.")
            self.git.run(['update-ref', '-d', ref])
            items.append(f"branch '{branch}'")

        if self.flags.force:
            self.git.log("Remove all subrepo refs.")
            suffix = '' if self.flags.all else f'{self.subref}/'

            show_ref = self.git.run(['show-ref'], capture=True, fail=False) or ''
            for line in show_ref.split('\n'):
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    ref = parts[1]
                    if ref.startswith(f'refs/subrepo/{suffix}') or ref.startswith(
                        f'refs/original/refs/heads/subrepo/{suffix}'
                    ):
                        self.git.run(['update-ref', '-d', ref])

        return items

    # ===== Support Functions =====

    def init_command(self):
        """Initialize command processing"""
        os.environ['GIT_SUBREPO_RUNNING'] = str(os.getpid())
        os.environ['GIT_SUBREPO_COMMAND'] = self.command

        pager = os.getenv('GIT_SUBREPO_PAGER') or os.getenv('PAGER') or 'less'
        os.environ['GIT_SUBREPO_PAGER'] = 'less -FRX' if pager == 'less' else pager

    def prepare_command(self):
        """Prepare for command execution"""
        if self.git.rev_exists('HEAD'):
            self.original_head_commit = self.git.run(['rev-parse', 'HEAD'], check=True)
        else:
            self.original_head_commit = 'none'

    def setup_command(self, params):
        """Setup command with parameters"""
        self.parse_params(params)
        self.normalize_subdir()
        self.encode_subdir()
        self.gitrepo = f'{self.subdir}/.gitrepo'

        # Check for existing worktree
        if not self.flags.force:
            self.git.log(f"Check for worktree with branch subrepo/{self.subdir}")
            worktree_list = (
                self.git.run(['worktree', 'list'], capture=True, fail=False) or ''
            )

            has_worktree = False
            worktree_path = None
            for line in worktree_list.split('\n'):
                if f'[subrepo/{self.subdir}]' in line:
                    has_worktree = True
                    worktree_path = line.split()[0]
                    break

            if self.command in ['commit'] and not has_worktree:
                self.error(
                    "There is no worktree available, use the branch command first"
                )
            elif (
                self.command not in ['branch', 'clean', 'commit', 'push']
                and has_worktree
            ):
                if os.path.exists(self.gitrepo):
                    self.error(
                        textwrap.dedent(f"""\
                        There is already a worktree with branch subrepo/{self.subdir}.
                        Use the --force flag to override this check or perform a subrepo clean
                        to remove the worktree.""")
                    )
                else:
                    self.error(
                        textwrap.dedent(f"""\
                        There is already a worktree with branch subrepo/{self.subdir}.
                        Use the --force flag to override this check or remove the worktree with
                        1. rm -rf {worktree_path}
                        2. git worktree prune
                        """)
                    )

        # Initialize config if needed
        if not self.config:
            self.config = SubrepoConfig()

        # Set config from parameters (for clone/init)
        if hasattr(self, 'subrepo_remote') and self.subrepo_remote:
            self.config.remote = self.subrepo_remote
        if hasattr(self, 'subrepo_branch') and self.subrepo_branch:
            self.config.branch = self.subrepo_branch

        # Apply overrides (from command line flags)
        if self.override_remote:
            self.config.remote = self.override_remote
        if self.override_branch:
            self.config.branch = self.override_branch

        # Read .gitrepo file if not clone/init
        if self.command not in ['clone', 'init']:
            self.read_config()

    def parse_params(self, params):
        """Parse command parameters"""
        i = 0
        num = len(self.args)

        for arg in params:
            value = self.args[i] if i < num else None

            if arg.startswith('+'):
                # Required parameter
                param = arg[1:]
                if i >= num:
                    self.usage_error(
                        f"Command '{self.command}' requires arg '{param}'."
                    )
                setattr(self, param, value)
            elif ':' in arg:
                # Optional with default function
                param, func = arg.split(':', 1)
                if i < num:
                    setattr(self, param, value)
                else:
                    getattr(self, func)()
            else:
                # Optional
                if i < num:
                    setattr(self, arg, value)

            i += 1

        if num > i:
            extra = ' '.join(self.args[i:])
            self.error(f"Unknown argument(s) '{extra}' for '{self.command}' command.")

    def guess_subdir(self):
        """Guess subdirectory name from remote URL"""
        remote = getattr(self, 'subrepo_remote', None)
        if not remote:
            self.error("No remote specified for guessing subdir")

        name = remote.rstrip('/')
        if name.endswith('.git'):
            name = name[:-4]
        name = os.path.basename(name)

        if not re.match(r'^[-_a-zA-Z0-9]+$', name):
            self.error(f"Can't determine subdir from '{remote}'.")

        self.subdir = name
        self.normalize_subdir()
        self.encode_subdir()

    def normalize_subdir(self):
        """Normalize subdir path"""
        if not self.subdir:
            self.error("subdir not set")

        if self.subdir.startswith('/') or (
            len(self.subdir) > 1 and self.subdir[1] == ':'
        ):
            self.usage_error(f"The subdir '{self.subdir}' should not be absolute path.")

        # Remove trailing /
        self.subdir = self.subdir.rstrip('/')

        # Remove leading ./ but keep if directory name starts with dot
        if self.subdir.startswith('./'):
            self.subdir = self.subdir[2:]

        # Compress multiple slashes
        self.subdir = re.sub(r'/+', '/', self.subdir)

    def encode_subdir(self):
        """Encode subdir as valid git ref"""
        self.subref = self.subdir

        # Check if already valid
        result = subprocess.run(
            ['git', 'check-ref-format', f'subrepo/{self.subref}'], capture_output=True
        )
        if result.returncode == 0:
            return

        # Encode special characters
        subref = self.subref.replace('%', '%25')
        subref = '/' + subref + '/'
        subref = subref.replace('/.', '/%2e')
        subref = subref.replace('.lock/', '%2elock/')
        subref = subref.strip('/')

        subref = subref.replace('..', '%2e%2e')
        subref = subref.replace('%2e.', '%2e%2e')
        subref = subref.replace('.%2e', '%2e%2e')

        for i in range(1, 32):
            subref = subref.replace(chr(i), f'%{i:02x}')

        for char, encoded in [
            ('\x7f', '%7f'),
            (' ', '%20'),
            ('~', '%7e'),
            ('^', '%5e'),
            (':', '%3a'),
            ('?', '%3f'),
            ('*', '%2a'),
            ('[', '%5b'),
            ('\n', '%0a'),
            ('@{', '%40{'),
            ('\\', '%5c'),
        ]:
            subref = subref.replace(char, encoded)

        subref = re.sub(r'/+', '/', subref)

        if subref.endswith('.'):
            subref = subref[:-1] + '%2e'

        try:
            result = subprocess.run(
                ['git', 'check-ref-format', '--normalize', '--allow-onelevel', subref],
                capture_output=True,
                text=True,
                check=True,
            )
            self.subref = result.stdout.strip()
        except subprocess.CalledProcessError:
            self.error(f"Can't determine valid subref from '{self.subdir}'.")

    def read_config(self):
        """Read .gitrepo file"""
        self.gitrepo = f'{self.subdir}/.gitrepo'

        if not os.path.isfile(self.gitrepo):
            self.error(f"No '{self.gitrepo}' file.")

        self.config = SubrepoConfig.from_file(self.gitrepo, self.git)

        # Apply overrides
        if self.override_remote:
            self.config.remote = self.override_remote
        if self.override_branch:
            self.config.branch = self.override_branch
        if self.join_method:
            self.config.method = self.join_method

    def update_gitrepo_file(self):
        """Update .gitrepo file"""
        newfile = False

        if not os.path.exists(self.gitrepo):
            # Try to recreate from parent commit
            result = subprocess.run(
                [
                    'git',
                    'cat-file',
                    '-e',
                    f'{self.original_head_commit}:{self.gitrepo}',
                ],
                capture_output=True,
            )

            if result.returncode == 0:
                self.git.log(
                    f"Try to recreate gitrepo file from {self.original_head_commit}"
                )
                content = self.git.run(
                    ['cat-file', '-p', f'{self.original_head_commit}:{self.gitrepo}'],
                    capture=True,
                )
                with open(self.gitrepo, 'w') as f:
                    f.write(content)
            else:
                newfile = True
                with open(self.gitrepo, 'w') as f:
                    f.write(GITREPO_HEADER)

        # Update fields
        should_update_remote = (
            newfile
            or (self.flags.update and self.override_remote)
            or (self.command in ['push', 'clone'] and self.override_remote)
        )
        should_update_branch = (
            newfile
            or (self.flags.update and self.override_branch)
            or (self.command in ['push', 'clone'] and self.override_branch)
        )

        if should_update_remote:
            self.git.config_set(self.gitrepo, 'subrepo.remote', self.config.remote)

        if should_update_branch:
            self.git.config_set(self.gitrepo, 'subrepo.branch', self.config.branch)

        if self.upstream_head_commit:
            self.git.config_set(
                self.gitrepo, 'subrepo.commit', self.upstream_head_commit
            )

        if self.upstream_head_commit and self.subrepo_commit_ref:
            commit_ref_sha = self.git.run(
                ['rev-parse', self.subrepo_commit_ref], check=True
            )
            self.git.log(f"{self.upstream_head_commit} == {commit_ref_sha}")
            if self.upstream_head_commit == commit_ref_sha:
                self.git.config_set(
                    self.gitrepo, 'subrepo.parent', self.original_head_commit
                )

        method = self.join_method or self.config.method or 'merge'
        self.git.config_set(self.gitrepo, 'subrepo.method', method)
        self.git.config_set(self.gitrepo, 'subrepo.cmdver', VERSION)
        self.git.run(['add', '-f', '--', self.gitrepo])

    # ===== Checks and Validations =====

    def check_environment(self):
        """Check that environment is suitable"""
        if not shutil.which('git'):
            self.error("Can't find your 'git' command in '$PATH'.")

        result = subprocess.run(['git', '--version'], capture_output=True, text=True)
        version_match = re.search(r'(\d+\.\d+\.\d+)', result.stdout)
        if version_match:
            self.git_version = version_match.group(1)
        else:
            self.error("Can't determine git version")

        if not self.check_version(self.git_version, REQUIRED_GIT_VERSION):
            self.error(
                f"Requires git version {REQUIRED_GIT_VERSION} or higher; you have '{self.git_version}'."
            )

    def check_repository(self):
        """Check that repository is ready"""
        if self.command in ['help', 'version', 'upgrade']:
            return

        try:
            subprocess.run(
                ['git', 'rev-parse', '--git-dir'], check=True, capture_output=True
            )
        except subprocess.CalledProcessError:
            self.error("Not inside a git repository.")

        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--git-common-dir'],
                capture_output=True,
                text=True,
                check=True,
            )
            git_common_dir = result.stdout.strip()
        except subprocess.CalledProcessError:
            git_common_dir = '.git'

        self.git_tmp = os.path.join(git_common_dir, 'tmp')

        # Get original branch
        result = subprocess.run(
            ['git', 'symbolic-ref', '--short', '--quiet', 'HEAD'],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip() != 'HEAD':
            self.original_head_branch = result.stdout.strip()
        else:
            self.original_head_branch = None

        if self.original_head_branch and self.original_head_branch.startswith(
            'subrepo/'
        ):
            self.error(f"Can't '{self.command}' while subrepo branch is checked out.")

        if self.original_head_branch in ['HEAD', '', None]:
            self.error("Must be on a branch to run this command.")

        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--is-inside-work-tree'],
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout.strip() != 'true':
                self.error(f"Can't 'subrepo {self.command}' outside a working tree.")
        except subprocess.CalledProcessError:
            self.error(f"Can't 'subrepo {self.command}' outside a working tree.")

        if self.command != 'clone':
            try:
                subprocess.run(
                    ['git', 'rev-parse', '--verify', 'HEAD'],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                self.error("HEAD does not exist")

        self.check_working_copy_clean()

        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--show-prefix'],
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout.strip():
                self.error(
                    "Need to run subrepo command from top level directory of the repo."
                )
        except subprocess.CalledProcessError:
            pass

    def check_working_copy_clean(self):
        """Ensure working copy has no uncommitted changes"""
        if self.command not in ['clone', 'init', 'pull', 'push', 'branch', 'commit']:
            return

        pwd = os.getcwd()
        self.git.log(f"Assert that working copy is clean: {pwd}")

        subprocess.run(
            ['git', 'update-index', '-q', '--ignore-submodules', '--refresh'],
            capture_output=True,
        )

        result = subprocess.run(
            ['git', 'diff-files', '--quiet', '--ignore-submodules'], capture_output=True
        )
        if result.returncode != 0:
            self.error(f"Can't {self.command} subrepo. Unstaged changes. ({pwd})")

        if self.command != 'clone' or self.git.rev_exists('HEAD'):
            result = subprocess.run(
                ['git', 'diff-index', '--quiet', '--ignore-submodules', 'HEAD'],
                capture_output=True,
            )
            if result.returncode != 0:
                self.error(
                    f"Can't {self.command} subrepo. Working tree has changes. ({pwd})"
                )

            result = subprocess.run(
                [
                    'git',
                    'diff-index',
                    '--quiet',
                    '--cached',
                    '--ignore-submodules',
                    'HEAD',
                ],
                capture_output=True,
            )
            if result.returncode != 0:
                self.error(f"Can't {self.command} subrepo. Index has changes. ({pwd})")
        else:
            result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True)
            if result.stdout.strip():
                self.error(f"Can't {self.command} subrepo. Index has changes. ({pwd})")

    def check_subdir_empty(self):
        """Ensure subdirectory is empty or doesn't exist"""
        if os.path.exists(self.subdir):
            if os.listdir(self.subdir):
                self.error(f"The subdir '{self.subdir}' exists and is not empty.")

    def check_subdir_for_init(self):
        """Check subdir is ready for init"""
        if not os.path.exists(self.subdir):
            self.error(f"The subdir '{self.subdir}' does not exist.")

        if os.path.exists(f'{self.subdir}/.gitrepo'):
            self.error(f"The subdir '{self.subdir}' is already a subrepo.")

        result = subprocess.run(
            ['git', 'log', '-1', '--date=default', '--', self.subdir],
            capture_output=True,
            text=True,
        )
        if not result.stdout.strip():
            self.error(f"The subdir '{self.subdir}' is not part of this repo.")

    # ===== Git Helpers =====

    def make_ref(self, ref_name: str, commit: str):
        """Create or update a ref"""
        commit_sha = self.git.run(['rev-parse', commit], check=True)
        self.git.run(['update-ref', ref_name, commit_sha])

    def create_worktree(self, branch: str):
        """Create a worktree for branch"""
        self.worktree = os.path.join(self.git_tmp, branch)
        self.git.run(['worktree', 'add', self.worktree, branch])

    def remove_worktree(self):
        """Remove worktree"""
        if not self.worktree:
            return

        self.git.log(f"Remove worktree: {self.worktree}")
        if os.path.isdir(self.worktree):
            self.git.log("Check worktree for unsaved changes")
            saved_pwd = os.getcwd()
            os.chdir(self.worktree)
            self.check_working_copy_clean()
            os.chdir(saved_pwd)

            self.git.log(f"Clean up worktree {self.worktree}")
            shutil.rmtree(self.worktree)
            self.git.run(['worktree', 'prune'])

    def delete_branch(self, branch: str):
        """Delete a branch"""
        self.git.log(f"Deleting old '{branch}' branch.")
        self.remove_worktree()
        subprocess.run(['git', 'branch', '-D', branch], capture_output=True)

    # ===== Utility Functions =====

    def find_all_subrepos(self) -> List[str]:
        """Find all subrepos in repository"""
        result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True)

        paths = []
        for line in result.stdout.split('\n'):
            if line.endswith('/.gitrepo'):
                paths.append(line[:-9])

        paths.sort()
        subrepos = []

        for path in paths:
            # Skip sub-subrepos unless ALL wanted
            if not self.flags.ALL:
                if any(path.startswith(f'{existing}/') for existing in subrepos):
                    continue
            subrepos.append(path)

        return subrepos

    def get_upstream_branch(self) -> str:
        """Determine upstream default branch"""
        remotes = self.git.run(
            ['ls-remote', '--symref', self.config.remote], capture=True, fail=False
        )

        if not remotes:
            self.error(
                f"Command failed: 'git ls-remote --symref {self.config.remote}'."
            )

        for line in remotes.split('\n'):
            if line.startswith('ref:') and line.endswith('HEAD'):
                parts = line.split()
                if len(parts) >= 2:
                    ref = parts[1]
                    if ref.startswith('refs/heads/'):
                        return ref[11:]

        self.error("Problem finding remote default head branch.")

    def get_default_branch(self) -> str:
        """Get git's default branch name"""
        result = subprocess.run(
            ['git', 'config', '--get', 'init.defaultbranch'],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        parts = self.git_version.split('.')
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0

        return 'main' if (major > 2 or (major == 2 and minor >= 28)) else 'master'

    def build_commit_message(self) -> str:
        """Generate commit message"""
        commit = 'none'
        if self.upstream_head_commit and self.git.rev_exists(self.upstream_head_commit):
            commit = self.git.run(
                ['rev-parse', '--short', self.upstream_head_commit], check=True
            )

        args = []
        if self.flags.all:
            args.append(self.subdir)
        args.extend(self.commit_msg_args)

        merged = 'none'
        if (
            hasattr(self, 'subrepo_commit_ref')
            and self.subrepo_commit_ref
            and self.git.rev_exists(self.subrepo_commit_ref)
        ):
            merged = self.git.run(
                ['rev-parse', '--short', self.subrepo_commit_ref], check=True
            )

        is_merge = ''
        if self.command != 'push':
            if hasattr(self, 'subrepo_commit_ref') and self.subrepo_commit_ref:
                result = subprocess.run(
                    ['git', 'show', '--summary', self.subrepo_commit_ref],
                    capture_output=True,
                    text=True,
                )
                if 'Merge:' in result.stdout:
                    is_merge = ' (merge)'

        args_str = ' '.join(args)

        return textwrap.dedent(f"""\
            git subrepo {self.command}{is_merge} {args_str}

            subrepo:
              subdir:   "{self.subdir}"
              merged:   "{merged}"
            upstream:
              origin:   "{self.config.remote}"
              branch:   "{self.config.branch}"
              commit:   "{commit}"
            git-subrepo:
              version:  "{VERSION}"
              origin:   "???"
              commit:   "???"
            """)

    def print_join_error(self):
        """Print error message for join failures"""
        method = self.join_method or self.config.method
        branch_name = getattr(self, 'branch', None) or f'subrepo/{self.subdir}'

        rebase_step = "git rebase --continue" if method == 'rebase' else "git commit"

        commit_cmd = (
            f"git subrepo commit --file={self.commit_msg_file} {self.subdir}"
            if self.commit_msg_file
            else f"git subrepo commit {self.subdir}"
        )

        push_cmd = f"git subrepo push {self.subdir} {branch_name}"

        rebase_note = ""
        if self.command == 'pull' and method == 'rebase':
            rebase_note = textwrap.dedent(f"""
                After you have performed the steps above you can push your local changes
                without repeating the rebase by:
                  1. {push_cmd}

                """)

        msg = textwrap.dedent(f"""\
            You will need to finish the {self.command} by hand. A new working tree has been
            created at {self.worktree} so that you can resolve the conflicts
            shown in the output above.

            This is the common conflict resolution workflow:

              1. cd {self.worktree}
              2. Resolve the conflicts (see "git status").
              3. "git add" the resolved files.
              4. {rebase_step}
              5. If there are more conflicts, restart at step 2.
              6. cd {self.start_pwd}
              7. {commit_cmd if self.command == 'pull' else push_cmd}
            """)

        if rebase_note:
            msg += rebase_note

        msg += textwrap.dedent(f"""
            See "git help {method}" for details.

            Alternatively, you can abort the {self.command} and reset back to where you started:

              1. git subrepo clean {self.subdir}

            See "git help subrepo" for more help.
            """)

        print(msg, file=sys.stderr)

    def check_version(self, got: str, want: str) -> bool:
        """Check version is sufficient"""
        got_parts = got.split('.')
        want_parts = want.split('.')

        while len(got_parts) < 3:
            got_parts.append('0')
        while len(want_parts) < 3:
            want_parts.append('0')

        got_nums = [int(p) for p in got_parts[:3]]
        want_nums = [int(p) for p in want_parts[:3]]

        if got_nums[0] > want_nums[0]:
            return True
        if got_nums[0] == want_nums[0]:
            if got_nums[1] > want_nums[1]:
                return True
            if got_nums[1] == want_nums[1]:
                return got_nums[2] >= want_nums[2]
        return False

    def error(self, msg: str):
        """Print error and exit"""
        print(f"git-subrepo: {msg}", file=sys.stderr)
        raise GitSubrepoError(msg)

    def usage_error(self, msg: str):
        """Print usage error and exit"""
        print(f"git-subrepo: {msg}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point"""
    try:
        app = GitSubrepo()
        app.main(sys.argv[1:])
    except GitSubrepoError:
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == '__main__':
    main()
