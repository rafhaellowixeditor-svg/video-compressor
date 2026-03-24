import os, sys, subprocess, re, tempfile, base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import uuid

# Config from Environment
CLIENT_ID      = os.getenv("GDRIVE_CLIENT_ID")
CLIENT_SECRET  = os.getenv("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN  = os.getenv("GDRIVE_REFRESH_TOKEN")
FOLDER_ID      = os.getenv("GDRIVE_FOLDER_ID")
PUBLIC_KEY_RAW = os.getenv("RSA_PUBLIC_KEY")
INPUT_FILE_ID  = os.getenv("GDRIVE_INPUT_FILE_ID")

def format_pem_key(raw_key):
    """Ensures the PEM key has correct headers and line breaks."""
    clean = raw_key.replace("-----BEGIN PUBLIC KEY-----", "")
    clean = clean.replace("-----END PUBLIC KEY-----", "")
    clean = "".join(clean.split())
    formatted = "-----BEGIN PUBLIC KEY-----\n"
    for i in range(0, len(clean), 64):
        formatted += clean[i:i+64] + "\n"
    formatted += "-----END PUBLIC KEY-----"
    return formatted

def encrypt_id(file_id):
    """Encrypts the File ID using PKCS1v15 padding for JS compatibility."""
    try:
        pem_formatted = format_pem_key(PUBLIC_KEY_RAW)
        public_key = serialization.load_pem_public_key(pem_formatted.encode())
        ciphertext = public_key.encrypt(
            file_id.encode(),
            padding.PKCS1v15()
        )
        return base64.b64encode(ciphertext).decode()
    except Exception as e:
        print(f"Encryption Error: {str(e)}")
        return None

def validate_id(id_string):
    return bool(id_string and re.match(r'^[a-zA-Z0-9\-_]{25,100}$', id_string))

def process():
    if not validate_id(INPUT_FILE_ID):
        print("Error: Invalid Input ID")
        sys.exit(1)

    # Initialize variables to ensure cleanup works even if upload fails
    tmp_in = None
    tmp_out = None

    try:
        # 1. Setup Service
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, client_id=CLIENT_ID, 
                            client_secret=CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token")
        service = build('drive', 'v3', credentials=creds)

        # 2. Download Source
        print(f"Downloading source: {INPUT_FILE_ID}")
        request = service.files().get_media(fileId=INPUT_FILE_ID)
        tmp_in_handler = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp_in = tmp_in_handler.name
        
        downloader = MediaIoBaseDownload(tmp_in_handler, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        tmp_in_handler.close()

        # 3. Compress with FFmpeg
        print("Compressing...")
        tmp_out = tempfile.mktemp(suffix=".mp4")
        # Silence FFmpeg to prevent leaking info in public logs
        subprocess.run([
            'ffmpeg', '-y', '-i', tmp_in, 
            '-vcodec', 'libx264', '-crf', '28', 
            '-preset', 'faster', '-movflags', '+faststart', 
            tmp_out
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 4. Upload to Drive
        print("Uploading compressed version...")
        random_name = f"{uuid.uuid4().hex}.mp4"
        file_metadata = {'name': random_name}
        if FOLDER_ID:
            file_metadata['parents'] = [FOLDER_ID]

        media = MediaFileUpload(tmp_out, mimetype='video/mp4', resumable=True)
        file_obj = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        
        # SUCCESS! Here is the defined uploaded_id
        uploaded_id = file_obj.get('id')
        print(f"RAW_UPLOADED_ID: {uploaded_id}")

        # 5. Set Permissions
        service.permissions().create(fileId=uploaded_id, body={'type': 'anyone', 'role': 'reader'}).execute()

        # 6. Encrypt the Result for Web App
        if PUBLIC_KEY_RAW:
            secure_blob = encrypt_id(uploaded_id)
            if secure_blob:
                print("\n--- SECURE RESULT BEGIN ---")
                print(secure_blob)
                print("--- SECURE RESULT END ---")
        else:
            print("Warning: RSA_PUBLIC_KEY not found in environment.")

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    finally:
        # Cleanup temp files
        if tmp_in and os.path.exists(tmp_in): os.remove(tmp_in)
        if tmp_out and os.path.exists(tmp_out): os.remove(tmp_out)

if __name__ == "__main__":
    process()
