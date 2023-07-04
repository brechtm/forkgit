forkgit
=======

forkgit is a git wrapper that enables [Fork](https://fork.dev/) to:
- open and interact with remote git checkouts over SSH
- set a [custom `.git` directory](https://git-scm.com/docs/git#Documentation/git.txt---git-dirltpathgt)
  for specific checkouts

Known issues with remote checkouts:
- removing untracked files doesn't work
- interactive rebase is not working
- not tested at all on Windows and thus unlikely to work there

See also https://github.com/fork-dev/Tracker/issues/929.


Remote checkouts
----------------

1. Clone this repository.

2. For each git checkout on the remote server, create a directory locally and
   create a file `.forkgit` inside with these contents (replacing values within
   `<>`):
   ```
   remote-host = <remote machine's hostname>
   remote-root = <absolute path to git checkout on the remote machine>
   ```

4. In the Fork Git preferences, add this repository's `bin/git` as a custom git
   instance.

5. Open the directories that represent the git checkouts on the remote machine
   in Fork.


To speed up interaction with remote checkouts, you can configure SSH multiplexing
for the server. This involves setting _ControlPath_, _ControlMaster_ and _ControlPersist_
in your `~/.ssh/config` for the host you're connecting to. See the [OpenSSH Wikibook](https://en.wikibooks.org/wiki/OpenSSH/Cookbook/Multiplexing#Setting_Up_Multiplexing)
for more information.


Custom .git directory
---------------------

This is useful when you want to track your dot-files in a git repository, but
don't want command-line git to know that your home directory is a git checkout.

To set this up:

1. Run `git init` in your home directory.

2. Rename the generated `.git` directory to `.dotfiles.git`.

3. Create a `.forkgit` file in your home-directory with these contents:
   ```
   git-dir = .dotfiles.git
   ```

4. Open your home directory in Fork.

You will want to create a `.gitignore` file to ignore most of the files in your
home directory to make this workable. For example:

```
*
!.*
!/.config/**/*
!/.ssh/config
.DS_Store
.bash_history
.cache/
.lesshst
.python_history
.viminfo
.wget-hsts
.zsh_history
.Xauthority
```
