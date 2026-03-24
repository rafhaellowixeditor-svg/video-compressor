import os, sys, subprocess, re, tempfile, base64, uuid
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Config
CLIENT_ID      = os.getenv("GDRIVE_CLIENT_ID")
CLIENT_SECRET  = os.getenv("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN  = os.getenv("GDRIVE_REFRESH_TOKEN")
FOLDER_ID      = os.getenv("GDRIVE_FOLDER_ID")
PUBLIC_KEY_B64 = os.getenv("RSA_PUBLIC_KEY")
INPUT_FILE_ID  = os.getenv("GDRIVE_INPUT_FILE_ID")

def get_public_key():
    """Decodes Base64 and loads the X.509 Public Key."""
    try:
        # 1. Decode the Base64 string from GitHub Secrets
        decoded_bytes = base64.b64decode(PUBLIC_KEY_B64)
        
        # 2. Load the Public Key (supports X.509 / SubjectPublicKeyInfo)
        return serialization.load_pem_public_key(decoded_bytes)
    except Exception as e:
        print(f"Key Loading Error: {str(e)}")
        return None

def encrypt_id(file_id):
    """Encrypts using PKCS1v15 padding (Required for JSEncrypt)."""
    public_key = get_public_key()
    if not public_key: return None
    try:
        ciphertext = public_key.encrypt(
            file_id.encode(),
            padding.PKCS1v15() 
        )
        return base64.b64encode(ciphertext).decode()
    except Exception as e:
        print(f"Encryption Error: {str(e)}")
        return None

def process():
    try:
        # --- PREPARATION & AUTH ---
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, client_id=CLIENT_ID, 
                            client_secret=CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token")
        service = build('drive', 'v3', credentials=creds)

        # --- DOWNLOAD ---
        print(f"Downloading: {INPUT_FILE_ID}")
        request = service.files().get_media(fileId=INPUT_FILE_ID)
        tmp_in = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        with open(tmp_in, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        # --- COMPRESS ---
        print("Compressing...")
        tmp_out = tempfile.mktemp(suffix=".mp4")
        subprocess.run(['ffmpeg', '-y', '-i', tmp_in, '-vcodec', 'libx264', '-crf', '28', 
                        '-preset', 'faster', '-movflags', '+faststart', tmp_out], 
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # --- UPLOAD ---
        print("Uploading...")
        file_metadata = {'name': f"{uuid.uuid4().hex}.mp4"}
        if FOLDER_ID: file_metadata['parents'] = [FOLDER_ID]
        media = MediaFileUpload(tmp_out, mimetype='video/mp4', resumable=True)
        uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        uploaded_id = uploaded_file.get('id')

        # --- PERMISSIONS ---
        service.permissions().create(fileId=uploaded_id, body={'type': 'anyone', 'role': 'reader'}).execute()

        # --- OUTPUT ---
        print(f"RAW_UPLOADED_ID: {uploaded_id}")
        secure_blob = encrypt_id(uploaded_id)
        if secure_blob:
            print("\n--- SECURE RESULT BEGIN ---")
            print(secure_blob)
            print("--- SECURE RESULT END ---")

    except Exception as e:
        print(f"Process Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    process()
