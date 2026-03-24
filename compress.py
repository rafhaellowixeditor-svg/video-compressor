import os, sys, subprocess, tempfile, uuid
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
CLIENT_ID     = os.getenv("GDRIVE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GDRIVE_REFRESH_TOKEN")
FOLDER_ID     = os.getenv("GDRIVE_FOLDER_ID")
INPUT_FILE_ID = os.getenv("GDRIVE_INPUT_FILE_ID")
def process():
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, client_id=CLIENT_ID,
                            client_secret=CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token")
        service = build('drive', 'v3', credentials=creds)
        request = service.files().get_media(fileId=INPUT_FILE_ID)
        tmp_in = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        with open(tmp_in, "wb") as f:
            from googleapiclient.http import MediaIoBaseDownload
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        tmp_out = tempfile.mktemp(suffix=".mp4")
        subprocess.run(['ffmpeg', '-y', '-i', tmp_in, '-vcodec', 'libx264', '-crf', '28',
                        '-preset', 'faster', '-movflags', '+faststart', tmp_out],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        file_metadata = {'name': f"{uuid.uuid4().hex}.mp4"}
        if FOLDER_ID: file_metadata['parents'] = [FOLDER_ID]
        media = MediaFileUpload(tmp_out, mimetype='video/mp4', resumable=True)
        uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        uploaded_id = uploaded_file.get('id')
        service.permissions().create(fileId=uploaded_id, body={'type': 'anyone', 'role': 'reader'}).execute()
        print(f"\n--- RESULT BEGIN ---")
        print(uploaded_id)
        print(f"--- RESULT END ---")
    except Exception as e:
        print(f"Process Error: {e}")
        sys.exit(1)
if __name__ == "__main__":
    process()
