import os, sys, subprocess, re, tempfile, base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Get Config from Environment
CLIENT_ID      = os.getenv("GDRIVE_CLIENT_ID")
CLIENT_SECRET  = os.getenv("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN  = os.getenv("GDRIVE_REFRESH_TOKEN")
FOLDER_ID      = os.getenv("GDRIVE_FOLDER_ID")
PUBLIC_KEY_B64 = os.getenv("RSA_PUBLIC_KEY")
INPUT_FILE_ID  = os.getenv("GDRIVE_INPUT_FILE_ID")

def setup_security():
    if INPUT_FILE_ID:
        print(f"::add-mask::{INPUT_FILE_ID}")

def get_public_key():
    """Decodes the Base64 key and loads it correctly."""
    try:
        key_data = base64.b64decode(PUBLIC_KEY_B64)
        return serialization.load_pem_public_key(key_data)
    except Exception as e:
        print(f"Error: Could not load RSA Public Key. {e}")
        sys.exit(1)

def encrypt_id(file_id):
    """Encrypts the Output ID."""
    public_key = get_public_key()
    ciphertext = public_key.encrypt(
        file_id.encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(ciphertext).decode()

def validate_id(id_string):
    if not id_string or not re.match(r'^[a-zA-Z0-9\-_]{25,100}$', id_string):
        return False
    return True

def process():
    setup_security()
    
    if not validate_id(INPUT_FILE_ID):
        print("Error: Invalid Input ID.")
        sys.exit(1)

    tmp_in, tmp_out = None, None

    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, client_id=CLIENT_ID, 
                            client_secret=CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token")
        service = build('drive', 'v3', credentials=creds)

        file_info = service.files().get(fileId=INPUT_FILE_ID, fields='name').execute()

        tmp_in = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        request = service.files().get_media(fileId=INPUT_FILE_ID)
        with open(tmp_in, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        tmp_out = tempfile.mktemp(suffix=".mp4")
        subprocess.run(['ffmpeg', '-y', '-i', tmp_in, '-vcodec', 'libx264', '-crf', '28', 
                        '-preset', 'faster', '-movflags', '+faststart', tmp_out], 
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    
        meta = {'name': f"output-{INPUT_FILE_ID[:5]}.mp4"}
        if FOLDER_ID: meta['parents'] = [FOLDER_ID]

        media = MediaFileUpload(tmp_out, mimetype='video/mp4', resumable=True)
        res = service.files().create(body=meta, media_body=media, fields='id').execute()
        uploaded_id = res.get('id')

        service.permissions().create(fileId=uploaded_id, body={'type': 'anyone', 'role': 'reader'}).execute()

        secure_blob = encrypt_id(uploaded_id)
        print("\n--- SECURE RESULT BEGIN ---")
        print(secure_blob)
        print("--- SECURE RESULT END ---")

    except Exception:
        print("An error occurred during processing.")
        sys.exit(1)
    finally:
        if tmp_in and os.path.exists(tmp_in): os.remove(tmp_in)
        if tmp_out and os.path.exists(tmp_out): os.remove(tmp_out)

if __name__ == "__main__":
    process()
