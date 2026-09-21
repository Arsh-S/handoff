#!/usr/bin/env bash
# Install handoff on this machine, then run `handoff setup`.
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

mkdir -p "$PREFIX/bin" "$PREFIX/share/handoff"
install -m 755 "$SRC/bin/handoff" "$PREFIX/bin/handoff"
mkdir -p "$PREFIX/share/handoff/remote" "$PREFIX/share/handoff/hooks"
install -m 755 "$SRC/remote/handoff-remote"   "$PREFIX/share/handoff/remote/handoff-remote"
install -m 755 "$SRC/hooks/handoff-guard.py"  "$PREFIX/share/handoff/hooks/handoff-guard.py"

echo "installed:"
echo "  $PREFIX/bin/handoff"
echo "  $PREFIX/share/handoff/"
echo

case ":$PATH:" in
  *":$PREFIX/bin:"*) ;;
  *) echo "note: $PREFIX/bin is not on your PATH. Add it, then reopen your shell." ;;
esac

echo "next: handoff setup"
