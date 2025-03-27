from dotenv import load_dotenv
import os
import requests
import gradio as gr
from datetime import datetime, timedelta
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle


load_dotenv()
hf_token = os.getenv("HF_API_KEY")

# Specialized system prompt for Indian education sector
education_prompt = """You are an expert on the Indian education sector. Your knowledge includes:
- Policies and initiatives (e.g., National Education Policy 2020, Samagra Shiksha)
- Scholarship programs (e.g., National Scholarship Portal, state-specific scholarships)
- Exams and certifications (e.g., JEE, NEET, UPSC, CBSE, ICSE, state boards)
- Educational institutions (e.g., IITs, IIMs, NITs, central universities, state universities)
- Teacher training and recruitment (e.g., TET, B.Ed programs)
- Digital education initiatives (e.g., DIKSHA, SWAYAM, e-Pathshala)
- Funding and grants for education (e.g., RUSA, PM SHRI Schools)
- Vocational and skill development programs (e.g., PMKVY, NSDC)
- International collaborations and rankings (e.g., QS rankings, GATE scores)
- Challenges and reforms in the Indian education system
Provide concise, factual, and accurate answers. If unsure, say "I don't have information about that specific topic."""

# Google Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pickle'

def authenticate_google_calendar():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    return creds

def create_google_calendar_event(event_name, event_datetime):
    creds = authenticate_google_calendar()
    service = build('calendar', 'v3', credentials=creds)

    event = {
        'summary': event_name,
        'start': {
            'dateTime': event_datetime.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': (event_datetime + timedelta(hours=1)).isoformat(),
            'timeZone': 'UTC',
        },
        'reminders': {
            'useDefault': True,  # Use Google Calendar's default reminders
        },
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    return event.get('htmlLink')

# Event database
EVENTS_FILE = "events.json"

def load_events():
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, "r") as f:
            return json.load(f)
    return []

def save_events(events):
    with open(EVENTS_FILE, "w") as f:
        json.dump(events, f)

events = load_events()

def schedule_event(event_name, event_date, event_time):
    try:
        # Validate event name
        if not event_name.strip():
            return "Error: Event name cannot be empty."

        # Combine date and time into a single datetime object
        event_datetime = datetime.strptime(f"{event_date} {event_time}", '%Y-%m-%d %H:%M')

        # Validate event date and time
        if event_datetime < datetime.now():
            return "Error: Event date and time must be in the future."

        # Add event to Google Calendar
        event_link = create_google_calendar_event(event_name, event_datetime)

        # Add event to the database
        events.append({"event_name": event_name, "event_time": event_datetime.strftime('%Y-%m-%d %H:%M')})
        save_events(events)

        return f"Event '{event_name}' scheduled for {event_datetime.strftime('%Y-%m-%d %H:%M')}. <a href='{event_link}' target='_blank'>View in Google Calendar</a>"
    except Exception as e:
        return f"Error scheduling event: {e}"

def get_events():
    if not events:
        return "No events scheduled."
    return "\n".join([f"{event['event_name']} at {event['event_time']}" for event in events])

def delete_event(event_name):
    global events
    events = [event for event in events if event['event_name'] != event_name]
    save_events(events)
    return f"Event '{event_name}' deleted."

def education_chat(message, history):
    input_text = message.lower()

    # Handle event-related queries
    if "get events" in input_text:
        return get_events()

    # Handle education-related queries
    API_URL = ""
    headers = {"Authorization": f""}
    
    # Prepare payload for the API
    payload = {
        "inputs": input_text,  # Only send the user input
        "parameters": {
            "max_new_tokens": 300,  # Limit response length
            "temperature": 0.3,     # Control creativity (lower = more factual)
            "repetition_penalty": 1.2  # Avoid repetition
        }
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()[0]['generated_text']
        else:
            return f"Error: {response.text}"
    except Exception as e:
        return f"Connection error: {str(e)}"

# Gradio Interface
with gr.Blocks() as demo:
    gr.Markdown("# Indian Education Sector Chatbot")
    gr.Markdown("Ask me anything about the Indian education sector or schedule an event.")

    with gr.Tab("Chat"):
        chatbot = gr.ChatInterface(
            education_chat,
            examples=[
                "What is the National Education Policy 2020?",
                "How do I apply for a scholarship in India?",
                "What are the top engineering colleges in India?",
                "Explain the DIKSHA platform.",
                "What is the eligibility for NEET?",
                "How does the PM SHRI Schools initiative work?",
                "Get events"
            ]
        )

    with gr.Tab("Schedule Event"):
        with gr.Row():
            event_name = gr.Textbox(label="Event Name", placeholder="Enter event name")
            event_date = gr.Dropdown(label="Date", choices=[(datetime.today() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)])
            event_time = gr.Dropdown(label="Time", choices=[f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]])
        schedule_button = gr.Button("Schedule Event")
        schedule_output = gr.Textbox(label="Output", interactive=False)
        schedule_button.click(
            lambda name, date, time: schedule_event(name, date, time),
            inputs=[event_name, event_date, event_time],
            outputs=schedule_output
        )

        # Display scheduled events
        events_display = gr.Textbox(label="Scheduled Events", value=get_events(), interactive=False)
        delete_event_name = gr.Textbox(label="Delete Event", placeholder="Enter event name to delete")
        delete_button = gr.Button("Delete Event")
        delete_output = gr.Textbox(label="Output", interactive=False)
        delete_button.click(delete_event, inputs=delete_event_name, outputs=delete_output)

        # Refresh events display after scheduling or deleting
        schedule_button.click(lambda: get_events(), outputs=events_display)
        delete_button.click(lambda: get_events(), outputs=events_display)

# Launch the Gradio app
if __name__ == "__main__":
    demo.launch()
