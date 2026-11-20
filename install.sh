#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/FastClock"
SERVICE_NAME="fastclock.service"
USER_NAME="fastclock"
GROUP_NAME="fastclock"

# Ensure script is run with root privileges
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (use sudo)." >&2
    exit 1
fi

echo "==> Creating dedicated system user '${USER_NAME}' (if not existing)..."
if ! id -u "${USER_NAME}" >/dev/null 2>&1; then
    useradd --system --user-group --shell /usr/sbin/nologin --home-dir "${INSTALL_DIR}" --no-create-home "${USER_NAME}"
    echo "Created system user '${USER_NAME}' and group '${GROUP_NAME}'."
else
    echo "User '${USER_NAME}' already exists."
fi

# Ensure install directory exists
mkdir -p "${INSTALL_DIR}"

# Create virtual environment if missing
if [[ ! -d "${INSTALL_DIR}/.venv" ]]; then
    echo "==> Creating Python virtual environment in ${INSTALL_DIR}/.venv..."
    python3 -m venv "${INSTALL_DIR}/.venv"
fi

echo "==> Installing / updating Python dependencies..."
"${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip paho-mqtt

echo "==> Setting directory ownership to ${USER_NAME}:${GROUP_NAME}..."
chown -R "${USER_NAME}:${GROUP_NAME}" "${INSTALL_DIR}"

echo "==> Installing systemd service..."
cp "${INSTALL_DIR}/${SERVICE_NAME}" "/etc/systemd/system/${SERVICE_NAME}"
systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "==> FastClock service successfully installed and started!"
systemctl status "${SERVICE_NAME}" --no-pager
