import os
import json
import flask
from flask import request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
from twilio.rest import Client
import speech_recognition as sr

# Load environment variables
load_dotenv()

# Twilio Setup
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Flask App for Google Cloud Functions
app = flask.Flask(__name__)

# Google Credentials for Gmail API
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
SERVICE_ACCOUNT_FILE = "credentials.json"

def get_gmail_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('gmail', 'v1', credentials=credentials)
    return service

@app.route('/read-emails', methods=['GET'])
def read_emails():
    service = get_gmail_service()
    results = service.users().messages().list(userId='me', maxResults=5).execute()
    messages = results.get('messages', [])

    email_data = []
    for msg in messages:
        msg_id = msg['id']
        msg_details = service.users().messages().get(userId='me', id=msg_id).execute()
        snippet = msg_details.get('snippet', 'No Content')
        email_data.append({"id": msg_id, "snippet": snippet})

    return jsonify(email_data)

@app.route('/send-email', methods=['POST'])
def send_email():
    data = request.json
    recipient = data.get('to')
    subject = data.get('subject')
    message_body = data.get('message')

    if not recipient or not subject or not message_body:
        return jsonify({"error": "Missing required fields"}), 400

    service = get_gmail_service()
    email_message = f"To: {recipient}\nSubject: {subject}\n\n{message_body}"
    
    message = {
        'raw': email_message.encode('utf-8').hex()
    }

    service.users().messages().send(userId='me', body=message).execute()
    return jsonify({"message": "Email sent successfully!"})

@app.route('/send-sms', methods=['POST'])
def send_sms():
    data = request.json
    to_number = data.get("to")
    message = data.get("message")

    if not to_number or not message:
        return jsonify({"error": "Missing phone number or message"}), 400

    sms = twilio_client.messages.create(
        body=message,
        from_=TWILIO_PHONE_NUMBER,
        to=to_number
    )
    return jsonify({"message": "SMS sent!", "sid": sms.sid})

@app.route('/call', methods=['POST'])
def make_call():
    data = request.json
    to_number = data.get("to")
    message = data.get("message")

    if not to_number or not message:
        return jsonify({"error": "Missing phone number or message"}), 400

    call = twilio_client.calls.create(
        twiml=f"<Response><Say>{message}</Say></Response>",
        from_=TWILIO_PHONE_NUMBER,
        to=to_number
    )
    return jsonify({"message": "Call initiated!", "sid": call.sid})

@app.route('/voice-command', methods=['POST'])
def voice_command():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening for a command...")
        audio = recognizer.listen(source)

    try:
        command = recognizer.recognize_google(audio).lower()
        print(f"Recognized Command: {command}")

        if "read email" in command:
            return read_emails()
        elif "send email" in command:
            return send_email()
        elif "send sms" in command:
            return send_sms()
        elif "call" in command:
            return make_call()
        else:
            return jsonify({"message": "Command not recognized!"})
    except sr.UnknownValueError:
        return jsonify({"error": "Could not understand audio"})
    except sr.RequestError:
        return jsonify({"error": "Could not request results"})

@app.route('/')
def home():
    return jsonify({"message": "AI Email & SMS Assistant is Running!"})

if __name__ == '__main__':
    app.run(debug=True)
