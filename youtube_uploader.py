import os
import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import pickle

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_authenticated_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secrets.json'):
                print("Error: client_secrets.json not found. Please follow setup instructions.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)

def upload_video(video_path, metadata_path, schedule_hours=6):
    youtube = get_authenticated_service()
    if not youtube: return

    # Parse metadata
    title, desc, tags = "Reddit Story", "Check out this story!", ["reddit"]
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("TITLE:"): title = line.replace("TITLE:", "").strip()
                if line.startswith("DESCRIPTION:"): desc = line.replace("DESCRIPTION:", "").strip()
                if line.startswith("TAGS:"): tags = [t.strip() for t in line.replace("TAGS:", "").split(",")]

    # Calculate schedule time (ISO 8601 format)
    publish_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=schedule_hours)).isoformat()

    body = {
        'snippet': {
            'title': title[:100], # YouTube limit
            'description': desc,
            'tags': tags,
            'categoryId': '24' # Entertainment
        },
        'status': {
            'privacyStatus': 'private', # Must be private to use publishAt
            'publishAt': publish_at,
            'selfDeclaredMadeForKids': False
        }
    }

    print(f"Uploading: {title} (Scheduled for {publish_at})")
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    print(f"Upload Complete! Video ID: {response['id']}")
    return response['id']
