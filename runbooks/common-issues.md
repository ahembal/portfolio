# Common Issues

## git pull / git fetch stalls silently

**Symptom:** `git pull` or `git fetch` hangs indefinitely with no output.

**Cause:** A stale SSH multiplexer socket from a previous session.
Git reuses an existing SSH connection via `~/.ssh/socket-git@github.com-22`.
If that session died uncleanly the socket file still exists but the connection
is broken, so git waits forever for a response that never comes.

**Fix:**
```bash
ssh -O exit git@github.com
```

This sends the `exit` command to the SSH master process, closing the socket
cleanly. Then `git pull` / `git fetch` will open a fresh connection.

**If that doesn't work** (socket file exists but process is already dead):
```bash
rm -f ~/.ssh/socket-git@github.com-22
```

**Prevention:** The SSH config in `~/.ssh/config` controls multiplexing.
If this recurs often, reduce `ControlPersist` from its current value or
disable multiplexing for GitHub entirely:
```
Host github.com
    ControlMaster no
```
