import os
import base64
import datetime
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = Flask(__name__)
SCOPES = ["https://www.googleapis.com/auth/calendar"]
SERVICE_ACCOUNT_FILE = "service_account.json"

# At startup, decode SERVICE_ACCOUNT_B64 into a file
if os.getenv("SERVICE_ACCOUNT_B64"):
    decoded = base64.b64decode(os.getenv("SERVICE_ACCOUNT_B64"))
    with open(SERVICE_ACCOUNT_FILE, "wb") as f:
        f.write(decoded)

def get_google_credentials():
    # Use service account credentials for a headless environment
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return creds

@app.route("/events", methods=["GET"])
def list_calendar_events():
    creds = get_google_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        if not events:
            return jsonify({"message": "No upcoming events found."})
        formatted = [
            {
                "summary": e.get("summary"),
                "start": e["start"].get("dateTime", e["start"].get("date")),
                "location": e.get("location"),
            }
            for e in events
        ]
        return jsonify(formatted)
    except HttpError as error:
        return jsonify({"error": f"Google API Error: {error}"}), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500

@app.route("/events", methods=["POST"])
def create_calendar_event():
    creds = get_google_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        event_data = request.get_json(silent=True)
        if not event_data:
            return jsonify({"error": "No event data provided"}), 400

        required = ["summary", "start", "end"]
        if not all(field in event_data for field in required):
            return (
                jsonify({"error": f"Missing required fields: {', '.join(required)}"}),
                400,
            )

        event = {
            "summary": event_data["summary"],
            "location": event_data.get("location"),
            "description": event_data.get("description"),
            "start": {"dateTime": event_data["start"], "timeZone": event_data.get("timeZone", "UTC")},
            "end": {"dateTime": event_data["end"], "timeZone": event_data.get("timeZone", "UTC")},
            "recurrence": event_data.get("recurrence"),
            "attendees": event_data.get("attendees"),
            "reminders": event_data.get("reminders"),
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return (
            jsonify({"message": "Event created", "htmlLink": created.get("htmlLink"), "id": created.get("id")}),
            201,
        )
    except HttpError as error:
        return jsonify({"error": f"Google API Error: {error}"}), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
