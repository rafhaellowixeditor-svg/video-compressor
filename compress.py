import os, sys, subprocess, re, tempfile, base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import uuid

CLIENT_ID      = os.getenv("GDRIVE_CLIENT_ID")
CLIENT_SECRET  = os.getenv("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN  = os.getenv("GDRIVE_REFRESH_TOKEN")
FOLDER_ID      = os.getenv("GDRIVE_FOLDER_ID")
PUBLIC_KEY_RAW = os.getenv("RSA_PUBLIC_KEY")
INPUT_FILE_ID  = os.getenv("GDRIVE_INPUT_FILE_ID")

def format_pem_key(raw_key):
    clean_key = raw_key.replace("-----BEGIN PUBLIC KEY-----", "")
    clean_key = clean_key.replace("-----END PUBLIC KEY-----", "")
    clean_key = "".join(clean_key.split())
    
    formatted = "-----BEGIN PUBLIC KEY-----\n"
    for i in range(0, len(clean_key), 64):
        formatted += clean_key[i:i+64] + "\n"
    formatted += "-----END PUBLIC KEY-----"
    return formatted

def encrypt_id(file_id):
    try:
        pem_data = format_pem_key(PUBLIC_KEY_RAW)
        public_key = serialization.load_pem_public_key(pem_data.encode())
        
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

    tmp_in, tmp_out = None, None

    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, client_id=CLIENT_ID, 
                            client_secret=CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token")
        service = build('drive', 'v3', credentials=creds)

        print("Downloading source...")
        request = service.files().get_media(fileId=INPUT_FILE_ID)
        tmp_in = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        with open(tmp_in, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        print("Compressing...")
        tmp_out = tempfile.mktemp(suffix=".mp4")
        subprocess.run(['ffmpeg', '-y', '-i', tmp_in, '-vcodec', 'libx264', '-crf', '28', 
                        '-preset', 'faster', '-movflags', '+faststart', tmp_out], 
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("Uploading...")
        meta = {'name': 'temp.mp4'}
        if FOLDER_ID: meta['parents'] = [FOLDER_ID]

        media = MediaFileUpload(tmp_out, mimetype='video/mp4', resumable=True)
        res = service.files().create(body=meta, media_body=media, fields='id').execute()
        uploaded_id = res.get('id')

        random_uid = uuid.uuid4().hex 
        new_name = f"{random_uid}.mp4"
        service.files().update(fileId=uploaded_id, body={'name': new_name}).execute()

        service.permissions().create(fileId=uploaded_id, body={'type': 'anyone', 'role': 'reader'}).execute()

        if PUBLIC_KEY_RAW:
            secure_blob = encrypt_id(uploaded_id)
            if secure_blob:
                print("\n--- SECURE RESULT BEGIN ---")
                print(secure_blob)
                print("--- SECURE RESULT END ---")
        else:
            print(f"DEBUG_UPLOADED_ID: {uploaded_id}")

    except Exception as e:
        print(f"An error occurred.")
        sys.exit(1)
    finally:
        if tmp_in and os.path.exists(tmp_in): os.remove(tmp_in)
        if tmp_out and os.path.exists(tmp_out): os.remove(tmp_out)

if __name__ == "__main__":
    process()
