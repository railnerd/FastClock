# FastClock

A JMRI-compatible Fast Clock MQTT publisher designed for model railroad automation, running seamlessly on a Raspberry Pi or any Linux/macOS machine.

It simulates a fast clock with configurable acceleration ratios and keeps layout displays, throttles, and automation controllers in sync via MQTT.

---

## Features

- **Fast Time Simulation**: Configurable initial time (default: `08:00`) and acceleration rate (default: `4.0x`).
- **MQTT Integration**:
  - Automatically publishes retained state whenever the simulated minute changes or a control command is executed.
  - Subscribes to a command topic for dynamic remote control.
- **Thread-Safe & Robust**: Thread-safe state synchronization between MQTT callback threads and the main loop.
- **Raspberry Pi Ready**: Includes a systemd service unit (`fastclock.service`) for running as a managed background daemon on boot.
- **Configurable CLI**: Customize broker host, port, topic prefix, and clock rates via command-line flags.

---

## MQTT Interface

Default topic prefix: `layout/clock` (configurable with `--prefix`).

### Published Topics (Retained)

| Topic | Payload Format | Description |
| :--- | :--- | :--- |
| `layout/clock/time` | `HH:MM` (e.g., `08:15`) | Current simulated fast time |
| `layout/clock/state` | `ACTIVE` or `INACTIVE` | Clock running status |
| `layout/clock/rate` | Decimal float (e.g., `4.00`) | Current clock speed multiplier |

### Control Commands

Publish any of the following UTF-8 strings to `layout/clock/cmd`:

| Command | Example | Description |
| :--- | :--- | :--- |
| `START` | `START` | Starts / resumes the fast clock |
| `STOP` | `STOP` | Pauses the fast clock |
| `RATE <multiplier>` | `RATE 2.5` | Sets the fast clock speed ratio |
| `SET <HH:MM>` | `SET 14:30` | Sets current fast clock time |

---

## Requirements & Installation

### 1. MQTT Broker (Mosquitto)

FastClock requires an MQTT broker to publish and receive messages. If you don't already have one running on your Raspberry Pi or network:

#### On Raspberry Pi OS / Debian / Ubuntu

Install the Mosquitto broker and CLI client tools:

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

> [!TIP]
> **Allowing Remote Devices & WebSockets (Ports 1883 & 9001)**:
> By default, Mosquitto 2.0+ only accepts connections from `localhost`. To allow layout devices (JMRI, Wi-Fi throttles) and browser-based displays/dashboards (over WebSockets) to connect, create `/etc/mosquitto/conf.d/local.conf`:
>
> ```bash
> sudo bash -c 'cat <<EOF > /etc/mosquitto/conf.d/local.conf
> listener 1883
> allow_anonymous true
> 
> listener 9001
> protocol websockets
> allow_anonymous true
> EOF'
> sudo systemctl restart mosquitto
> ```

#### On macOS (Development / Testing)

```bash
brew install mosquitto
brew services start mosquitto
```

#### Verifying the Broker

Test broker communication using the CLI tools:

```bash
# In one terminal, listen for messages:
mosquitto_sub -h localhost -t "test/topic"

# In another terminal, send a test message:
mosquitto_pub -h localhost -t "test/topic" -m "hello layout"
```

---

### 2. Python Environment & Dependencies

1. **Python 3.9+**
2. **paho-mqtt** client library:

```bash
pip install paho-mqtt
```

*(Optional but recommended)* Create and use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install paho-mqtt
```

---

## Usage

Run with default settings (connects to `localhost:1883`, prefix `layout/clock`, start time `08:00`, rate `4.0`):

```bash
python3 fastclock.py
```

### Command-Line Options

```text
usage: fastclock.py [-h] [--broker BROKER] [--port PORT] [--prefix PREFIX]
                    [--start START] [--rate RATE]
                    [--poll-interval POLL_INTERVAL] [--verbose]

optional arguments:
  -h, --help            Show this help message and exit
  --broker BROKER       MQTT broker address (default: localhost)
  --port PORT           MQTT broker port (default: 1883)
  --prefix PREFIX       MQTT topic prefix (default: layout/clock)
  --start START         Initial clock time in HH:MM (default: 08:00)
  --rate RATE           Clock speed multiplier (default: 4.0)
  --poll-interval POLL_INTERVAL
                        State polling interval in seconds (default: 0.2)
  --verbose, -v         Enable verbose debug logging
```

#### Example

```bash
# Connect to a remote broker with 6:1 speed starting at 06:30
python3 fastclock.py --broker 192.168.1.50 --start 06:30 --rate 6.0
```

---

## Running as a Background Service on Raspberry Pi (systemd)

A systemd unit file is provided in `fastclock.service` configured to run under a dedicated system user (`fastclock`) in `/opt/FastClock`.

### Automated Installation

Clone to `/opt/FastClock` and run the included installation script with `sudo`:

```bash
sudo git clone https://github.com/railnerd/FastClock.git /opt/FastClock
cd /opt/FastClock
sudo ./install.sh
```

The script will:
1. Create the dedicated, unprivileged system user `fastclock` (with no login shell).
2. Create the Python virtual environment and install dependencies.
3. Set secure ownership of `/opt/FastClock` to `fastclock:fastclock`.
4. Install and enable the systemd service to start on boot.

### Manual Installation

1. **Create the dedicated system user**:
   ```bash
   sudo useradd --system --user-group --shell /usr/sbin/nologin --home-dir /opt/FastClock --no-create-home fastclock
   ```

2. **Set ownership**:
   ```bash
   sudo chown -R fastclock:fastclock /opt/FastClock
   ```

3. **Install and enable the service**:
   ```bash
   sudo cp /opt/FastClock/fastclock.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now fastclock.service
   ```

3. **Check status and logs**:
   ```bash
   # Status
   sudo systemctl status fastclock.service

   # Live log stream
   journalctl -u fastclock.service -f
   ```

---

## License

MIT
