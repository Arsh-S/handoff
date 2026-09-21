# handoff

Move a project to another machine, work on it there with Claude Code, bring it back.

Your laptop is not always the right place to run something. A test suite that takes
twenty minutes, a video render, anything that wants a GPU, or simply work that should
outlive closing the lid. `handoff` pushes the project to a machine that is always on,
starts a Claude Code session there with Remote Control enabled so you can drive it from
your phone, and pulls everything home when you are done.

The project lives in exactly one place at a time. While it is away, a Claude Code hook
stops the local machine from editing the stale copy.

```
$ handoff to remote
==> Checking homelab
  [ok] reachable
==> Handing off checkout-api
  local :  /Users/you/code/checkout-api
  remote:  you@homelab:/home/you/work/checkout-api
  git   :  worktree on branch refactor, 4 uncommitted change(s)
           the shared object store travels too, so git works over there
==> Syncing working files
  [ok] working files synced
==> Materialising a real .git on the remote
  [ok] standalone repo on branch refactor
==> Starting Claude on the remote (session 'hand-checkout-api')
  [ok] registered: this machine will now refuse to edit checkout-api

  Pick it up in the Claude app under 'hand-checkout-api', or run 'handoff attach'.
  Dev server over there?  handoff port 3000
  Finished?               handoff back
```

## Install

```sh
git clone https://github.com/Arsh-S/handoff
cd handoff && ./install.sh
handoff setup
```

`handoff setup` asks for the SSH target, writes a config, installs the remote helper,
registers the Claude Code hook, and tells you what the remote is missing.
Run `handoff doctor` any time to check both ends.

## Commands

| | |
|---|---|
| `handoff to remote [-y]` | push this project and start Claude over there |
| `handoff back` | pull it home and stop the remote session |
| `handoff status` | what is out, and is the remote up |
| `handoff attach` | attach to the remote tmux session over SSH |
| `handoff port <n>` | forward a dev server port from the remote |
| `handoff abort` | release the lock without syncing back |
| `handoff doctor` | health check both machines |

### Before it sends anything

Two checks run before the first byte moves.

**It refuses a directory that is not a git repository**, which is almost always a sign
you are one level above the project you meant. Confirm, or pass `-y`.

**It prints the transfer size and asks if it is large.** For a worktree that includes the
shared object store, which is usually the bigger half. The threshold is
`HANDOFF_CONFIRM_SIZE_MB`, default 100.

```
==> Transfer size
  working files:    41.2MB
  git object store: 380.6MB
  total:            421.8MB
  [!!] that is over the 100MB confirmation threshold
  Send 421.8MB to homelab? [y/N]:
```

Neither prompt will hang a script: with no terminal and no `-y`, handoff stops rather
than guessing.

## Requirements

**Local:** bash, rsync, python3, git, SSH access to the remote, and Claude Code if you
want the edit guard.

**Remote:** git, rsync, tmux, python3 or node, and Claude Code logged in. The remote
must be reachable by SSH. Something like Tailscale makes that easy across networks, but
`handoff` does not care how you get there.

## How it works

`handoff to remote` rsyncs the project to `<remote root>/<project>`. Uncommitted
changes, `.git`, and gitignored config such as `.env` all come along, because otherwise
the project will not run. `node_modules`, virtualenvs, and build output are excluded, so
**install dependencies on the remote before expecting anything to work.**

It then pre-accepts Claude Code's folder-trust prompt (which would otherwise block an
unattended start), and launches:

```
tmux new-session -d -s hand-<project> 'claude --remote-control hand-<project> --permission-mode auto'
```

Remote Control means the session registers itself and shows up in the Claude mobile app
and at claude.ai/code, so you can drive it from anywhere. Auto permission mode means it
asks you rather than running unattended with permissions skipped. Both are configurable.

`handoff back` snapshots your local copy to `~/.handoff/backups/` before it touches
anything, then rsyncs the remote copy home, stops the session, and releases the lock.

### The edit guard

While a project is handed off it is recorded in `~/.handoff/handoffs.json`. A
`PreToolUse` hook checks every Edit and Write against that registry and blocks anything
inside a handed-off tree, telling Claude to stop rather than work around it.

This is the part that makes the whole thing safe to use. Without it, a Claude session on
your laptop will happily edit a copy that is about to be overwritten.

The guard only constrains Claude. If you hand-edit the local copy in your own editor,
`handoff back` will overwrite it. The snapshot makes that recoverable, not prevented.

### Git worktrees

Worktrees work, and they take a different path through the code.

A worktree's `.git` is not a directory. It is a one-line file holding an absolute path
back into the parent repository (`gitdir: /Users/you/code/main/.git/worktrees/refactor`).
That path does not exist on the remote, so a naive copy leaves you with
`fatal: not a git repository` and no way to commit.

Instead, `handoff` builds a real repository on the remote: it syncs the shared object
store to `<remote>/.git`, lays the worktree's own `HEAD` and `index` on top, and stashes
the worktree metadata. You get a standalone repo on the same branch with full history and
your staged changes intact.

Coming back, the remote's objects are merged into your repository's object store. Git
objects are immutable and content addressed, so this is purely additive and cannot lose
anything. The index is restored and the branch ref is moved with `git update-ref`. Your
local `.git` pointer file is never written to.

## Configuration

`~/.config/handoff/config` is plain shell, written by `handoff setup`:

Values are single quoted on purpose. A path containing `$HOME` must be expanded by the
remote shell, not by yours when the config is sourced.

```sh
HANDOFF_HOST='you@homelab'            # anything ssh understands
HANDOFF_REMOTE_ROOT='/home/you/work'  # where projects land
HANDOFF_REMOTE_KIND='plain'           # plain | wsl
HANDOFF_WSL_DISTRO='Ubuntu'           # only for kind=wsl
HANDOFF_REMOTE_LABEL='homelab'        # what to call it in messages
HANDOFF_CLAUDE_BIN='$HOME/.local/bin/claude'
HANDOFF_PERMISSION_MODE='auto'        # auto | acceptEdits | bypassPermissions | plan
HANDOFF_SESSION_PREFIX='hand-'
HANDOFF_CONFIRM_SIZE_MB='100'         # prompt above this transfer size
HANDOFF_CONNECT_TRIES='3'             # SSH attempts before giving up
```

Per project, a `.handoffignore` file in the project root is passed to rsync as
`--exclude-from`, so you can add or unwind exclusions.

## Windows remotes (WSL)

Set `HANDOFF_REMOTE_KIND=wsl` and every remote command gets wrapped in
`wsl -d <distro> -- bash -lc`, including rsync's `--rsync-path`. Three things to know:

**Keeping WSL alive.** Windows shuts a distro down once nothing is running inside it,
which kills detached tmux sessions between SSH connections. Register a scheduled task
that holds it open:

```powershell
$action  = New-ScheduledTaskAction -Execute 'C:\Windows\System32\wsl.exe' `
           -Argument '-d Ubuntu -u YOURUSER -- /bin/sleep infinity'
$trigger = New-ScheduledTaskTrigger -AtStartup
$set     = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
           -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 `
           -RestartInterval (New-TimeSpan -Minutes 1)
$prin    = New-ScheduledTaskPrincipal -UserId 'PCNAME\YOURUSER' -LogonType S4U -RunLevel Highest
Register-ScheduledTask -TaskName 'WSL Keepalive' -Action $action -Trigger $trigger `
  -Settings $set -Principal $prin -Force
```

S4U lets it run without storing a password and without anyone being logged in.

**Dev server ports.** WSL2 sits behind its own NAT, so forwarding to the Windows loopback
reaches nothing. `handoff port` resolves the distro's current address at tunnel time. Your
server still has to bind `0.0.0.0` rather than `127.0.0.1`.

**Staying reachable.** If the box disappears from your network after a reboot, check
whether your VPN runs unattended. Tailscale, for example, does not connect until someone
logs in unless you run `tailscale set --unattended=true`.

## Caveats

- Dependencies do not travel. Run your install step on the remote.
- The exclude list drops any directory named `build`, `dist`, `out`, or `target`. If a
  project keeps real source in one of those, add a `.handoffignore`.
- The guard stops Claude, not you. Editing the local copy by hand while it is away means
  `handoff back` overwrites your edits, recoverable only from the snapshot.
- Branches created on the remote are not synced back. The checked-out branch is.
- `handoff back` uses `rsync --delete`. It snapshots first, but be aware.
- Proven against a macOS client with a Windows/WSL remote: full round trips including
  worktrees. For `plain` remotes the command plumbing and `handoff doctor` are verified,
  but a full session start has not been exercised end to end. Reports welcome.

## License

MIT
