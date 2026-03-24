import os, sys, subprocess, re, tempfile
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

CLIENT_ID     = os.getenv("GDRIVE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("GDRIVE_REFRESH_TOKEN")
FOLDER_ID     = os.getenv("GDRIVE_FOLDER_ID")

def validate_id(id_string):
    if not id_string or not re.match(r'^[a-zA-Z0-9\-_]{25,100}$', id_string):
        return False
    return True

def slugify(name):
    name_no_ext = os.path.splitext(name)[0]
    slugged = re.sub(r'[^a-zA-Z0-9]', '-', name_no_ext)
    return re.sub(r'-+', '-', slugged).strip('-')

def set_github_output(key, value):
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"{key}={value}\n")

def process():
    if len(sys.argv) < 2:
        print("Error: Missing File ID")
        sys.exit(1)

    FILE_ID = sys.argv[1]
    if not validate_id(FILE_ID):
        print("Error: Invalid File ID")
        sys.exit(1)

    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, client_id=CLIENT_ID, 
                            client_secret=CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token")
        service = build('drive', 'v3', credentials=creds)

        file_info = service.files().get(fileId=FILE_ID, fields='name').execute()
        output_filename = f"compressed-{slugify(file_info.get('name', 'video'))}.mp4"

        tmp_in = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        request = service.files().get_media(fileId=FILE_ID)
        with open(tmp_in, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        tmp_out = tempfile.mktemp(suffix=".mp4")
        subprocess.run(['ffmpeg', '-y', '-i', tmp_in, '-vcodec', 'libx264', '-crf', '28', 
                        '-preset', 'faster', '-movflags', '+faststart', tmp_out], 
                       check=True, capture_output=True)

        meta = {'name': output_filename}
        if FOLDER_ID and validate_id(FOLDER_ID):
            meta['parents'] = [FOLDER_ID]

        media = MediaFileUpload(tmp_out, mimetype='video/mp4', resumable=True)
        res = service.files().create(body=meta, media_body=media, fields='id').execute()
        uploaded_id = res.get('id')

        service.permissions().create(fileId=uploaded_id, body={'type': 'anyone', 'role': 'reader'}).execute()

        set_github_output("public_url", f"https://drive.google.com/file/d/{uploaded_id}/view")
        set_github_output("file_name", output_filename)
        set_github_output("file_id", uploaded_id)
        
        print(f"Success: {uploaded_id}")

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    finally:
        for p in [tmp_in, tmp_out]:
            if os.path.exists(p): os.remove(p)

if __name__ == "__main__":
    process()
