
import os

from flask import Flask, redirect, url_for, session, render_template, jsonify, request
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request, AuthorizedSession
import requests
import time
import threading
from dotenv import load_dotenv
import datetime
import atexit

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SERVER_NAME'] = 'outgar.duckdns.org:8443'
app.secret_key = os.environ.get("SECRET_KEY")
app.permanent_session_lifetime = datetime.timedelta(hours=24)

# OAuth 2.0 configuration
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile", "openid"]

# GPIO Pin Constants
PIN_DOWN_SENSOR = int(os.getenv('PIN_DOWN_SENSOR', 20))
PIN_UP_SENSOR = int(os.getenv('PIN_UP_SENSOR', 21))
PIN_DOOR_CONTROL = int(os.getenv('PIN_DOOR_CONTROL', 16))
PIN_BUZZER = int(os.getenv('PIN_BUZZER', 19))


GPIO_AVAILABLE = False
try:
    import RPi.GPIO as gpio
    gpio.setmode(gpio.BCM)
    gpio.setwarnings(False)
    gpio.setup(PIN_DOWN_SENSOR, gpio.IN, pull_up_down=gpio.PUD_UP)
    gpio.setup(PIN_UP_SENSOR, gpio.IN, pull_up_down=gpio.PUD_UP)
    gpio.setup(PIN_DOOR_CONTROL, gpio.OUT)
    gpio.setup(PIN_BUZZER, gpio.OUT)
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    # Mock RPi.GPIO for non-Raspberry Pi environments
    class MockGPIO:
        BCM = 11
        IN = 1
        OUT = 0
        PUD_UP = 22
        LOW = 0
        HIGH = 1

        def setmode(self, mode):
            print("GPIO: setmode called")

        def setwarnings(self, flag):
            print(f"GPIO: setwarnings({flag}) called")

        def setup(self, pin, mode, pull_up_down=None):
            print(f"GPIO: setup(pin={pin}, mode={mode}, pull_up_down={pull_up_down}) called")

        def output(self, pin, value):
            print(f"GPIO: output(pin={pin}, value={value}) called")

        def input(self, pin):
            print(f"GPIO: input(pin={pin}) called")
            return self.LOW # Assume door is always down or up in mock

        def cleanup(self):
            print("GPIO: cleanup called")

    gpio = MockGPIO()


# Cleanup GPIO resources
def cleanup_gpio():
    if GPIO_AVAILABLE:
        gpio.cleanup()

atexit.register(cleanup_gpio)

relay_lock = threading.Lock()

def toggle_door():
    activate_gpio_pin(PIN_DOOR_CONTROL, 0.5)

def buzz_buzzer():
    activate_gpio_pin(PIN_BUZZER, 0.5)

def activate_gpio_pin(pin, duration):
    if GPIO_AVAILABLE:
        with relay_lock:
            gpio.output(pin, gpio.HIGH)
            try:
                time.sleep(duration)
            finally:
                gpio.output(pin, gpio.LOW)
    else:
        print(f"GPIO: Mock activate_gpio_pin(pin={pin}, duration={duration}) called")

def is_door_down():
    if GPIO_AVAILABLE:
        return gpio.input(PIN_DOWN_SENSOR) == gpio.LOW
    else:
        print("GPIO: Mock is_door_down called, returning True")
        return True

def is_door_up():
    if GPIO_AVAILABLE:
        return gpio.input(PIN_UP_SENSOR) == gpio.LOW
    else:
        print("GPIO: Mock is_door_up called, returning False")
        return False

from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "credentials" not in session:
            return redirect(url_for("login"))
        
        creds = Credentials(**session['credentials'])
        
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            session['credentials'] = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            }

        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def index():
    if "credentials" not in session:
        return redirect(url_for("login"))
    return render_template("index.html")

@app.route("/login")
def login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for("callback", _external=True),
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
    )
    session["state"] = state
    return redirect(authorization_url)

@app.route("/callback")
def callback():
    state = session["state"]
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for("callback", _external=True),
    )
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    
    credentials = flow.credentials
    
    # Get user info
    authed_session = AuthorizedSession(credentials)
    userinfo_endpoint = 'https://www.googleapis.com/oauth2/v1/userinfo'
    response = authed_session.get(userinfo_endpoint)
    user_info = response.json()
    
    # Check if user is allowed
    allowed_emails = os.environ.get("ALLOWED_EMAILS", "").split(",")
    if user_info.get("email") not in allowed_emails:
        session.clear()
        return "Unauthorized", 403

    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    session.permanent = True

    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/api/door/up", methods=["POST"])
@login_required
def door_up():
    if is_door_up():
        return jsonify(status="Door is already up"), 200
    toggle_door()
    return jsonify(status="Door is going up"), 200

@app.route("/api/door/down", methods=["POST"])
@login_required
def door_down():
    if is_door_down():
        return jsonify(status="Door is already down"), 200
    toggle_door()
    return jsonify(status="Door is going down"), 200

@app.route("/api/door/status", methods=["GET"])
@login_required
def door_status():
    if is_door_down():
        status = "down"
    elif is_door_up():
        status = "up"
    else:
        status = "in_transition"
    return jsonify(status=status)
