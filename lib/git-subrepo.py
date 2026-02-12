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
from pathlib import Path
from typing import Optional, List, Tuple, Dict
import tempfile

VERSION = "0.4.9"
REQUIRED_GIT_VERSION = "2.23.0"

# Environment setup
os.environ['FILTER_BRANCH_SQUELCH_WARNING'] = '1'


class GitSubrepoError(Exception):
    """Base exception for git-subrepo errors"""
    def __init__(self, message, code=1):
        self.message = message
        self.code = code
        super().__init__(self.message)


class GitSubrepo:
    """Main git-subrepo implementation"""

    def __init__(self):
        # Global state variables
        self.command = None
        self.command_arguments = []
        self.commit_msg_args = []
        self.subrepos = []

        # Flags
        self.all_wanted = False
        self.ALL_wanted = False
        self.force_wanted = False
        self.fetch_wanted = False
        self.squash_wanted = False
        self.update_wanted = False
        self.quiet_wanted = False
        self.verbose_wanted = False
        self.debug_wanted = False
        self.edit_wanted = False

        # Paths and refs
        self.subdir = None
        self.subref = None
        self.gitrepo = None
        self.worktree = None
        self.start_pwd = os.getcwd()

        # Commits and refs
        self.original_head_commit = None
        self.original_head_branch = None
        self.upstream_head_commit = None

        # Subrepo state
        self.subrepo_remote = None
        self.subrepo_branch = None
        self.subrepo_commit = None
        self.subrepo_parent = None
        self.subrepo_former = None

        # Refs
        self.refs_subrepo_branch = None
        self.refs_subrepo_commit = None
        self.refs_subrepo_fetch = None
        self.refs_subrepo_push = None

        # Overrides
        self.override_remote = None
        self.override_branch = None

        # Commit message options
        self.wanted_commit_message = None
        self.commit_msg_file = None

        # Join method
        self.join_method = None

        # RUN flags
        self.FAIL = True
        self.OUT = False
        self.TTY = False
        self.SAY = True
        self.OK = True
        self.CODE = 0
        self.INDENT = ""

        # Git version
        self.git_version = None

        # Git temp directory
        self.GIT_TMP = None

        # Output storage
        self.output = ""

    def main(self, args):
        """Main entry point"""
        # Check for environment variable flags
        if os.getenv('GIT_SUBREPO_QUIET'):
            self.quiet_wanted = True
        if os.getenv('GIT_SUBREPO_VERBOSE'):
            self.verbose_wanted = True
        if os.getenv('GIT_SUBREPO_DEBUG'):
            self.debug_wanted = True

        # Parse arguments
        self.parse_arguments(args)

        # Check environment
        self.assert_environment_ok()

        # Make sure repo is ready
        self.assert_repo_is_ready()

        # Initialize command
        self.command_init()

        # Handle --all flag
        if self.all_wanted and self.command not in ['help', 'status']:
            if self.subrepo_branch:
                self.error("options --branch and --all are not compatible")

            # Run command on all subrepos
            args = self.command_arguments[:]
            self.get_all_subrepos()
            for subdir in self.subrepos:
                self.command_prepare()
                self.subrepo_remote = None
                self.subrepo_branch = None
                self.command_arguments = [subdir] + args
                self.dispatch_command()
        else:
            # Run command on specific subrepo
            self.command_prepare()
            self.dispatch_command()

    def parse_arguments(self, args):
        """Parse command line arguments"""
        # Reorder arguments to put options before positionals (git-style)
        # This allows: git subrepo pull --quiet bar
        # To be reordered to: git subrepo --quiet pull bar
        # But respect -- separator
        options = []
        positionals = []
        i = 0
        seen_separator = False
        while i < len(args):
            arg = args[i]
            if arg == '--':
                # Everything after -- is positional
                seen_separator = True
                positionals.append(arg)
            elif seen_separator or not arg.startswith('-'):
                # It's a positional
                positionals.append(arg)
            else:
                # It's an option
                options.append(arg)
                # Check if it takes a value
                if arg in ['-b', '--branch', '-M', '--method', '-m', '--message',
                          '--file', '-r', '--remote']:
                    # Next arg is the value
                    if i + 1 < len(args):
                        i += 1
                        options.append(args[i])
            i += 1

        # Recombine: options first, then positionals
        reordered_args = options + positionals

        # Custom error handler for argparse
        class CustomArgumentParser(argparse.ArgumentParser):
            def error(self, message):
                # Don't print usage, just raise
                raise argparse.ArgumentError(None, message)

        parser = CustomArgumentParser(
            prog='git subrepo',
            description='Git Submodule Alternative',
            add_help=False
        )

        # Options
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

        # Command and arguments
        parser.add_argument('command', nargs='?')
        parser.add_argument('arguments', nargs='*')

        # Parse with reordered arguments
        try:
            parsed = parser.parse_args(reordered_args)
        except argparse.ArgumentError as e:
            # Format error message to match bash version
            msg = str(e.message) if hasattr(e, 'message') else str(e)
            # Convert argparse format to bash format
            if 'unrecognized arguments:' in msg:
                args = msg.split('unrecognized arguments:')[1].strip()
                msg = f"error: unknown option `{args.lstrip('-')}"
            self.usage_error(msg)

        # Handle version
        if parsed.version:
            print(VERSION)
            sys.exit(0)

        # Handle help
        if parsed.help_flag:
            if not parsed.command:
                self.command = 'help'
                self.command_arguments = []
                return

        # Set flags
        if parsed.all_flag:
            self.all_wanted = True
        if parsed.ALL_flag:
            self.ALL_wanted = True
            self.all_wanted = True
        if parsed.branch:
            self.subrepo_branch = parsed.branch
            self.override_branch = parsed.branch
            self.commit_msg_args.append(f'--branch={parsed.branch}')
        if parsed.edit:
            self.edit_wanted = True
        if parsed.force:
            self.force_wanted = True
            self.commit_msg_args.append('--force')
        if parsed.fetch_flag:
            self.fetch_wanted = True
        if parsed.method:
            self.join_method = parsed.method
        if parsed.message:
            if parsed.msg_file:
                self.error("fatal: options '-m' and '--file' cannot be used together")
            self.wanted_commit_message = parsed.message
        if parsed.msg_file:
            if parsed.message:
                self.error("fatal: options '-m' and '--file' cannot be used together")
            if not os.path.isfile(parsed.msg_file):
                self.error(f"Commit msg file at {parsed.msg_file} not found")
            self.commit_msg_file = parsed.msg_file
        if parsed.remote:
            self.subrepo_remote = parsed.remote
            self.override_remote = parsed.remote
            self.commit_msg_args.append(f'--remote={parsed.remote}')
        if parsed.squash:
            self.squash_wanted = True
        if parsed.update:
            self.update_wanted = True
            self.commit_msg_args.append('--update')
        if parsed.quiet:
            self.quiet_wanted = True
        if parsed.verbose:
            self.verbose_wanted = True
        if parsed.debug:
            self.debug_wanted = True
        if parsed.DEBUG:
            os.environ['BASH_XTRACEFD'] = '1'

        # Set command
        self.command = parsed.command
        if not self.command:
            self.usage_error("No command specified. See 'git subrepo help'.")

        # Validate command exists
        valid_commands = ['clone', 'init', 'pull', 'push', 'fetch', 'branch',
                         'commit', 'status', 'clean', 'config', 'help', 'version', 'upgrade']
        if self.command not in valid_commands:
            self.usage_error(f"'{self.command}' is not a command. See 'git subrepo help'.")

        # Set command arguments
        self.command_arguments = parsed.arguments or []
        if self.command_arguments:
            self.command_arguments[0] = self.command_arguments[0].rstrip('/')
        self.commit_msg_args.extend(self.command_arguments)

        # Validate options for command
        self.check_options_for_command()

        # Validate update option
        if self.update_wanted:
            if not self.subrepo_branch and not self.subrepo_remote:
                self.usage_error("Can't use '--update' without '--branch' or '--remote'.")

    def check_options_for_command(self):
        """Validate options are valid for the command"""
        options_map = {
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

        valid_options = options_map.get(self.command, [])

        # Check each active option
        checks = [
            ('all', self.all_wanted),
            ('ALL', self.ALL_wanted),
            ('edit', self.edit_wanted),
            ('fetch', self.fetch_wanted),
            ('force', self.force_wanted),
            ('squash', self.squash_wanted),
            ('branch', self.override_branch is not None),
            ('remote', self.override_remote is not None),
            ('message', self.wanted_commit_message or self.commit_msg_file),
            ('update', self.update_wanted),
        ]

        for option, is_set in checks:
            if is_set and option not in valid_options:
                self.usage_error(f"Invalid option '--{option}' for '{self.command}'.")

    def dispatch_command(self):
        """Dispatch to the appropriate command function"""
        command_map = {
            'clone': self.command_clone,
            'init': self.command_init_subrepo,
            'pull': self.command_pull,
            'push': self.command_push,
            'fetch': self.command_fetch,
            'branch': self.command_branch,
            'commit': self.command_commit,
            'status': self.command_status,
            'clean': self.command_clean,
            'config': self.command_config,
            'help': self.command_help,
            'version': self.command_version,
            'upgrade': self.command_upgrade,
        }

        command_func = command_map.get(self.command)
        if command_func:
            try:
                command_func()
            except GitSubrepoError as e:
                if e.code != 0:
                    sys.exit(e.code)
        else:
            self.usage_error(f"Unknown command: {self.command}")

    # ===== Command Functions =====

    def command_clone(self):
        """Clone a remote repository into a local subdirectory"""
        self.command_setup(['+subrepo_remote', 'subdir:guess_subdir'])

        # Clone or reclone
        reclone_up_to_date = self.subrepo_clone()
        if reclone_up_to_date:
            self.say(f"Subrepo '{self.subdir}' is up to date.")
            return

        # Success message
        re_prefix = 're' if self.force_wanted else ''
        self.say(f"Subrepo '{self.subrepo_remote}' ({self.subrepo_branch}) {re_prefix}cloned into '{self.subdir}'.")

    def command_init_subrepo(self):
        """Initialize a subdirectory as a subrepo"""
        self.command_setup(['+subdir'])

        # Determine default branch
        default_branch = self.get_default_branch()

        # Set defaults for remote and branch if not already set
        if not self.subrepo_remote:
            self.subrepo_remote = 'none'
        if not self.subrepo_branch:
            self.subrepo_branch = default_branch

        # Init new subrepo
        self.subrepo_init()

        if self.OK:
            if self.subrepo_remote == 'none':
                self.say(f"Subrepo created from '{self.subdir}' (with no remote).")
            else:
                self.say(f"Subrepo created from '{self.subdir}' with remote '{self.subrepo_remote}' ({self.subrepo_branch}).")
        else:
            self.error(f"Unknown init error code: '{self.CODE}'")

    def command_pull(self):
        """Pull upstream changes to the subrepo"""
        self.command_setup(['+subdir'])

        self.subrepo_pull()

        if self.OK:
            self.say(f"Subrepo '{self.subdir}' pulled from '{self.subrepo_remote}' ({self.subrepo_branch}).")
        elif self.CODE == -1:
            self.say(f"Subrepo '{self.subdir}' is up to date.")
        elif self.CODE == 1:
            self.error_join()
            sys.exit(self.CODE)
        else:
            self.error(f"Unknown pull error code: '{self.CODE}'")

    def command_push(self):
        """Push local subrepo changes upstream"""
        self.command_setup(['+subdir', 'branch'])

        self.subrepo_push()

        if self.OK:
            self.say(f"Subrepo '{self.subdir}' pushed to '{self.subrepo_remote}' ({self.subrepo_branch}).")
        elif self.CODE == -2:
            self.say(f"Subrepo '{self.subdir}' has no new commits to push.")
        elif self.CODE == 1:
            self.error_join()
            sys.exit(self.CODE)
        else:
            self.error(f"Unknown push error code: '{self.CODE}'")

    def command_fetch(self):
        """Fetch a subrepo's remote branch"""
        self.command_setup(['+subdir'])

        if self.subrepo_remote == 'none':
            self.say(f"Ignored '{self.subdir}', no remote.")
        else:
            self.subrepo_fetch()
            self.say(f"Fetched '{self.subdir}' from '{self.subrepo_remote}' ({self.subrepo_branch}).")

    def command_branch(self):
        """Create a branch containing the local subrepo commits"""
        self.command_setup(['+subdir'])

        if self.fetch_wanted:
            self.CALL(self.subrepo_fetch)

        branch = f'subrepo/{self.subref}'
        if self.force_wanted:
            self.worktree = os.path.join(self.GIT_TMP, branch)
            self.git_delete_branch(branch)

        if self.git_branch_exists(branch):
            self.error(f"Branch '{branch}' already exists. Use '--force' to override.")

        self.subrepo_branch_create()
        self.say(f"Created branch '{branch}' and worktree '{self.worktree}'.")

    def command_commit(self):
        """Commit a merged subrepo branch"""
        self.command_setup(['+subdir', 'subrepo_commit_ref'])

        if self.fetch_wanted:
            self.CALL(self.subrepo_fetch)

        if not self.git_rev_exists(self.refs_subrepo_fetch):
            self.error(f"Can't find ref '{self.refs_subrepo_fetch}'. Try using -F.")

        self.upstream_head_commit = self.run_git(['rev-parse', self.refs_subrepo_fetch], capture=True).strip()

        if not hasattr(self, 'subrepo_commit_ref') or not self.subrepo_commit_ref:
            self.subrepo_commit_ref = f'subrepo/{self.subref}'

        self.do_subrepo_commit()
        self.say(f"Subrepo commit '{self.subrepo_commit_ref}' committed as")
        self.say(f"subdir '{self.subdir}/' to branch '{self.original_head_branch}'.")

    def command_status(self):
        """Get status of a subrepo (or all of them)"""
        output = self.subrepo_status()
        pager = os.getenv('GIT_SUBREPO_PAGER') or os.getenv('PAGER') or 'less'
        if pager == 'less':
            pager = 'less -FRX'

        # Use pager
        try:
            proc = subprocess.Popen(shlex.split(pager), stdin=subprocess.PIPE, text=True)
            proc.communicate(output)
        except:
            print(output)

    def command_clean(self):
        """Remove branches, remotes and refs for a subrepo"""
        self.command_setup(['+subdir'])
        clean_list = self.subrepo_clean()
        for item in clean_list:
            self.say(f"Removed {item}.")

    def command_config(self):
        """Get/set subrepo configuration"""
        self.command_setup(['+subdir', '+config_option', 'config_value'])

        self.o(f"Update '{self.subdir}' configuration with {self.config_option}={getattr(self, 'config_value', '')}")

        valid_options = ['branch', 'cmdver', 'commit', 'method', 'remote', 'version']
        if self.config_option not in valid_options:
            self.error(f"Option {self.config_option} not recognized")

        # Get value
        if not hasattr(self, 'config_value') or not self.config_value:
            value = self.run_git(['config', f'--file={self.gitrepo}', f'subrepo.{self.config_option}'], capture=True).strip()
            self.say(f"Subrepo '{self.subdir}' option '{self.config_option}' has value '{value}'.")
            return

        # Set value - requires force except for method
        if not self.force_wanted and self.config_option != 'method':
            self.error("This option is autogenerated, use '--force' to override.")

        if self.config_option == 'method':
            if self.config_value not in ['merge', 'rebase']:
                self.error("Not a valid method. Valid options are 'merge' or 'rebase'.")

        self.run_git(['config', f'--file={self.gitrepo}', f'subrepo.{self.config_option}', self.config_value])
        self.say(f"Subrepo '{self.subdir}' option '{self.config_option}' set to '{self.config_value}'.")

    def command_help(self):
        """Show help documentation"""
        help_text = """
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
"""
        print(help_text)

    def command_version(self):
        """Print version information"""
        print(f"git-subrepo Version: {VERSION}")
        print("Copyright 2013-2020 Ingy döt Net")
        print("https://github.com/ingydotnet/git-subrepo")
        print(os.path.abspath(__file__))
        print(f"Git Version: {self.git_version}")

    def command_upgrade(self):
        """Upgrade git-subrepo installation"""
        # This is mainly for bash-based installations
        print("The upgrade command is not implemented for the Python version.")
        print("Please update your git-subrepo installation manually.")

    # ===== Subrepo Worker Functions =====

    def subrepo_clone(self):
        """Clone implementation"""
        # Check if we can clone
        self.FAIL = False
        self.run_git(['rev-parse', 'HEAD'])
        if not self.OK:
            self.error("You can't clone into an empty repository")
        self.FAIL = True

        # Turn off force unless really a reclone
        if self.force_wanted and not os.path.isfile(self.gitrepo):
            self.force_wanted = False

        reclone_up_to_date = False
        if self.force_wanted:
            self.o("--force indicates a reclone.")
            self.CALL(self.subrepo_fetch)
            # Read .gitrepo after fetching (to avoid fetching old branch)
            if os.path.isfile(self.gitrepo):
                self.read_gitrepo_file()
            self.o("Check if we already are up to date.")
            if self.upstream_head_commit == self.subrepo_commit:
                return True

            self.o("Remove the old subdir.")
            self.run_git(['rm', '-r', '--', self.subdir])

            if not self.override_branch:
                self.o("Determine the upstream head branch.")
                branch = self.get_upstream_head_branch()
                self.subrepo_branch = branch
                self.override_branch = branch
        else:
            self.assert_subdir_empty()
            if not self.subrepo_branch:
                self.o("Determine the upstream head branch.")
                self.subrepo_branch = self.get_upstream_head_branch()

            self.CALL(self.subrepo_fetch)

        self.o(f"Make the directory '{self.subdir}/' for the clone.")
        os.makedirs(self.subdir, exist_ok=True)

        self.o(f"Commit the new '{self.subdir}/' content.")
        self.subrepo_commit_ref = self.upstream_head_commit
        self.CALL(self.do_subrepo_commit)

        return reclone_up_to_date

    def subrepo_init(self):
        """Initialize a subrepo"""
        branch_name = f"subrepo/{self.subref}"
        self.assert_subdir_ready_for_init()

        # For init, set subrepo_commit_ref only (no upstream yet)
        self.subrepo_commit_ref = self.original_head_commit

        self.o(f"Put info into '{self.subdir}/.gitrepo' file.")
        self.update_gitrepo_file()

        self.o(f"Add the new '{self.subdir}/.gitrepo' file.")
        self.run_git(['add', '-f', '--', self.gitrepo])

        self.o(f"Commit new subrepo to the '{self.original_head_branch}' branch.")
        commit_msg = self.get_commit_message()
        self.run_git(['commit', '-m', commit_msg])

        self.o(f"Create ref '{self.refs_subrepo_commit}'.")
        self.git_make_ref(self.refs_subrepo_commit, self.subrepo_commit_ref)

    def subrepo_pull(self):
        """Pull implementation"""
        self.CALL(self.subrepo_fetch)

        # If forced pull, then clone instead
        if self.force_wanted:
            self.CALL(self.subrepo_clone)
            return

        # Check if already up to date
        if self.upstream_head_commit == self.subrepo_commit and not self.update_wanted:
            self.OK = False
            self.CODE = -1
            return

        branch_name = f'subrepo/{self.subref}'
        self.git_delete_branch(branch_name)

        self.subrepo_commit_ref = branch_name

        self.o(f"Create subrepo branch '{branch_name}'.")
        self.CALL(self.subrepo_branch_create, branch_name)

        # Change to worktree
        os.chdir(self.worktree)

        if self.join_method == 'rebase':
            self.o(f"Rebase changes to {self.refs_subrepo_fetch}")
            self.FAIL = False
            self.OUT = True
            self.run_git(['rebase', self.refs_subrepo_fetch, branch_name])
            if not self.OK:
                self.say("The \"git rebase\" command failed:")
                self.say("")
                self.say("  " + self.output.replace('\n', '\n  '))
                self.CODE = 1
                return
            self.FAIL = True
            self.OUT = False
        else:
            self.o(f"Merge in changes from {self.refs_subrepo_fetch}")
            self.FAIL = False
            self.run_git(['merge', self.refs_subrepo_fetch])
            if not self.OK:
                self.say("The \"git merge\" command failed:")
                self.say("")
                self.say("  " + self.output.replace('\n', '\n  '))
                self.CODE = 1
                return
            self.FAIL = True

        # Back to original directory
        self.o(f"Back to {self.start_pwd}")
        os.chdir(self.start_pwd)

        self.o(f"Create ref '{self.refs_subrepo_branch}' for branch '{branch_name}'.")
        self.git_make_ref(self.refs_subrepo_branch, branch_name)

        self.o(f"Commit the new '{self.subrepo_commit_ref}' content.")
        self.CALL(self.do_subrepo_commit)

    def subrepo_push(self):
        """Push implementation"""
        branch_name = getattr(self, 'branch', None)
        new_upstream = False
        branch_created = False

        if not branch_name:
            self.FAIL = False
            self.OUT = False
            self.CALL(self.subrepo_fetch)

            if not self.OK:
                # Check if pushing to new upstream
                if re.search(r"(^|\n)fatal: couldn't find remote ref ", self.output.lower()):
                    self.o(f"Pushing to new upstream: {self.subrepo_remote} ({self.subrepo_branch}).")
                    new_upstream = True
                else:
                    self.error(f"Fetch for push failed: {self.output}")
            else:
                # Check that we are up to date
                self.o("Check upstream head against .gitrepo commit.")
                if not self.force_wanted:
                    if self.upstream_head_commit != self.subrepo_commit:
                        self.error("There are new changes upstream, you need to pull first.")

            self.FAIL = True
            self.OUT = False

            branch_name = f'subrepo/{self.subref}'
            self.worktree = os.path.join(self.GIT_TMP, branch_name)
            self.git_delete_branch(branch_name)

            if self.squash_wanted:
                self.o("Squash commits")
                self.subrepo_parent = 'HEAD^'

            self.o(f"Create subrepo branch '{branch_name}'.")
            self.CALL(self.subrepo_branch_create, branch_name)

            os.chdir(self.worktree)

            if self.join_method == 'rebase':
                self.o(f"Rebase changes to {self.refs_subrepo_fetch}")
                self.FAIL = False
                self.OUT = True
                self.run_git(['rebase', self.refs_subrepo_fetch, branch_name])
                if not self.OK:
                    self.say("The \"git rebase\" command failed:")
                    self.say("")
                    self.say("  " + self.output.replace('\n', '\n  '))
                    self.CODE = 1
                    return
                self.FAIL = True
                self.OUT = False

            branch_created = True
            os.chdir(self.start_pwd)
        else:
            if self.squash_wanted:
                self.error("Squash option (-s) can't be used with branch parameter")

        self.o(f"Make sure that '{branch_name}' exists.")
        if not self.git_branch_exists(branch_name):
            self.error(f"No subrepo branch '{branch_name}' to push.")

        self.o("Check if we have something to push")
        new_upstream_head_commit = self.run_git(['rev-parse', branch_name], capture=True).strip()
        if not new_upstream:
            if self.upstream_head_commit == new_upstream_head_commit:
                if branch_created:
                    self.o(f"Remove branch '{branch_name}'.")
                    self.git_delete_branch(branch_name)
                self.OK = False
                self.CODE = -2
                return

        if not self.force_wanted and not new_upstream:
            self.o(f"Make sure '{branch_name}' contains the '{self.refs_subrepo_fetch}' HEAD.")
            if not self.git_commit_in_rev_list(self.upstream_head_commit, branch_name):
                self.error(f"Can't commit: '{branch_name}' doesn't contain upstream HEAD: {self.upstream_head_commit}")

        force_flag = ' --force' if self.force_wanted else ''
        self.o(f"Push{force_flag} branch '{branch_name}' to '{self.subrepo_remote}' ({self.subrepo_branch}).")
        push_cmd = ['push']
        if self.force_wanted:
            push_cmd.append('--force')
        push_cmd.extend([self.subrepo_remote, f'{branch_name}:{self.subrepo_branch}'])
        self.run_git(push_cmd)

        self.o(f"Create ref '{self.refs_subrepo_push}' for branch '{branch_name}'.")
        self.git_make_ref(self.refs_subrepo_push, branch_name)

        if branch_created:
            self.o(f"Remove branch '{branch_name}'.")
            self.git_delete_branch(branch_name)

        self.o(f"Put updates into '{self.subdir}/.gitrepo' file.")
        self.upstream_head_commit = new_upstream_head_commit
        self.subrepo_commit_ref = self.upstream_head_commit
        self.update_gitrepo_file()

        # Commit the changes
        commit_message = self.wanted_commit_message or self.get_commit_message()

        if self.commit_msg_file:
            self.run_git(['commit', '--file', self.commit_msg_file])
        else:
            self.run_git(['commit', '-m', commit_message])

    def subrepo_fetch(self):
        """Fetch upstream content"""
        if self.subrepo_remote == 'none':
            self.error(f"Can't fetch subrepo. Remote is 'none' in '{self.subdir}/.gitrepo'.")

        branch_info = f"({self.subrepo_branch})" if self.subrepo_branch else ""
        self.o(f"Fetch the upstream: {self.subrepo_remote} {branch_info}.")

        # Build fetch command - only include branch if it's set
        fetch_cmd = ['fetch', '--no-tags', '--quiet', self.subrepo_remote]
        if self.subrepo_branch:
            fetch_cmd.append(self.subrepo_branch)

        self.run_git(fetch_cmd)
        if not self.OK:
            return

        self.o("Get the upstream subrepo HEAD commit.")
        self.OUT = True
        self.run_git(['rev-parse', 'FETCH_HEAD^0'])
        self.upstream_head_commit = self.output.strip()
        self.OUT = False

        self.o(f"Create ref '{self.refs_subrepo_fetch}'.")
        self.git_make_ref(self.refs_subrepo_fetch, 'FETCH_HEAD^0')

    def subrepo_branch_create(self, branch=None):
        """Create a subrepo branch"""
        if branch is None:
            branch = f'subrepo/{self.subref}'

        self.o(f"Check if the '{branch}' branch already exists.")
        if self.git_branch_exists(branch):
            return

        self.o(f"Subrepo parent: {self.subrepo_parent}")

        first_gitrepo_commit = None
        last_gitrepo_commit = None

        if self.subrepo_parent:
            # Check if parent is ancestor of HEAD
            self.FAIL = False
            self.run_git(['merge-base', '--is-ancestor', self.subrepo_parent, 'HEAD'])
            parent_is_ancestor = self.OK
            self.FAIL = True

            if not parent_is_ancestor:
                prev_merge_point = self.run_git(
                    ['log', '-1', '-G', 'commit =', '--format=%H', self.gitrepo],
                    capture=True
                ).strip()
                if prev_merge_point:
                    prev_merge_point = self.run_git(
                        ['log', '-1', '--format=%H', f'{prev_merge_point}^'],
                        capture=True
                    ).strip()
                self.error(f"""The last sync point (where upstream and the subrepo were equal) is not an ancestor.
This is usually caused by a rebase affecting that commit.
To recover set the subrepo parent in '{self.gitrepo}'
to '{prev_merge_point}'
and validate the subrepo by comparing with 'git subrepo branch {self.subdir}'""")

            # Get commit list
            self.o("Create new commits with parents into the subrepo fetch")
            self.OUT = True
            self.run_git(['rev-list', '--reverse', '--ancestry-path', '--topo-order',
                         f'{self.subrepo_parent}..HEAD'])
            commit_list = self.output.strip().split('\n')
            self.OUT = False

            prev_commit = None
            ancestor = None

            for commit in commit_list:
                self.o(f"Working on {commit}")

                # Get gitrepo commit reference
                self.FAIL = False
                self.OUT = True
                self.run_git(['config', '--blob', f'{commit}:{self.subdir}/.gitrepo', 'subrepo.commit'])
                gitrepo_commit = self.output.strip()
                self.FAIL = True

                if not gitrepo_commit:
                    self.o("Ignore commit, no .gitrepo file")
                    continue

                self.o(f".gitrepo reference commit: {gitrepo_commit}")

                # Check if direct child
                if ancestor:
                    is_direct_child = self.run_git(
                        ['show', '-s', '--pretty=format:%P', commit],
                        capture=True
                    )
                    if ancestor not in is_direct_child:
                        self.o(f"Ignore {commit}, it's not in the selected path")
                        continue

                ancestor = commit

                # Check for rebase
                self.o("Check for rebase")
                if self.git_rev_exists(self.refs_subrepo_fetch):
                    if not self.git_commit_in_rev_list(gitrepo_commit, self.refs_subrepo_fetch):
                        self.error(f"Local repository does not contain {gitrepo_commit}. Try to 'git subrepo fetch {self.subref}' or add the '-F' flag to always fetch the latest content.")

                # Find parents
                self.o("Find parents")
                first_parent = []
                if prev_commit:
                    first_parent = ['-p', prev_commit]

                second_parent = []
                if not first_gitrepo_commit:
                    first_gitrepo_commit = gitrepo_commit
                    second_parent = ['-p', gitrepo_commit]

                if self.join_method != 'rebase':
                    if gitrepo_commit != last_gitrepo_commit:
                        second_parent = ['-p', gitrepo_commit]
                        last_gitrepo_commit = gitrepo_commit

                # Create new commit
                self.o(f"Create a new commit {' '.join(first_parent)} {' '.join(second_parent)}")
                self.FAIL = False
                self.run_git(['cat-file', '-e', f'{commit}:{self.subdir}'])
                has_content = self.OK
                self.FAIL = True

                if has_content:
                    self.o("Create with content")
                    # Get author info
                    author_date = self.run_git(['log', '-1', '--date=default', '--format=%ad', commit], capture=True).strip()
                    author_email = self.run_git(['log', '-1', '--date=default', '--format=%ae', commit], capture=True).strip()
                    author_name = self.run_git(['log', '-1', '--date=default', '--format=%an', commit], capture=True).strip()

                    # Get commit message
                    commit_msg = self.run_git(['log', '-n', '1', '--date=default', '--format=%B', commit], capture=True)

                    # Create commit tree
                    env = os.environ.copy()
                    env['GIT_AUTHOR_DATE'] = author_date
                    env['GIT_AUTHOR_EMAIL'] = author_email
                    env['GIT_AUTHOR_NAME'] = author_name

                    tree_cmd = ['commit-tree', '-F', '-'] + first_parent + second_parent + [f'{commit}:{self.subdir}']
                    proc = subprocess.run(
                        ['git'] + tree_cmd,
                        input=commit_msg,
                        capture_output=True,
                        text=True,
                        env=env
                    )
                    prev_commit = proc.stdout.strip()
                else:
                    self.o("Create empty placeholder")
                    empty_tree = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'
                    prev_commit = self.run_git(
                        ['commit-tree', '-m', 'EMPTY'] + first_parent + second_parent + [empty_tree],
                        capture=True
                    ).strip()

            self.o(f"Create branch '{branch}' for this new commit set {prev_commit}.")
            self.run_git(['branch', branch, prev_commit])
        else:
            self.o("No parent setting, use the subdir content.")
            self.run_git(['branch', branch, 'HEAD'])
            # Run filter-branch quietly unless verbose
            self.FAIL = False
            if self.verbose_wanted:
                self.TTY = True
                self.run_git(['filter-branch', '-f', '--subdirectory-filter', self.subref, branch])
                self.TTY = False
            else:
                # Suppress all output
                result = subprocess.run(['git', 'filter-branch', '-f', '--subdirectory-filter',
                                       self.subref, branch],
                                      capture_output=True, check=False)
                if result.returncode != 0:
                    self.OK = False
            self.FAIL = True

        # Remove .gitrepo file from branch
        self.o(f"Remove the .gitrepo file from {first_gitrepo_commit}..{branch}")
        filter_range = branch
        if first_gitrepo_commit:
            filter_range = f'{first_gitrepo_commit}..{branch}'

        # Run filter-branch quietly unless verbose
        self.FAIL = False
        if self.verbose_wanted:
            self.run_git(['filter-branch', '-f', '--prune-empty', '--tree-filter',
                         'rm -f .gitrepo', '--', filter_range, '--first-parent'])
        else:
            # Suppress all output
            result = subprocess.run(['git', 'filter-branch', '-f', '--prune-empty', '--tree-filter',
                                   'rm -f .gitrepo', '--', filter_range, '--first-parent'],
                                  capture_output=True, check=False)
            if result.returncode != 0:
                self.OK = False
        self.FAIL = True

        self.git_create_worktree(branch)

        self.o(f"Create ref '{self.refs_subrepo_branch}'.")
        self.git_make_ref(self.refs_subrepo_branch, branch)

    def do_subrepo_commit(self):
        """Commit a subrepo branch"""
        self.o(f"Check that '{self.subrepo_commit_ref}' exists.")
        if not self.git_rev_exists(self.subrepo_commit_ref):
            self.error(f"Commit ref '{self.subrepo_commit_ref}' does not exist.")

        if not self.force_wanted:
            upstream = self.upstream_head_commit
            self.o(f"Make sure '{self.subrepo_commit_ref}' contains the upstream HEAD.")
            if not self.git_commit_in_rev_list(upstream, self.subrepo_commit_ref):
                self.error(f"Can't commit: '{self.subrepo_commit_ref}' doesn't contain upstream HEAD.")

        # Check if subdir has files
        has_files = self.run_git(['ls-files', '--', self.subdir], capture=True).strip()
        if has_files:
            self.o("Remove old content of the subdir.")
            self.run_git(['rm', '-r', '--', self.subdir])

        self.o(f"Put remote subrepo content into '{self.subdir}/'.")
        self.run_git(['read-tree', f'--prefix={self.subdir}', '-u', self.subrepo_commit_ref])

        self.o(f"Put info into '{self.subdir}/.gitrepo' file.")
        self.update_gitrepo_file()
        self.run_git(['add', '-f', '--', self.gitrepo])

        commit_message = self.wanted_commit_message or self.get_commit_message()

        edit_flag = ['--edit'] if self.edit_wanted else []

        self.o(f"Commit to the '{self.original_head_branch}' branch.")
        if self.original_head_commit != 'none':
            if self.commit_msg_file:
                self.run_git(['commit'] + edit_flag + ['--file', self.commit_msg_file])
            else:
                self.run_git(['commit'] + edit_flag + ['-m', commit_message])
        else:
            # Empty repo case
            self.OUT = True
            self.run_git(['write-tree'])
            tree = self.output.strip()
            self.OUT = False

            if self.commit_msg_file:
                self.OUT = True
                commit_cmd = ['commit-tree'] + edit_flag + ['--file', self.commit_msg_file, tree]
                self.run_git(commit_cmd)
                commit_sha = self.output.strip()
                self.OUT = False
            else:
                self.OUT = True
                self.run_git(['commit-tree'] + edit_flag + ['-m', commit_message, tree])
                commit_sha = self.output.strip()
                self.OUT = False

            self.run_git(['reset', '--hard', commit_sha])

        # Clean up worktree
        self.git_remove_worktree()

        self.o(f"Create ref '{self.refs_subrepo_commit}'.")
        self.git_make_ref(self.refs_subrepo_commit, self.subrepo_commit_ref)

    def subrepo_status(self):
        """Get subrepo status"""
        output = []

        if not self.command_arguments:
            self.get_all_subrepos()
            count = len(self.subrepos)
            if not self.quiet_wanted:
                if count == 0:
                    return "No subrepos.\n"
                else:
                    s = 's' if count != 1 else ''
                    output.append(f"{count} subrepo{s}:\n")
        else:
            self.subrepos = self.command_arguments

        for subdir in self.subrepos:
            self.subdir = subdir
            self.check_and_normalize_subdir()
            self.encode_subdir()

            gitrepo = f'{subdir}/.gitrepo'
            if not os.path.isfile(gitrepo):
                output.append(f"'{subdir}' is not a subrepo\n")
                continue

            self.refs_subrepo_fetch = f'refs/subrepo/{self.subref}/fetch'

            # Get upstream head commit if ref exists
            self.FAIL = False
            upstream_head = self.run_git(['rev-parse', '--short', self.refs_subrepo_fetch], capture=True).strip()
            self.FAIL = True

            self.subrepo_remote = None
            self.subrepo_branch = None
            self.gitrepo = gitrepo
            self.read_gitrepo_file()

            if self.fetch_wanted:
                self.subrepo_fetch()

            if self.quiet_wanted:
                output.append(f"{subdir}\n")
                continue

            output.append(f"Git subrepo '{subdir}':\n")

            if self.git_branch_exists(f'subrepo/{self.subref}'):
                output.append(f"  Subrepo Branch:  subrepo/{self.subref}\n")

            # Check for remote
            remote = f'subrepo/{self.subref}'
            self.FAIL = False
            self.OUT = True
            self.run_git(['config', f'remote.{remote}.url'])
            if self.output.strip():
                output.append(f"  Remote Name:     subrepo/{self.subref}\n")
            self.FAIL = True
            self.OUT = False

            output.append(f"  Remote URL:      {self.subrepo_remote}\n")
            if upstream_head:
                output.append(f"  Upstream Ref:    {upstream_head}\n")
            output.append(f"  Tracking Branch: {self.subrepo_branch}\n")

            if self.subrepo_commit:
                short_commit = self.run_git(['rev-parse', '--short', self.subrepo_commit], capture=True).strip()
                output.append(f"  Pulled Commit:   {short_commit}\n")

            if self.subrepo_parent:
                short_parent = self.run_git(['rev-parse', '--short', self.subrepo_parent], capture=True).strip()
                output.append(f"  Pull Parent:     {short_parent}\n")

            # Check for worktree
            worktree_list = self.run_git(['worktree', 'list'], capture=True)
            for line in worktree_list.split('\n'):
                if f'{self.GIT_TMP}/subrepo/{subdir}' in line:
                    output.append(f"  Worktree: {line}\n")

            if self.verbose_wanted:
                output.append(self.status_refs())

            output.append("\n")

        return ''.join(output)

    def status_refs(self):
        """Show refs for status"""
        output = []
        show_ref = self.run_git(['show-ref'], capture=True)

        for line in show_ref.split('\n'):
            m = re.match(rf'^([0-9a-f]+)\s+refs/subrepo/{self.subref}/([a-z]+)', line)
            if m:
                sha1_full = m.group(1)
                sha1 = self.run_git(['rev-parse', '--short', sha1_full], capture=True).strip()
                ref_type = m.group(2)
                ref = f'refs/subrepo/{self.subref}/{ref_type}'

                if ref_type == 'branch':
                    output.append(f"    Branch Ref:    {sha1} ({ref})\n")
                elif ref_type == 'commit':
                    output.append(f"    Commit Ref:    {sha1} ({ref})\n")
                elif ref_type == 'fetch':
                    output.append(f"    Fetch Ref:     {sha1} ({ref})\n")
                elif ref_type == 'pull':
                    output.append(f"    Pull Ref:      {sha1} ({ref})\n")
                elif ref_type == 'push':
                    output.append(f"    Push Ref:      {sha1} ({ref})\n")

        if output:
            return "  Refs:\n" + ''.join(output)
        return ""

    def subrepo_clean(self):
        """Clean subrepo branches and refs"""
        clean_list = []
        branch = f'subrepo/{self.subref}'
        ref = f'refs/heads/{branch}'
        self.worktree = os.path.join(self.GIT_TMP, branch)

        self.o(f"Clean {self.subdir}")
        self.git_remove_worktree()

        if self.git_branch_exists(branch):
            self.o(f"Remove branch '{branch}'.")
            self.run_git(['update-ref', '-d', ref])
            clean_list.append(f"branch '{branch}'")

        if self.force_wanted:
            self.o("Remove all subrepo refs.")
            suffix = '' if self.all_wanted else f'{self.subref}/'

            show_ref = self.run_git(['show-ref'], capture=True)
            for line in show_ref.split('\n'):
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    ref = parts[1]
                    if ref.startswith(f'refs/subrepo/{suffix}'):
                        self.run_git(['update-ref', '-d', ref])
                    elif ref.startswith(f'refs/original/refs/heads/subrepo/{suffix}'):
                        self.run_git(['update-ref', '-d', ref])

        return clean_list

    # ===== Support Functions =====

    def command_init(self):
        """Initialize command processing"""
        os.environ['GIT_SUBREPO_RUNNING'] = str(os.getpid())
        os.environ['GIT_SUBREPO_COMMAND'] = self.command

        pager = os.getenv('GIT_SUBREPO_PAGER') or os.getenv('PAGER') or 'less'
        if pager == 'less':
            os.environ['GIT_SUBREPO_PAGER'] = 'less -FRX'
        else:
            os.environ['GIT_SUBREPO_PAGER'] = pager

    def command_prepare(self):
        """Prepare for command execution"""
        if self.git_rev_exists('HEAD'):
            self.git_get_head_branch_commit()
        self.original_head_commit = self.output.strip() if self.output else 'none'

    def command_setup(self, params):
        """Setup command with parameters"""
        self.get_params(params)
        self.check_and_normalize_subdir()
        self.encode_subdir()
        self.gitrepo = f'{self.subdir}/.gitrepo'

        # Check for existing worktree
        if not self.force_wanted:
            self.o(f"Check for worktree with branch subrepo/{self.subdir}")
            worktree_list = self.run_git(['worktree', 'list'], capture=True)

            has_worktree = False
            worktree_path = None
            for line in worktree_list.split('\n'):
                if f'[subrepo/{self.subdir}]' in line:
                    has_worktree = True
                    worktree_path = line.split()[0]
                    break

            if self.command in ['commit'] and not has_worktree:
                self.error("There is no worktree available, use the branch command first")
            elif self.command not in ['branch', 'clean', 'commit', 'push'] and has_worktree:
                if os.path.exists(self.gitrepo):
                    self.error(f"""There is already a worktree with branch subrepo/{self.subdir}.
Use the --force flag to override this check or perform a subrepo clean
to remove the worktree.""")
                else:
                    self.error(f"""There is already a worktree with branch subrepo/{self.subdir}.
Use the --force flag to override this check or remove the worktree with
1. rm -rf {worktree_path}
2. git worktree prune
""")

        # Set refs
        self.refs_subrepo_branch = f'refs/subrepo/{self.subref}/branch'
        self.refs_subrepo_commit = f'refs/subrepo/{self.subref}/commit'
        self.refs_subrepo_fetch = f'refs/subrepo/{self.subref}/fetch'
        self.refs_subrepo_push = f'refs/subrepo/{self.subref}/push'

        # Read .gitrepo file if not clone/init
        if self.command not in ['clone', 'init']:
            self.read_gitrepo_file()

    def get_params(self, params):
        """Parse command parameters"""
        i = 0
        num = len(self.command_arguments)

        for arg in params:
            value = self.command_arguments[i] if i < num else None

            # Required parameter
            if arg.startswith('+'):
                param_name = arg[1:]
                if i >= num:
                    self.usage_error(f"Command '{self.command}' requires arg '{param_name}'.")
                setattr(self, param_name, value)
            # Optional with default function
            elif ':' in arg:
                param_name, default_func = arg.split(':', 1)
                if i < num:
                    setattr(self, param_name, value)
                else:
                    # Call default function
                    getattr(self, default_func)()
            # Optional
            else:
                if i < num:
                    setattr(self, arg, value)

            i += 1

        # Check for extra arguments
        if num > i:
            extra = ' '.join(self.command_arguments[i:])
            self.error(f"Unknown argument(s) '{extra}' for '{self.command}' command.")

    def guess_subdir(self):
        """Guess subdirectory name from remote URL"""
        dir_name = self.subrepo_remote
        dir_name = dir_name.rstrip('/')
        if dir_name.endswith('.git'):
            dir_name = dir_name[:-4]
        dir_name = os.path.basename(dir_name)

        if not re.match(r'^[-_a-zA-Z0-9]+$', dir_name):
            self.error(f"Can't determine subdir from '{self.subrepo_remote}'.")

        self.subdir = dir_name
        self.check_and_normalize_subdir()
        self.encode_subdir()

    def check_and_normalize_subdir(self):
        """Normalize subdir path"""
        if not self.subdir:
            self.error("subdir not set")

        if self.subdir.startswith('/') or (len(self.subdir) > 1 and self.subdir[1] == ':'):
            self.usage_error(f"The subdir '{self.subdir}' should not be absolute path.")

        # Remove leading ./
        if self.subdir.startswith('./'):
            self.subdir = self.subdir[2:]

        # Remove trailing /
        self.subdir = self.subdir.rstrip('/')

        # Compress multiple slashes
        if '//' in self.subdir:
            self.subdir = re.sub(r'/+', '/', self.subdir)

    def encode_subdir(self):
        """Encode subdir as valid git ref"""
        self.subref = self.subdir

        # Check if already valid
        try:
            subprocess.run(
                ['git', 'check-ref-format', f'subrepo/{self.subref}'],
                check=True, capture_output=True
            )
            return
        except subprocess.CalledProcessError:
            pass

        # Need to encode
        subref = self.subref

        # Escape %
        subref = subref.replace('%', '%25')

        # Handle dots and .lock
        subref = '/' + subref + '/'
        subref = subref.replace('/.', '/%2e')
        subref = subref.replace('.lock/', '%2elock/')
        subref = subref.strip('/')

        # Handle consecutive dots
        subref = subref.replace('..', '%2e%2e')
        subref = subref.replace('%2e.', '%2e%2e')
        subref = subref.replace('.%2e', '%2e%2e')

        # Encode special characters
        for i in range(1, 32):
            char = chr(i)
            encoded = f'%{i:02x}'
            subref = subref.replace(char, encoded)

        subref = subref.replace('\x7f', '%7f')
        subref = subref.replace(' ', '%20')
        subref = subref.replace('~', '%7e')
        subref = subref.replace('^', '%5e')
        subref = subref.replace(':', '%3a')
        subref = subref.replace('?', '%3f')
        subref = subref.replace('*', '%2a')
        subref = subref.replace('[', '%5b')
        subref = subref.replace('\n', '%0a')

        # Compress slashes
        if '//' in subref:
            subref = re.sub(r'/+', '/', subref)

        # Handle trailing dot
        if subref.endswith('.'):
            subref = subref[:-1] + '%2e'

        # Handle @{
        subref = subref.replace('@{', '%40{')

        # Handle backslash
        subref = subref.replace('\\', '%5c')

        # Normalize
        try:
            result = subprocess.run(
                ['git', 'check-ref-format', '--normalize', '--allow-onelevel', subref],
                capture_output=True, text=True, check=True
            )
            self.subref = result.stdout.strip()
        except subprocess.CalledProcessError:
            self.error(f"Can't determine valid subref from '{self.subdir}'.")

    def read_gitrepo_file(self):
        """Read .gitrepo file"""
        self.gitrepo = f'{self.subdir}/.gitrepo'

        if not os.path.isfile(self.gitrepo):
            self.error(f"No '{self.gitrepo}' file.")

        # Read values using git config
        if not self.subrepo_remote:
            self.SAY = False
            self.OUT = True
            self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.remote'])
            self.subrepo_remote = self.output.strip()
            self.SAY = True
            self.OUT = False

        if not self.subrepo_branch:
            self.SAY = False
            self.OUT = True
            self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.branch'])
            self.subrepo_branch = self.output.strip()
            self.SAY = True
            self.OUT = False

        self.FAIL = False
        self.SAY = False
        self.OUT = True
        self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.commit'])
        self.subrepo_commit = self.output.strip() if self.OK else ''
        self.FAIL = True
        self.SAY = True
        self.OUT = False

        self.FAIL = False
        self.SAY = False
        self.OUT = True
        self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.parent'])
        self.subrepo_parent = self.output.strip() if self.OK else ''
        self.FAIL = True
        self.SAY = True
        self.OUT = False

        # Read method
        self.FAIL = False
        self.SAY = False
        self.OUT = True
        self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.method'])
        method = self.output.strip()
        if method == 'rebase':
            self.join_method = 'rebase'
        else:
            self.join_method = 'merge'
        self.FAIL = True
        self.SAY = True
        self.OUT = False

        # Read former if no parent
        if not self.subrepo_parent:
            self.FAIL = False
            self.SAY = False
            self.OUT = True
            self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.former'])
            self.subrepo_former = self.output.strip()
            self.FAIL = True
            self.SAY = True
            self.OUT = False

    def update_gitrepo_file(self):
        """Update .gitrepo file"""
        newfile = False

        if not os.path.exists(self.gitrepo):
            # Try to recreate from parent commit
            self.FAIL = False
            self.run_git(['cat-file', '-e', f'{self.original_head_commit}:{self.gitrepo}'])

            if self.OK:
                self.o(f"Try to recreate gitrepo file from {self.original_head_commit}")
                content = self.run_git(['cat-file', '-p', f'{self.original_head_commit}:{self.gitrepo}'], capture=True)
                with open(self.gitrepo, 'w') as f:
                    f.write(content)
            else:
                newfile = True
                with open(self.gitrepo, 'w') as f:
                    f.write("""; DO NOT EDIT (unless you know what you are doing)
;
; This subdirectory is a git "subrepo", and this file is maintained by the
; git-subrepo command. See https://github.com/ingydotnet/git-subrepo#readme
;
""")
            self.FAIL = True

        # Update fields
        # For push/clone with --remote/--branch, implicitly update even without -u flag
        should_update_remote = newfile or (self.update_wanted and self.override_remote) or \
                               (self.command in ['push', 'clone'] and self.override_remote)
        should_update_branch = newfile or (self.update_wanted and self.override_branch) or \
                               (self.command in ['push', 'clone'] and self.override_branch)

        if should_update_remote:
            self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.remote', self.subrepo_remote])

        if should_update_branch:
            self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.branch', self.subrepo_branch])

        # Write commit only if we have an upstream (not 'none')
        if self.upstream_head_commit:
            self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.commit', self.upstream_head_commit])

        # Only write parent when at head of upstream
        if self.upstream_head_commit and self.subrepo_commit_ref:
            self.OUT = True
            self.run_git(['rev-parse', self.subrepo_commit_ref])
            commit_ref_sha = self.output.strip()
            self.OUT = False

            self.o(f"{self.upstream_head_commit} == {commit_ref_sha}")
            if self.upstream_head_commit == commit_ref_sha:
                self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.parent', self.original_head_commit])

        # Set method
        join_method = self.join_method or 'merge'
        self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.method', join_method])

        self.run_git(['config', f'--file={self.gitrepo}', 'subrepo.cmdver', VERSION])
        self.run_git(['add', '-f', '--', self.gitrepo])

    # ===== Environment Assertions =====

    def assert_environment_ok(self):
        """Check that environment is suitable"""
        # Check git exists
        if not shutil.which('git'):
            self.error("Can't find your 'git' command in '$PATH'.")

        # Get git version
        result = subprocess.run(['git', '--version'], capture_output=True, text=True)
        version_match = re.search(r'(\d+\.\d+\.\d+)', result.stdout)
        if version_match:
            self.git_version = version_match.group(1)
        else:
            self.error("Can't determine git version")

        # Check git version
        if not self.version_check(self.git_version, REQUIRED_GIT_VERSION):
            self.error(f"Requires git version {REQUIRED_GIT_VERSION} or higher; you have '{self.git_version}'.")

    def assert_repo_is_ready(self):
        """Check that repository is ready"""
        # Skip for info commands
        if self.command in ['help', 'version', 'upgrade']:
            return

        # Must be inside git repo
        try:
            subprocess.run(['git', 'rev-parse', '--git-dir'],
                         check=True, capture_output=True)
        except subprocess.CalledProcessError:
            self.error("Not inside a git repository.")

        # Get git common dir for GIT_TMP
        try:
            result = subprocess.run(['git', 'rev-parse', '--git-common-dir'],
                                  capture_output=True, text=True, check=True)
            git_common_dir = result.stdout.strip()
        except subprocess.CalledProcessError:
            git_common_dir = '.git'

        self.GIT_TMP = os.path.join(git_common_dir, 'tmp')

        # Get original branch
        self.git_get_head_branch_name()
        self.original_head_branch = self.output.strip() if self.output else None

        # Check not on subrepo branch
        if self.original_head_branch and self.original_head_branch.startswith('subrepo/'):
            self.error(f"Can't '{self.command}' while subrepo branch is checked out.")

        # Must be on a branch
        if self.original_head_branch in ['HEAD', '', None]:
            self.error("Must be on a branch to run this command.")

        # Must be in work tree
        try:
            result = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'],
                                  capture_output=True, text=True, check=True)
            if result.stdout.strip() != 'true':
                self.error(f"Can't 'subrepo {self.command}' outside a working tree.")
        except subprocess.CalledProcessError:
            self.error(f"Can't 'subrepo {self.command}' outside a working tree.")

        # HEAD must exist (except for clone)
        if self.command != 'clone':
            try:
                subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'],
                             check=True, capture_output=True)
            except subprocess.CalledProcessError:
                self.error("HEAD does not exist")

        # Check working copy is clean
        self.assert_working_copy_is_clean()

        # Must run from top level
        try:
            result = subprocess.run(['git', 'rev-parse', '--show-prefix'],
                                  capture_output=True, text=True, check=True)
            if result.stdout.strip():
                self.error("Need to run subrepo command from top level directory of the repo.")
        except subprocess.CalledProcessError:
            pass

    def assert_working_copy_is_clean(self):
        """Ensure working copy has no uncommitted changes"""
        if self.command not in ['clone', 'init', 'pull', 'push', 'branch', 'commit']:
            return

        pwd = os.getcwd()
        self.o(f"Assert that working copy is clean: {pwd}")

        subprocess.run(['git', 'update-index', '-q', '--ignore-submodules', '--refresh'],
                      capture_output=True)

        # Check for unstaged changes
        result = subprocess.run(['git', 'diff-files', '--quiet', '--ignore-submodules'],
                              capture_output=True)
        if result.returncode != 0:
            self.error(f"Can't {self.command} subrepo. Unstaged changes. ({pwd})")

        # Check working tree changes
        if self.command != 'clone' or self.git_rev_exists('HEAD'):
            result = subprocess.run(['git', 'diff-index', '--quiet', '--ignore-submodules', 'HEAD'],
                                  capture_output=True)
            if result.returncode != 0:
                self.error(f"Can't {self.command} subrepo. Working tree has changes. ({pwd})")

            result = subprocess.run(['git', 'diff-index', '--quiet', '--cached', '--ignore-submodules', 'HEAD'],
                                  capture_output=True)
            if result.returncode != 0:
                self.error(f"Can't {self.command} subrepo. Index has changes. ({pwd})")
        else:
            # Empty repo
            result = subprocess.run(['git', 'ls-files'], capture_output=True, text=True)
            if result.stdout.strip():
                self.error(f"Can't {self.command} subrepo. Index has changes. ({pwd})")

    def assert_subdir_empty(self):
        """Ensure subdirectory is empty or doesn't exist"""
        if os.path.exists(self.subdir):
            if os.listdir(self.subdir):
                self.error(f"The subdir '{self.subdir}' exists and is not empty.")

    def assert_subdir_ready_for_init(self):
        """Check subdir is ready for init"""
        if not os.path.exists(self.subdir):
            self.error(f"The subdir '{self.subdir}' does not exist.")

        if os.path.exists(f'{self.subdir}/.gitrepo'):
            self.error(f"The subdir '{self.subdir}' is already a subrepo.")

        # Check that subdir is part of repo
        result = subprocess.run(['git', 'log', '-1', '--date=default', '--', self.subdir],
                              capture_output=True, text=True)
        if not result.stdout.strip():
            self.error(f"The subdir '{self.subdir}' is not part of this repo.")

    # ===== Git Helper Functions =====

    def git_branch_exists(self, branch):
        """Check if branch exists"""
        return self.git_rev_exists(f'refs/heads/{branch}')

    def git_rev_exists(self, rev):
        """Check if revision exists"""
        if not rev:
            return False
        result = subprocess.run(['git', 'rev-list', rev, '-1'],
                              capture_output=True)
        return result.returncode == 0

    def git_get_head_branch_name(self):
        """Get current branch name"""
        result = subprocess.run(['git', 'symbolic-ref', '--short', '--quiet', 'HEAD'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            name = result.stdout.strip()
            if name != 'HEAD':
                self.output = name
                return
        self.output = ""

    def git_get_head_branch_commit(self):
        """Get HEAD commit"""
        result = subprocess.run(['git', 'rev-parse', 'HEAD'],
                              capture_output=True, text=True)
        self.output = result.stdout

    def git_commit_in_rev_list(self, commit, list_head):
        """Check if commit is in rev-list"""
        if not commit:
            return False
        result = subprocess.run(['git', 'rev-list', list_head],
                              capture_output=True, text=True)
        return commit in result.stdout

    def git_make_ref(self, ref_name, commit):
        """Create or update a ref"""
        result = subprocess.run(['git', 'rev-parse', commit],
                              capture_output=True, text=True)
        commit_sha = result.stdout.strip()
        self.run_git(['update-ref', ref_name, commit_sha])

    def git_create_worktree(self, branch):
        """Create a worktree for branch"""
        self.worktree = os.path.join(self.GIT_TMP, branch)
        self.run_git(['worktree', 'add', self.worktree, branch])

    def git_remove_worktree(self):
        """Remove worktree"""
        if not self.worktree:
            return

        self.o(f"Remove worktree: {self.worktree}")
        if os.path.isdir(self.worktree):
            self.o("Check worktree for unsaved changes")
            saved_pwd = os.getcwd()
            os.chdir(self.worktree)
            self.assert_working_copy_is_clean()
            os.chdir(saved_pwd)

            self.o(f"Clean up worktree {self.worktree}")
            shutil.rmtree(self.worktree)
            self.run_git(['worktree', 'prune'])

    def git_delete_branch(self, branch):
        """Delete a branch"""
        self.o(f"Deleting old '{branch}' branch.")
        self.git_remove_worktree()
        self.FAIL = False
        self.run_git(['branch', '-D', branch])
        self.FAIL = True

    # ===== Utility Functions =====

    def get_all_subrepos(self):
        """Find all subrepos in repository"""
        result = subprocess.run(['git', 'ls-files'],
                              capture_output=True, text=True)

        paths = []
        for line in result.stdout.split('\n'):
            if line.endswith('/.gitrepo'):
                path = line[:-9]  # Remove '/.gitrepo'
                paths.append(path)

        paths.sort()
        self.subrepos = []

        for path in paths:
            self.add_subrepo(path)

    def add_subrepo(self, path):
        """Add subrepo to list, avoiding subsubrepos unless ALL wanted"""
        if not self.ALL_wanted:
            for existing in self.subrepos:
                if path.startswith(f'{existing}/'):
                    return
        self.subrepos.append(path)

    def get_upstream_head_branch(self):
        """Determine upstream default branch"""
        self.OUT = True
        # Don't fail automatically - we want to provide a custom error message
        self.FAIL = False
        self.run_git(['ls-remote', '--symref', self.subrepo_remote])
        remotes = self.output
        self.OUT = False
        self.FAIL = True

        if not self.OK or not remotes:
            # Provide clean error message without git stderr
            self.error(f"Command failed: 'git ls-remote --symref {self.subrepo_remote}'.")

        # Parse: ref: refs/heads/master  HEAD
        for line in remotes.split('\n'):
            if line.startswith('ref:') and line.endswith('HEAD'):
                parts = line.split()
                if len(parts) >= 2:
                    ref = parts[1]
                    if ref.startswith('refs/heads/'):
                        return ref[11:]  # Remove 'refs/heads/'

        self.error("Problem finding remote default head branch.")

    def get_default_branch(self):
        """Get git's default branch name"""
        # Try git config
        result = subprocess.run(['git', 'config', '--get', 'init.defaultbranch'],
                              capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        # Check git version for init.defaultbranch support
        git_parts = self.git_version.split('.')
        git_major = int(git_parts[0])
        git_minor = int(git_parts[1]) if len(git_parts) > 1 else 0

        if git_major > 2 or (git_major == 2 and git_minor >= 28):
            return 'main'
        return 'master'

    def get_commit_message(self):
        """Generate commit message"""
        commit = 'none'
        if self.upstream_head_commit and self.git_rev_exists(self.upstream_head_commit):
            commit = self.run_git(['rev-parse', '--short', self.upstream_head_commit], capture=True).strip()

        args = []
        if self.all_wanted:
            args.append(self.subdir)
        args.extend(self.commit_msg_args)

        # Get command info
        command_remote = '???'
        command_commit = '???'
        # TODO: Implement get_command_info if needed

        merged = 'none'
        if hasattr(self, 'subrepo_commit_ref') and self.subrepo_commit_ref and self.git_rev_exists(self.subrepo_commit_ref):
            merged = self.run_git(['rev-parse', '--short', self.subrepo_commit_ref], capture=True).strip()

        is_merge = ''
        if self.command != 'push':
            # Check if merge commit
            if hasattr(self, 'subrepo_commit_ref') and self.subrepo_commit_ref:
                result = subprocess.run(['git', 'show', '--summary', self.subrepo_commit_ref],
                                      capture_output=True, text=True)
                if 'Merge:' in result.stdout:
                    is_merge = ' (merge)'

        args_str = ' '.join(args)

        return f"""git subrepo {self.command}{is_merge} {args_str}

subrepo:
  subdir:   "{self.subdir}"
  merged:   "{merged}"
upstream:
  origin:   "{self.subrepo_remote}"
  branch:   "{self.subrepo_branch}"
  commit:   "{commit}"
git-subrepo:
  version:  "{VERSION}"
  origin:   "{command_remote}"
  commit:   "{command_commit}"
"""

    def error_join(self):
        """Print error message for join failures"""
        msg = f"""
You will need to finish the {self.command} by hand. A new working tree has been
created at {self.worktree} so that you can resolve the conflicts
shown in the output above.

This is the common conflict resolution workflow:

  1. cd {self.worktree}
  2. Resolve the conflicts (see "git status").
  3. "git add" the resolved files.
"""

        if self.join_method == 'rebase':
            msg += """  4. git rebase --continue
"""
        else:
            msg += """  4. git commit
"""

        msg += f"""  5. If there are more conflicts, restart at step 2.
  6. cd {self.start_pwd}
"""

        branch_name = getattr(self, 'branch', None) or f'subrepo/{self.subdir}'
        if self.command == 'push':
            msg += f"""  7. git subrepo push {self.subdir} {branch_name}
"""
        else:
            if self.commit_msg_file:
                msg += f"""  7. git subrepo commit --file={self.commit_msg_file} {self.subdir}
"""
            else:
                msg += f"""  7. git subrepo commit {self.subdir}
"""

        if self.command == 'pull' and self.join_method == 'rebase':
            msg += f"""
After you have performed the steps above you can push your local changes
without repeating the rebase by:
  1. git subrepo push {self.subdir} {branch_name}

"""

        msg += f"""See "git help {self.join_method}" for details.

Alternatively, you can abort the {self.command} and reset back to where you started:

  1. git subrepo clean {self.subdir}

See "git help subrepo" for more help.
"""
        print(msg, file=sys.stderr)

    def version_check(self, got, want):
        """Check version is sufficient"""
        got_parts = got.split('.')
        want_parts = want.split('.')

        # Pad to 3 parts
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
                if got_nums[2] >= want_nums[2]:
                    return True
        return False

    def run_git(self, args, capture=False, suppress_stderr=False):
        """Run a git command"""
        cmd = ['git'] + args

        if self.debug_wanted and self.SAY:
            self.say(f">>> {' '.join(cmd)}")

        self.OK = True

        try:
            if capture:
                stderr = subprocess.DEVNULL if suppress_stderr else subprocess.PIPE
                result = subprocess.run(cmd, capture_output=False, stdout=subprocess.PIPE,
                                      stderr=stderr, text=True, check=False)
                return result.stdout
            elif self.OUT:
                stderr = subprocess.DEVNULL if suppress_stderr else subprocess.PIPE
                result = subprocess.run(cmd, capture_output=False, stdout=subprocess.PIPE,
                                      stderr=stderr, text=True, check=False)
                self.output = result.stdout
                if result.returncode != 0:
                    self.OK = False
                    if self.FAIL:
                        self.error(f"Command failed: '{' '.join(cmd)}'.\n{result.stderr if not suppress_stderr else ''}")
                return result.stdout
            elif self.TTY or (self.debug_wanted and not self.OUT):
                stderr = subprocess.DEVNULL if suppress_stderr else None
                result = subprocess.run(cmd, stderr=stderr, check=False)
                if result.returncode != 0:
                    self.OK = False
                    if self.FAIL:
                        self.error(f"Command failed: '{' '.join(cmd)}'.")
            else:
                if suppress_stderr:
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                          text=True, check=False)
                    self.output = result.stdout
                else:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                    self.output = result.stdout + result.stderr
                if result.returncode != 0:
                    self.OK = False
                    if self.FAIL:
                        self.error(f"Command failed: '{' '.join(cmd)}'.\n{self.output}")
        except Exception as e:
            self.OK = False
            if self.FAIL:
                self.error(f"Command failed: '{' '.join(cmd)}'.\n{str(e)}")

    def CALL(self, func, *args, **kwargs):
        """Call a function with increased indent"""
        old_indent = self.INDENT
        self.INDENT = "  " + self.INDENT
        try:
            func(*args, **kwargs)
        finally:
            self.INDENT = old_indent

    def o(self, msg):
        """Print verbose message"""
        if self.verbose_wanted:
            print(f"{self.INDENT}* {msg}")

    def say(self, msg):
        """Print message unless quiet"""
        if not self.quiet_wanted:
            print(msg)

    def error(self, msg):
        """Print error and exit"""
        print(f"git-subrepo: {msg}", file=sys.stderr)
        raise GitSubrepoError(msg)

    def usage_error(self, msg):
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
