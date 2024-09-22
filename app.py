import pytesseract
from PIL import Image
import re
from datetime import datetime
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime
import os.path
import pickle
import json
import requests

SCOPES = ["https://www.googleapis.com/auth/calendar"]


# Load credentials and create service
def create_google_calendar_service():
    creds = None

    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    service = build("calendar", "v3", credentials=creds)
    return service


def perform_ocr(image_path):
    """Perform OCR on the image and return extracted text."""
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image)
    return text


def extract_information(text):
    """Extract dates, times, and courts from the text."""
    date_pattern = r"\b\w{3} \d{1,2}\.\d\b"
    time_pattern = r"Time: [\w\s\.\d]+ (\d{2}:\d{2} - \d{2}:\d{2})"
    court_pattern = r"\bLocation: ([\w\s/]+/Court \d)\b"

    dates = re.findall(date_pattern, text)
    times = re.findall(time_pattern, text)
    courts = re.findall(court_pattern, text)

    return dates, times, courts


def create_reservations(dates, times, courts):
    """Create a list of reservation dictionaries from extracted information."""
    reservations = []
    for i in range(
        len(courts)
    ):  # Adjusting the length to match the number of actual events
        try:
            reservation = {
                "date": dates[i * 2],  # Adjusting for duplicate dates
                "time": times[i],
                "court": courts[i],
            }
            reservations.append(reservation)
        except IndexError as e:
            print(f"Error: {e}, at index: {i}")
    return reservations


def parse_datetime(date_str, time_str):
    """Parse date and time strings into datetime objects with Finland's time zone."""
    day, month = map(int, date_str.split()[1].split("."))
    start_time, end_time = time_str.split(" - ")
    start_hour, start_minute = map(int, start_time.split(":"))
    end_hour, end_minute = map(int, end_time.split(":"))
    current_year = datetime.now().year
    start_datetime = datetime(
        current_year, month, day, start_hour, start_minute
    )
    end_datetime = datetime(current_year, month, day, end_hour, end_minute)
    return start_datetime, end_datetime


def read_invited_emails():
    with open('invited.json', 'r',  encoding='utf-8') as f:
        data = json.load(f)
    email = data['email']
    return email

def create_google_calendar_event(service, reservation, calendar_id="primary"):
    """Create a Google Calendar event from the reservation."""
    start_datetime, end_datetime = parse_datetime(
        reservation["date"], reservation["time"]
    )
    event = {
        "summary": reservation["court"],
        "start": {
            "dateTime": start_datetime.isoformat(),
            "timeZone": "Europe/Helsinki",
        },
        "end": {
            "dateTime": end_datetime.isoformat(),
            "timeZone": "Europe/Helsinki",
        },
        'attendees': [
            {'email': read_invited_emails()},
        ],
        'reminders': {
            'useDefault': True,
        },
    }
    event = service.events().insert(calendarId=calendar_id, body=event, sendUpdates="all").execute()
    print(f"Event created: {event.get('htmlLink')}")

def get_image_from_pasteboard(url):
    # Convert the Pasteboard link to a direct image link
    image_id = url.split('/')[-1]
    direct_image_url = f"https://gcdnb.pbrd.co/images/{image_id}?o=1"
    
    # Fetch the image from the direct link
    response = requests.get(direct_image_url)
    response.raise_for_status()  # Check if the request was successful
    
    # Save the image to a file
    with open("image.jpg", "wb") as f:
        f.write(response.content)

def main():
    # Prompt user to paste the URL of the image
    url = input("Paste the URL of the image: ")
    get_image_from_pasteboard(url)
    image_path = "image.jpg"
    print("Image downloaded successfully!")

    # Perform OCR and extract information
    text = perform_ocr(image_path)
    dates, times, courts = extract_information(text)
    reservations = create_reservations(dates, times, courts)

    # Create Google Calendar service
    service = create_google_calendar_service()

    # # Create Google Calendar events
    for reservation in reservations:
        create_google_calendar_event(service, reservation)
        


if __name__ == "__main__":
    main()
