import os, sys, subprocess
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Config from GitHub Secrets
CLIENT_ID = os.getenv("GDRIVE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GDRIVE_REFRESH_TOKEN")
FILE_ID = sys.argv[1] # Received from the web form

creds = Credentials(None, refresh_token=REFRESH_TOKEN, client_id=CLIENT_ID, client_secret=CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token")
service = build('drive', 'v3', credentials=creds)

def process():
    # 1. Download
    request = service.files().get_media(fileId=FILE_ID)
    with open("input.mp4", "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%")

    # 2. Compress (CRF 28 is high compression, preset faster saves time)
    print("Compressing...")
    subprocess.run(['ffmpeg', '-i', 'input.mp4', '-vcodec', 'libx264', '-crf', '28', '-preset', 'faster', 'output.mp4'])

    # 3. Upload
    file_metadata = {'name': 'Compressed_Video.mp4'}
    media = MediaFileUpload('output.mp4', mimetype='video/mp4')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Finished! New File ID: {file.get('id')}")

if __name__ == "__main__":
    process()