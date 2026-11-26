# FastClock

## Introduction

A **Fast Clock** is a staple of realistic model railroad operating sessions—compressing a full prototype work shift into a 2- to 3-hour evening session. For example, at a **4:1 ratio**, your crew can work an 8-hour railroad shift in 2 real-world hours.

**FastClock** is a lightweight, JMRI-compatible master fast clock designed to run continuously on a Raspberry Pi (or any Linux/macOS computer). Instead of relying on a single desktop PC or a proprietary DCC cab bus, FastClock broadcasts the time over your layout's Wi-Fi/Ethernet network using **MQTT**—think of MQTT as a shared "bulletin board" where FastClock posts the current time, and JMRI, Wi-Fi throttles, ESP32/Arduino fascia clocks, and web-browser/tablet displays (via WebSockets on port `9001`) can all stay synchronized or send commands to pause, resume, or reset the clock.

---

## Why Use FastClock?

- **Automatic Startup**: Runs in the background on your Raspberry Pi and starts automatically whenever you power on the layout.
- **Works with All Your Displays**: Supports standard MQTT (port `1883`) for JMRI, ESP32/Arduino, and Node-RED, plus **WebSockets** (port `9001`) for web-browser and tablet clock displays.
- **Session-Friendly Controls**: Easily pause for a derailment or coffee break, adjust the speed ratio on the fly, or reset the clock to the start of your timetable.
- **Reliable & Lightweight**: Runs cleanly even on older/smaller Raspberry Pi models (like a Pi Zero or Pi 3 A+) and recovers cleanly if devices reconnect.

---

## What You'll Need

- A **Raspberry Pi** (any model) connected to your layout's Wi-Fi or Ethernet network—or a Linux/macOS computer.
- Access to the Pi's terminal (either directly with a keyboard/monitor or over SSH).

---

## Quick Start: Raspberry Pi Setup (Recommended)

### Step 1 — Clone & Run the Installer

Clone the project into `/opt/FastClock` and run the included installer:

```bash
sudo git clone https://github.com/railnerd/FastClock.git /opt/FastClock
cd /opt/FastClock
sudo ./install.sh
```

**What `install.sh` does for you automatically:**
1. Installs the **Mosquitto MQTT broker and client tools** (`mosquitto` and `mosquitto-clients`) if they are not already installed on your Pi.
2. Configures Mosquitto (`/etc/mosquitto/conf.d/local.conf`, if not already present) so layout devices can connect on port `1883` and web-browser clocks can connect via WebSockets on port `9001`, and enables the broker on boot.
3. Creates a dedicated, unprivileged `fastclock` background user.
4. Sets up a Python virtual environment (`.venv`) and installs `paho-mqtt`.
5. Installs and starts the `fastclock.service` background daemon so FastClock starts automatically on boot.

### Step 2 — Verify It's Working

Watch the live clock messages on your Pi's terminal:

```bash
mosquitto_sub -h localhost -t "layout/clock/#" -v
```

You should immediately see the current clock state:

```text
layout/clock/time 08:00
layout/clock/state ACTIVE
layout/clock/rate 4.00
```

Press `Ctrl+C` when you're done watching.

---

## Controlling the Clock During an Operating Session

You can control the clock from any computer or device on your layout network using `mosquitto_pub` (replace `localhost` with your Pi's hostname or IP address, such as `pi3aplus.local`, if sending from another machine):

- **Pause the clock** (e.g., for a derailment or lunch break):
  ```bash
  mosquitto_pub -h localhost -t "layout/clock/cmd" -m "STOP"
  ```
- **Resume the clock**:
  ```bash
  mosquitto_pub -h localhost -t "layout/clock/cmd" -m "START"
  ```
- **Reset to the start of a session** (accepts `HH:MM` or `HH:MM:SS`):
  ```bash
  mosquitto_pub -h localhost -t "layout/clock/cmd" -m "SET 06:00"
  ```
- **Change the fast clock speed** (e.g., switch to 6:1):
  ```bash
  mosquitto_pub -h localhost -t "layout/clock/cmd" -m "RATE 6.0"
  ```

---

## Managing FastClock on Your Raspberry Pi

| Task | Command |
| :--- | :--- |
| Check if FastClock is running | `sudo systemctl status fastclock.service` |
| Watch live log messages | `journalctl -u fastclock.service -f` |
| Restart FastClock | `sudo systemctl restart fastclock.service` |
| Stop FastClock | `sudo systemctl stop fastclock.service` |

### Changing the Default Start Time or Speed

By default, FastClock starts at `08:00` running at `4.0x` speed. To change the startup defaults:

1. Edit `/opt/FastClock/fastclock.service` and add `--start` and/or `--rate` to the `ExecStart` line, for example:
   ```ini
   ExecStart=/opt/FastClock/.venv/bin/python /opt/FastClock/fastclock.py --start 06:00 --rate 6.0
   ```
2. Apply the change by re-running the installer (or copying the service file and reloading systemd):
   ```bash
   sudo cp /opt/FastClock/fastclock.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl restart fastclock.service
   ```

---

## Connecting FastClock to JMRI

### Step 1 — Add the MQTT Connection in JMRI

1. Open **JMRI** (PanelPro or DecoderPro) and go to **Edit → Preferences → Connections**.
2. Click **`+`** to add a new connection:
   - **System Manufacturer**: `MQTT`
   - **System Connection**: `MQTT Connection`
   - **IP Address / Host Name**: Enter your Raspberry Pi's hostname (e.g., `pi3aplus.local`) or IP address (e.g., `192.168.1.50`).
   - **TCP/UDP Port** *(under Additional Connection Settings, if needed)*: `1883`
   - **MQTT Channel**: JMRI prepends this channel prefix to its MQTT topics. Leave it blank if you want to reference FastClock's default topics directly (`layout/clock/time`), or if you already use a JMRI channel (such as `trains/`), launch FastClock with `--prefix trains/clock` so everything shares the same root namespace.
3. Click **Save** and restart JMRI when prompted.

### Step 2 — Display & Control FastClock in JMRI

JMRI's built-in MQTT connection natively maps Turnouts (`MT`), Sensors (`MS`), Lights (`ML`), and Reporters (`MR`). To connect the Fast Clock, choose either **LogixNG** (no coding) or a **Jython script**:

#### Option A — Display & Control via LogixNG (No Coding Required)

1. **Show the fast time on a PanelPro panel**:
   - Open **Tools → Tables → LogixNG → LogixNGs** and create a ConditionalNG.
   - Add an **MQTT Subscribe** action listening to `layout/clock/time` (or `clock/time` if your JMRI MQTT Channel is already `layout/`).
   - Store the incoming payload in a **Local Variable**, then copy that value into a JMRI **Memory Variable** (such as `IMCURRENTTIME` or a custom `IMFASTCLOCK`) placed on your panel.
2. **Show Running / Paused status**:
   - `layout/clock/state` publishes `ACTIVE` and `INACTIVE`—matching JMRI's standard MQTT Sensor states—so you can link it directly to a JMRI MQTT Sensor (`MS...`) or a LogixNG indicator.
3. **Add Start / Stop / Reset buttons to your panel**:
   - Tie panel buttons (or Internal Sensors) to a LogixNG **MQTT Publish** action targeting `layout/clock/cmd` with payloads like `START`, `STOP`, `SET 08:00`, or `RATE 4.0`.

#### Option B — Sync JMRI's Built-In Fast Clock (Jython Script)

If you want JMRI's native Fast Clock (**Tools → Clocks → Set up Fast Clock** / `Timebase`)—including JMRI's analog/LCD clock windows and WiThrottle fast clock broadcast—to follow FastClock automatically, add a lightweight Jython bridge script under **Edit → Preferences → Start Up → Add → Run Script** that listens to `layout/clock/time`, `layout/clock/state`, and `layout/clock/rate` and updates `jmri.InstanceManager.getDefault(jmri.Timebase)`.

---

## MQTT Reference (For JMRI, ESP32/Arduino, & Web Clocks)

- **Standard MQTT Port**: `1883` (for JMRI, Arduino/ESP32, Node-RED, Python scripts)
- **WebSockets Port**: `9001` (for web-browser and tablet clock displays)
- **Default Topic Prefix**: `layout/clock` (configurable with `--prefix`)

### Published Topics (Retained)

Mosquitto retains the latest value on these topics so newly powered-on layout clocks immediately receive the current time:

| Topic | Payload Format | Description |
| :--- | :--- | :--- |
| `layout/clock/time` | `HH:MM` (e.g., `08:15`) | Current simulated fast time |
| `layout/clock/state` | `ACTIVE` or `INACTIVE` | Whether the clock is running or paused |
| `layout/clock/rate` | Decimal float (e.g., `4.00`) | Current clock speed multiplier |

### Control Commands

Publish any of these UTF-8 strings to `layout/clock/cmd`:

| Command | Example | Description |
| :--- | :--- | :--- |
| `START` | `START` | Starts or resumes the fast clock |
| `STOP` | `STOP` | Pauses the fast clock |
| `RATE <multiplier>` | `RATE 2.5` | Sets the fast clock speed ratio |
| `SET <HH:MM>` or `SET <HH:MM:SS>` | `SET 14:30` | Sets the current fast clock time |

---

## Running Manually (macOS / Linux / Testing)

If you want to test FastClock on a Mac or Linux workstation without installing the background service:

### 1. Install Mosquitto (macOS)

```bash
brew install mosquitto
brew services start mosquitto
```

### 2. Set Up Python (Python 3.9+)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install paho-mqtt
```

### 3. Run FastClock

```bash
python3 fastclock.py
```

#### Command-Line Options

```text
usage: fastclock.py [-h] [--broker BROKER] [--port PORT] [--prefix PREFIX]
                    [--start START] [--rate RATE]
                    [--poll-interval POLL_INTERVAL] [--verbose]

optional arguments:
  -h, --help            show this help message and exit
  --broker BROKER       MQTT broker address (default: localhost)
  --port PORT           MQTT broker port (default: 1883)
  --prefix PREFIX       MQTT topic prefix (default: layout/clock)
  --start START         Initial clock time in HH:MM (default: 08:00)
  --rate RATE           Clock speed multiplier (default: 4.0)
  --poll-interval POLL_INTERVAL
                        Polling interval in seconds (default: 0.2)
  --verbose, -v         Enable verbose debug logging
```

**Example** (connect to a broker at `192.168.1.50` starting at `06:30` at `6:1` speed):

```bash
python3 fastclock.py --broker 192.168.1.50 --start 06:30 --rate 6.0
```

### Manual Mosquitto & Systemd Configuration (If Not Using `install.sh`)

#### Manual Mosquitto Installation & Configuration (Ports 1883 & 9001)

1. Install and start Mosquitto:
   ```bash
   sudo apt update
   sudo apt install -y mosquitto mosquitto-clients
   sudo systemctl enable --now mosquitto
   ```

2. By default, Mosquitto 2.0+ only accepts connections from `localhost`. To allow layout devices and browser displays on your network to connect, create `/etc/mosquitto/conf.d/local.conf`:
   ```bash
   sudo bash -c 'cat <<EOF > /etc/mosquitto/conf.d/local.conf
   listener 1883
   allow_anonymous true

   listener 9001
   protocol websockets
   allow_anonymous true
   EOF'
   sudo systemctl restart mosquitto
   ```

#### Manual Systemd Setup

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
4. **Check status and logs**:
   ```bash
   sudo systemctl status fastclock.service
   journalctl -u fastclock.service -f
   ```

---

## Troubleshooting

- **Other devices on the layout can't connect to the clock:**
  1. Make sure your devices are pointing at your Raspberry Pi's hostname (e.g., `pi3aplus.local`) or IP address—not `localhost`.
  2. Check that `/etc/mosquitto/conf.d/local.conf` exists and contains `listener 1883`, `listener 9001`, and `allow_anonymous true`, then run `sudo systemctl restart mosquitto`.
- **How do I update FastClock to the latest version?**
  ```bash
  cd /opt/FastClock
  sudo git pull
  sudo ./install.sh
  ```

---

## License

MIT
