#!/usr/bin/env bash
# The Umidasu — startup script.
#
# Sets up (idempotently) and launches the backend, which also serves the
# built frontend, as a single local process on a single port.
#
#   chmod +x execute.sh
#   ./execute.sh
#
set -euo pipefail

# ---------------------------------------------------------------- paths ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
VENV_DIR="$SCRIPT_DIR/.venv"

HOST="${UMIDASU_HOST:-127.0.0.1}"
REQUESTED_PORT="${UMIDASU_PORT:-8420}"

c_reset=$'\033[0m'; c_bold=$'\033[1m'; c_orange=$'\033[38;5;208m'; c_grey=$'\033[90m'; c_red=$'\033[31m'; c_green=$'\033[32m'

log()  { echo "${c_orange}[umidasu]${c_reset} $*"; }
warn() { echo "${c_orange}[umidasu]${c_reset} ${c_red}WARNING:${c_reset} $*"; }
die()  { echo "${c_orange}[umidasu]${c_reset} ${c_red}ERROR:${c_reset} $*" >&2; exit 1; }

if [[ "$HOST" != "127.0.0.1" && "$HOST" != "localhost" ]]; then
  warn "UMIDASU_HOST is set to '$HOST'. This exposes the app beyond localhost."
  warn "The Umidasu processes untrusted files; only do this if you understand the risk."
fi

# -------------------------------------------------------------- PATH -----
# A tool can be genuinely installed and visible to `ffmpeg -version` in an
# interactive terminal, yet still be missing from the PATH this script (and
# the backend process it launches) actually sees — snap puts binaries in
# /snap/bin via a profile.d script that only runs for login shells, and a
# manual/static install commonly lands in /usr/local/bin or ~/.local/bin,
# added to PATH only by ~/.bashrc, which a non-interactive script
# invocation does not source. That mismatch is what makes the web UI show
# a tool as "not installed" even though the same shell that ran this
# script can run it directly. Add the common locations here so the
# backend's own tool-availability check (shutil.which, same PATH it was
# started with) agrees with the terminal.
for _umidasu_extra_dir in /usr/local/bin /usr/local/sbin /snap/bin "$HOME/.local/bin"; do
  if [[ -d "$_umidasu_extra_dir" ]] && [[ ":$PATH:" != *":$_umidasu_extra_dir:"* ]]; then
    PATH="$PATH:$_umidasu_extra_dir"
  fi
done
export PATH
unset _umidasu_extra_dir

# ----------------------------------------------------------- prereqs -----
log "Checking prerequisites…"

command -v python3 >/dev/null 2>&1 || die "python3 is required but was not found on PATH."

# Pinned dependencies (Pillow, pikepdf, pydantic — see requirements.txt)
# don't yet ship prebuilt wheels for brand-new CPython releases, and
# pydantic-core in particular hard-fails to build on them (PyO3 caps out
# below the newest interpreter for a while after each Python release).
# Prefer the newest interpreter actually known to work, rather than
# whatever "python3" happens to resolve to — on a rolling-release distro
# that can be the newest release, which breaks `pip install` with
# confusing from-source build errors instead of a clear version message.
select_python() {
  for c in python3.13 python3.12 python3.11 python3.10 python3.9; do
    if command -v "$c" >/dev/null 2>&1; then
      echo "$c"
      return 0
    fi
  done
  echo "python3"
}

PY_BIN="$(select_python)"
PY_VERSION=$("$PY_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log "Found python3 $PY_VERSION"

PY_MAJOR="${PY_VERSION%%.*}"
PY_MINOR="${PY_VERSION##*.}"
if [[ "$PY_MAJOR" -gt 3 || ( "$PY_MAJOR" -eq 3 && "$PY_MINOR" -ge 14 ) ]]; then
  warn "Only Python $PY_VERSION was found ($PY_BIN). Pillow, pikepdf, and pydantic may not have"
  warn "prebuilt wheels for it yet, which can make 'pip install' fail trying to compile from"
  warn "source (missing libjpeg/qpdf headers, or pydantic-core refusing to build at all)."
  warn "If dependency installation fails below, install an older Python (3.11-3.13), e.g.:"
  warn "  sudo apt-get install -y python3.12 python3.12-venv"
  warn "then delete the .venv folder here and re-run ./execute.sh."
fi

MISSING_TOOLS=()
command -v exiftool >/dev/null 2>&1 || MISSING_TOOLS+=("exiftool")
command -v ffmpeg  >/dev/null 2>&1 || MISSING_TOOLS+=("ffmpeg")
command -v ffprobe >/dev/null 2>&1 || MISSING_TOOLS+=("ffprobe")

if [[ ${#MISSING_TOOLS[@]} -gt 0 ]]; then
  warn "Missing external tool(s): ${MISSING_TOOLS[*]}"
  echo
  echo "  The Umidasu will still start, but metadata extraction/editing for the"
  echo "  formats that depend on these tools will be reported as unavailable."
  echo
  echo "  To install on Debian/Ubuntu/Kali:"
  echo "    sudo apt-get update"
  echo "    sudo apt-get install -y libimage-exiftool-perl ffmpeg"
  echo
  echo "  To install on Fedora/RHEL:"
  echo "    sudo dnf install -y perl-Image-ExifTool ffmpeg"
  echo
  echo "  To install on Arch:"
  echo "    sudo pacman -S perl-image-exiftool ffmpeg"
  echo
  read -r -p "  Continue without these tools? [y/N] " REPLY || true
  if [[ ! "${REPLY:-}" =~ ^[Yy]$ ]]; then
    die "Install the missing tools above, then re-run ./execute.sh"
  fi
else
  log "exiftool, ffmpeg, and ffprobe are all available."
fi

command -v node >/dev/null 2>&1 || die "Node.js is required to build the frontend but was not found on PATH."
command -v npm  >/dev/null 2>&1 || die "npm is required to build the frontend but was not found on PATH."

# ------------------------------------------------------------- venv ------
if [[ ! -d "$VENV_DIR" ]]; then
  log "Creating Python virtual environment at $VENV_DIR (using $PY_BIN)"
  "$PY_BIN" -m venv "$VENV_DIR"
else
  log "Using existing virtual environment at $VENV_DIR"
  EXISTING_PY_VERSION=$("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "unknown")
  if [[ "$EXISTING_PY_VERSION" != "$PY_VERSION" ]]; then
    warn "The existing virtual environment uses Python $EXISTING_PY_VERSION, but $PY_BIN (Python $PY_VERSION) is now the preferred interpreter."
    read -r -p "  Delete and recreate .venv with Python $PY_VERSION? [y/N] " REPLY || true
    if [[ "${REPLY:-}" =~ ^[Yy]$ ]]; then
      rm -rf "$VENV_DIR"
      "$PY_BIN" -m venv "$VENV_DIR"
      log "Recreated virtual environment with $PY_BIN."
    fi
  fi
fi

VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

REQ_HASH_FILE="$VENV_DIR/.requirements.sha256"
REQ_CURRENT_HASH=$(sha256sum "$SCRIPT_DIR/requirements.txt" | awk '{print $1}')
REQ_STORED_HASH=""
[[ -f "$REQ_HASH_FILE" ]] && REQ_STORED_HASH=$(cat "$REQ_HASH_FILE")

if [[ "$REQ_CURRENT_HASH" != "$REQ_STORED_HASH" ]]; then
  log "Installing/updating pinned Python dependencies…"
  "$VENV_PIP" install --upgrade pip -q
  "$VENV_PIP" install -r "$SCRIPT_DIR/requirements.txt" -q
  echo "$REQ_CURRENT_HASH" > "$REQ_HASH_FILE"
else
  log "Python dependencies already up to date — skipping reinstall."
fi

# --------------------------------------------------------- frontend ------
NEED_FRONTEND_BUILD=1
if [[ -d "$FRONTEND_DIR/dist" && -f "$FRONTEND_DIR/dist/index.html" ]]; then
  # Rebuild only if source files are newer than the existing build.
  NEWEST_SRC=$(find "$FRONTEND_DIR/src" "$FRONTEND_DIR/index.html" -type f -newer "$FRONTEND_DIR/dist/index.html" 2>/dev/null | head -n1 || true)
  [[ -z "$NEWEST_SRC" ]] && NEED_FRONTEND_BUILD=0
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  log "Installing frontend dependencies (npm install)…"
  (cd "$FRONTEND_DIR" && npm install --no-fund --no-audit --loglevel=error)
fi

if [[ "$NEED_FRONTEND_BUILD" -eq 1 ]]; then
  log "Building frontend…"
  (cd "$FRONTEND_DIR" && npm run build --silent)
else
  log "Frontend build is up to date — skipping rebuild."
fi

# ------------------------------------------------------------- port ------
port_in_use() {
  "$VENV_PY" - "$1" <<'PYEOF'
import socket, sys
port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("127.0.0.1", port))
    s.close()
    sys.exit(1)  # free
except OSError:
    sys.exit(0)  # in use
PYEOF
}

PORT="$REQUESTED_PORT"
if port_in_use "$PORT"; then
  warn "Port $PORT is already in use."
  FOUND=0
  for candidate in $(seq $((PORT + 1)) $((PORT + 20))); do
    if ! port_in_use "$candidate"; then
      PORT="$candidate"
      FOUND=1
      break
    fi
  done
  [[ "$FOUND" -eq 1 ]] || die "Could not find a free port in range $REQUESTED_PORT-$((REQUESTED_PORT + 20))."
  log "Automatically selected free port $PORT instead."
fi

# --------------------------------------------------------- shutdown ------
CHILD_PIDS=()
cleanup() {
  echo
  log "Shutting down…"
  for pid in "${CHILD_PIDS[@]:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
  log "Stopped."
}
trap cleanup INT TERM EXIT

# -------------------------------------------------------------- start ----
export UMIDASU_HOST="$HOST"
export UMIDASU_PORT="$PORT"

log "Starting The Umidasu backend (also serving the built frontend)…"
(cd "$BACKEND_DIR" && exec "$VENV_PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT") &
BACKEND_PID=$!
CHILD_PIDS+=("$BACKEND_PID")

# Wait for the server to come up before printing the URL.
for _ in $(seq 1 40); do
  if "$VENV_PY" - "$HOST" "$PORT" <<'PYEOF' >/dev/null 2>&1
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.25)
s.connect((sys.argv[1], int(sys.argv[2])))
s.close()
PYEOF
  then
    break
  fi
  sleep 0.25
done

echo
echo "  ${c_bold}${c_orange}The Umidasu is running.${c_reset}"
echo "  ${c_bold}Open: http://$HOST:$PORT${c_reset}"
echo "  ${c_grey}Press Ctrl+C to stop.${c_reset}"
echo

wait "$BACKEND_PID"
