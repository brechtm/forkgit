#!/usr/bin/env python3

import errno
import os
import re
import shlex
import subprocess
import sys
import stat

from pathlib import Path
from configparser import ConfigParser
from shutil import which
from subprocess import run


LOCAL_GIT_BINARY = 'git.exe' if os.name == 'nt' else 'git'
EXIT_COMMAND_NOT_FOUND = 127
EXIT_SSHFS_HOST_MISMATCH = 1
SSH_BINARY = 'ssh'


def listtoshc(arglist):
    """
    Convert a list of command line arguments to a string that can be
    executed by POSIX shells without interpolation of special characters.

    Example:
    >>> print(listtoshc(['cat', '.profile', '`rm -rf *`']))
    cat .profile '`rm -rf *`'
    """
    return ' '.join(map(shlex.quote, arglist))


def fake_section_heading(fp):
    yield '[fakesection]\n'
    yield from fp

    
def read_dotforkgit(path):
    dotforkgit = Path(path) / '.forkgit'
    if not dotforkgit.exists():
        return {}
    cp = ConfigParser()
    cp.read_file(fake_section_heading(dotforkgit.open()))
    return cp['fakesection']


def main():
    command, originalargs = os.path.basename(sys.argv[0]), sys.argv[1:]
    #print(command, originalargs)
    envpassthrough = dict()
    environment = dict(os.environ)
    stdin_is_pipe = stat.S_ISFIFO(os.fstat(0).st_mode)

    # Configuration defaults
    translate_all_arguments = False
    preserve_isatty = False
    coerce_remote_execution = False

    local_root = os.getcwd()
    config = read_dotforkgit(local_root)

    git_dir = config.get('git-dir')
    if git_dir:
        environment['GIT_DIR'] = git_dir

    # Figure out where the current working directory is on the remote system.
    remote_host = config.get('remote-host')
    if remote_host:
        remote_root = config['remote-root']
        sshlogin = remote_host
        remotepath = remote_root
        sshhost = sshlogin.split('@')[0] if '@' in sshlogin else sshlogin
    else:
        sshlogin = None


    if sshlogin and command == LOCAL_GIT_BINARY:
        preserve_isatty = True
        if originalargs in (['rev-parse', '--absolute-git-dir'],
                            ['rev-parse', '--show-toplevel']):
            print(os.getcwd())
            sys.exit()
        elif originalargs[0] == 'commit':
            for i, originalarg in enumerate(originalargs[1:], 1):
                if not originalarg.startswith('--file'):
                    continue
                arg, local_path = originalarg.split('=')
                remote_path = os.path.join('/tmp', os.path.basename(local_path))
                run(['scp', local_path, f'{sshlogin}:{remote_path}'], check=True)
                originalargs[i] = f'--file={remote_path}'
    
    # Fork checks the .git/logs/HEAD timestamp for highlighting the HEAD commit
    if ((command == LOCAL_GIT_BINARY and originalargs[0] in ['commit', 'fetch', 'pull'])
            and (sshlogin or git_dir == '.')):
        for logs_head in ('.git/logs/HEAD', 'logs/HEAD'):
            dotgit_logs_head = Path(local_root) / logs_head
            dotgit_logs_head.parent.mkdir(parents=True, exist_ok=True)
            dotgit_logs_head.touch()

    remoteargs = list()
    for argument in originalargs:
        remoteargs.append(argument)

    if sshlogin:
        # If the command should be executed on a remote server, generate the
        # execution string to pass into the shell.
        executed = listtoshc(['git'] + remoteargs)

        # Prepend environment variable declarations
        for variable, value in envpassthrough.items():
            executed = '%s=%s %s' % (variable, shlex.quote(value), executed)

        if remote_root:
            # If the current working directory is inside an SSHFS mount, cd
            # into the corresponding remote directory first. Why the brackets?
            # When data is piped into cd without cd being in a command group,
            # cd will not work:
            #
            #   ~% echo example | cd / && pwd
            #   /home/jameseric
            #   ~% echo example | { cd / && pwd; }
            #   /
            #
            quotedremotecwd = shlex.quote(remote_root)
            sshcommand = '{ cd %s && %s; }' % (quotedremotecwd, executed)
        else:
            sshcommand = executed

        ttys = [fd.isatty() for fd in (sys.stdin, sys.stdout, sys.stderr)]
        if any(ttys):
            ttyoption = '-t'
            if not preserve_isatty:
                # Only create a tty if stdin and stdout are attached a tty.
                ttyoption = '-t' if all(ttys[0:2]) else '-T'

            elif not all(ttys):
                # Do some kludgey stuff to make isatty for the remote process
                # match the what sshfsexec sees.
                if not ttys[0]:
                    sshcommand = 'stty -echo; /bin/cat | ' + sshcommand
                    ttyoption = '-tt'
                if not ttys[1]:
                    sshcommand += ' | /bin/cat'
                if not ttys[2]:
                    sshcommand = ('exec 3>&1; %s 2>&1 >&3 3>&- | /bin/cat >&2'
                        % sshcommand)

        else:
            ttyoption = '-T'

        argv = [SSH_BINARY, '-o', 'LogLevel=QUIET']
        if ttyoption == '-T':
            argv += ['-e', 'none']

        argv += [sshlogin, ttyoption, sshcommand]

    else:   # local checkout
        real_git = which(LOCAL_GIT_BINARY)
        try:
            this_git = __file__
        except NameError:
            this_git = sys.executable
        if real_git == this_git:
            raise ValueError("forkgit's git should not be in PATH!")
        if not real_git:
            raise SystemExit(EXIT_COMMAND_NOT_FOUND)
        argv = [real_git, *originalargs]

        # Older versions of Fork sets GIT_EXEC_PATH (why?), breaking forkgit for local checkouts
        # https://github.com/fork-dev/Tracker/issues/929#issuecomment-1373919511
        try:
            environment.pop('GIT_EXEC_PATH')
        except KeyError:
            pass

    process = run(argv, env=environment)
    raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
