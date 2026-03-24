import os, sys, subprocess, re, tempfile, base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

CLIENT_ID      = os.getenv("GDRIVE_CLIENT_ID")
CLIENT_SECRET  = os.getenv("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN  = os.getenv("GDRIVE_REFRESH_TOKEN")
FOLDER_ID      = os.getenv("GDRIVE_FOLDER_ID")
PUBLIC_KEY_PEM = os.getenv("RSA_PUBLIC_KEY")

def encrypt_id(file_id):
    """Encrypts the File ID using the RSA Public Key."""
    public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM.encode())
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

def slugify(name):
    name_no_ext = os.path.splitext(name)[0]
    slugged = re.sub(r'[^a-zA-Z0-9]', '-', name_no_ext)
    return re.sub(r'-+', '-', slugged).strip('-')

def process():
    if len(sys.argv) < 2:
        print("Error: Missing input File ID")
        sys.exit(1)

    FILE_ID = sys.argv[1]
    if not validate_id(FILE_ID):
        print("Error: Invalid Input ID")
        sys.exit(1)

    tmp_in = None
    tmp_out = None

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

        if PUBLIC_KEY_PEM:
            secure_blob = encrypt_id(uploaded_id)
            print(secure_blob)
        else:
            print("Warning: RSA_PUBLIC_KEY not found, ID not encrypted.")

    except Exception as e:
        print(f"Error during processing: {str(e)}")
        sys.exit(1)
    finally:
        if tmp_in and os.path.exists(tmp_in): os.remove(tmp_in)
        if tmp_out and os.path.exists(tmp_out): os.remove(tmp_out)

if __name__ == "__main__":
    process()
