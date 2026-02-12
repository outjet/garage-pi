
import os
from flask import Flask, redirect, url_for, session, render_template, jsonify, request
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request, AuthorizedSession
import requests
import RPi.GPIO as gpio
import time
import threading
from dotenv import load_dotenv
import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SERVER_NAME'] = 'outgar.duckdns.org:8443'
app.secret_key = os.environ.get("SECRET_KEY")
app.permanent_session_lifetime = datetime.timedelta(hours=24)

# OAuth 2.0 configuration
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # Remove in production
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile", "openid"]

# GPIO Pin Constants
PIN_DOWN_SENSOR = int(os.getenv('PIN_DOWN_SENSOR', 20))
PIN_UP_SENSOR = int(os.getenv('PIN_UP_SENSOR', 21))
PIN_DOOR_CONTROL = int(os.getenv('PIN_DOOR_CONTROL', 16))
PIN_BUZZER = int(os.getenv('PIN_BUZZER', 19))

# GPIO setup function
def setup_gpio():
    gpio.setmode(gpio.BCM)
    gpio.setwarnings(False)
    gpio.setup(PIN_DOWN_SENSOR, gpio.IN, pull_up_down=gpio.PUD_UP)
    gpio.setup(PIN_UP_SENSOR, gpio.IN, pull_up_down=gpio.PUD_UP)
    gpio.setup(PIN_DOOR_CONTROL, gpio.OUT)
    gpio.setup(PIN_BUZZER, gpio.OUT)

# Cleanup GPIO resources
def cleanup_gpio():
    gpio.cleanup()

with app.app_context():
    setup_gpio()

relay_lock = threading.Lock()

def toggle_door():
    activate_gpio_pin(PIN_DOOR_CONTROL, 0.5)

def buzz_buzzer():
    activate_gpio_pin(PIN_BUZZER, 0.5)

def activate_gpio_pin(pin, duration):
    with relay_lock:
        gpio.output(pin, gpio.HIGH)
        try:
            time.sleep(duration)
        finally:
            gpio.output(pin, gpio.LOW)

def is_door_down():
    return gpio.input(PIN_DOWN_SENSOR) == gpio.LOW

def is_door_up():
    return gpio.input(PIN_UP_SENSOR) == gpio.LOW

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
