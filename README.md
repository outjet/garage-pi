# Garage Pi

A Raspberry Pi–based garage door controller with:

* Google OAuth authentication
* Door state detection (up / down / in transition)
* Secure GPIO relay control
* Flask backend + Gunicorn deployment
* Designed to run behind a private network (e.g., Tailscale)

---

## Security Model

This app:

* Requires Google OAuth login
* Restricts access to specific email addresses (`ALLOWED_EMAILS`)
* Uses server-side sessions
* Exposes only authenticated API endpoints for door control

Recommended deployment:

* Bind Gunicorn to `127.0.0.1`
* Access over a private network overlay (e.g., Tailscale)
* Do NOT expose directly to the public internet

---

## Hardware Requirements

* Raspberry Pi (Pi 3 or Pi 4 recommended)
* Magnetic reed sensors (door up / door down)
* Relay module for door trigger
* Optional buzzer
* High-endurance microSD card recommended

---

## Project Structure

```
garage_oauth_project/
│
├── app.py
├── requirements.txt
├── .env.example
├── static/
├── templates/
└── deploy/
    └── garage-gunicorn.service
```

---

## Environment Variables

Create a `.env` file in `garage_oauth_project/`:

```
SECRET_KEY=your-secret-key
ALLOWED_EMAILS=you@example.com,spouse@example.com

PIN_DOWN_SENSOR=20
PIN_UP_SENSOR=21
PIN_DOOR_CONTROL=16
PIN_BUZZER=19

LOCAL_API_KEY=replace-with-long-random-key
# Optional: comma-separated list of CIDRs that can use /api/local/*
LOCAL_API_ALLOWED_CIDR=127.0.0.1/32,::1/128,100.64.0.0/10,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
```

---

## Google OAuth Setup

1. Go to Google Cloud Console
2. Create OAuth 2.0 Client Credentials
3. Add redirect URI:

```
http://localhost:8443/callback
```

(or your Tailscale hostname if using private network access)

4. Download `client_secret.json`
5. Place it inside `garage_oauth_project/`

---

## Installation (Fresh Pi Setup)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-venv python3-pip -y

mkdir -p /garage
cd /garage
git clone https://github.com/outjet/garage-pi.git
cd garage-pi/garage_oauth_project

python3 -m venv garage_env
source garage_env/bin/activate
pip install -r requirements.txt
```

---

## Running Manually (Development)

```bash
source garage_env/bin/activate
python app.py
```

---

## Production (Gunicorn + systemd)

Copy the service file:

```bash
sudo cp deploy/garage-gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable garage-gunicorn
sudo systemctl start garage-gunicorn
```

---

## API Endpoints

Authenticated only:

| Endpoint           | Method | Description       |
| ------------------ | ------ | ----------------- |
| `/api/door/up`     | POST   | Open door         |
| `/api/door/down`   | POST   | Close door        |
| `/api/door/status` | GET    | Get current state |

Local API key (for Home Assistant / LAN / Tailscale):

| Endpoint                 | Method | Description                 |
| ------------------------ | ------ | --------------------------- |
| `/api/local/door/up`     | POST   | Open door (API key + CIDR)  |
| `/api/local/door/down`   | POST   | Close door (API key + CIDR) |
| `/api/local/door/status` | GET    | Get state (API key + CIDR)  |
| `/status`                | GET    | Public status (no auth)     |

### Home Assistant (REST) example

```yaml
rest_command:
  garage_open:
    url: "https://outgar.duckdns.org:8443/api/local/door/up"
    method: POST
    headers:
      X-API-Key: !secret garage_local_api_key

  garage_close:
    url: "https://outgar.duckdns.org:8443/api/local/door/down"
    method: POST
    headers:
      X-API-Key: !secret garage_local_api_key

sensor:
  - platform: rest
    name: Garage Door API Status
    resource: "https://outgar.duckdns.org:8443/api/local/door/status"
    method: GET
    headers:
      X-API-Key: !secret garage_local_api_key
    value_template: "{{ value_json.status }}"
```

---

## How It Works

* Reed switches detect door position
* Relay triggers standard garage opener
* App prevents redundant open/close commands
* Thread lock ensures relay isn't double-triggered

---

## Recommended Hardening

* Run behind Tailscale (no public ports)
* Bind Gunicorn to localhost
* Disable file logging to reduce SD wear
* Use high-endurance SD card

---

## License

GPL-3.0

---

If you’d like, I can also:

* Make a slightly more “open source polished” version
* Add architecture diagrams
* Add a Tailscale deployment section
* Or write a “Lessons Learned / Why This Exists” section that tells the story

Just say the tone you want:

* Clean & professional
* Personal project narrative
* Enterprise-ish
* Hacker minimalist
* Or somewhere in between
