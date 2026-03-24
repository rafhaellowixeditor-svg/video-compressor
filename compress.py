import os
import sys
import subprocess
import re
import tempfile
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

CLIENT_ID     = os.getenv("GDRIVE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GDRIVE_REFRESH_TOKEN")
FOLDER_ID     = os.getenv("GDRIVE_FOLDER_ID")

def validate_file_id(file_id):
    if not file_id or not re.match(r'^[a-zA-Z0-9\-_]{25,100}$', file_id):
        sys.exit(1)

def slugify(name):
    name_no_ext = os.path.splitext(name)[0]
    slugged = re.sub(r'[^a-zA-Z0-9]', '-', name_no_ext)
    slugged = re.sub(r'-+', '-', slugged)
    return slugged.strip('-')

def set_github_output(key, value):
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"{key}={value}\n")

def process():
    if len(sys.argv) < 2:
        print("Error: Missing input File ID.")
        sys.exit(1)

    FILE_ID = sys.argv[1]
    validate_file_id(FILE_ID)

    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("Error: Missing required Google Drive credentials in environment.")
        sys.exit(1)

    try:
        creds = Credentials(
            None,
            refresh_token=REFRESH_TOKEN,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token"
        )
        service = build('drive', 'v3', credentials=creds)

        file_info = service.files().get(fileId=FILE_ID, fields='name').execute()
        slug = slugify(file_info.get('name', 'video'))
        output_filename = f"compressed-{slug}.mp4"

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_in:
            in_path = tmp_in.name
            request = service.files().get_media(fileId=FILE_ID)
            downloader = MediaIoBaseDownload(tmp_in, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

        out_path = tempfile.mktemp(suffix=".mp4")
        try:
            subprocess.run([
                'ffmpeg', '-y', '-i', in_path,
                '-vcodec', 'libx264', '-crf', '28', '-preset', 'faster',
                '-movflags', '+faststart', out_path
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print("Error: FFmpeg compression failed.")
            sys.exit(1)

        file_metadata = {'name': output_filename}
        if FOLDER_ID:
            file_metadata['parents'] = [FOLDER_ID]

        media = MediaFileUpload(out_path, mimetype='video/mp4', resumable=True)
        upload_req = service.files().create(body=file_metadata, media_body=media, fields='id')
        
        response = None
        while response is None:
            status, response = upload_req.next_chunk()

        uploaded_id = response.get('id')

        service.permissions().create(
            fileId=uploaded_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        public_url = f"https://drive.google.com/file/d/{uploaded_id}/view"
        set_github_output("public_url", public_url)
        set_github_output("file_name", output_filename)
        
        print("Process complete. File uploaded successfully.")

    except HttpError as e:
        print(f"Google API Error occurred")
    except Exception:
        print("An unexpected error occurred. Check script logic.")
    finally:
        for p in [in_path, out_path]:
            if 'p' in locals() and os.path.exists(p):
                os.remove(p)

if __name__ == "__main__":
    process()
