import os, sys, subprocess
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

CLIENT_ID = os.getenv("GDRIVE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GDRIVE_REFRESH_TOKEN")
FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")

if len(sys.argv) < 2:
    print("Error: No File ID provided")
    sys.exit(1)

FILE_ID = sys.argv[1]

creds = Credentials(None, refresh_token=REFRESH_TOKEN, client_id=CLIENT_ID, client_secret=CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token")
service = build('drive', 'v3', credentials=creds)

def process():
    request = service.files().get_media(fileId=FILE_ID)
    with open("input.mp4", "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Download Progress: {int(status.progress() * 100)}%")

    subprocess.run(['ffmpeg', '-i', 'input.mp4', '-vcodec', 'libx264', '-crf', '28', '-preset', 'faster', 'output.mp4'])
    
    output_filename = f"COMPRESSED-{os.path.basename('output.mp4').upper()}"
    file_metadata = {'name': output_filename}
    if FOLDER_ID:
        file_metadata['parents'] = [FOLDER_ID]

    media = MediaFileUpload('output.mp4', mimetype='video/mp4', resumable=True)
    request = service.files().create(body=file_metadata, media_body=media, fields='id')
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload Progress: {int(status.progress() * 100)}%")

    print(f"Finished! New File ID: {response.get('id')}")

if __name__ == "__main__":
    process()
