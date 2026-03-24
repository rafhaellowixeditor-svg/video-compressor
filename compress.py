import os, sys, subprocess, re, tempfile, base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import uuid

# Config
CLIENT_ID      = os.getenv("GDRIVE_CLIENT_ID")
CLIENT_SECRET  = os.getenv("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN  = os.getenv("GDRIVE_REFRESH_TOKEN")
FOLDER_ID      = os.getenv("GDRIVE_FOLDER_ID")
PUBLIC_KEY_RAW = os.getenv("RSA_PUBLIC_KEY") # This contains your -----BEGIN PUBLIC KEY-----
INPUT_FILE_ID  = os.getenv("GDRIVE_INPUT_FILE_ID")

def format_pem_key(raw_key):
    """
    Ensures the PEM key has correct headers and line breaks.
    This fixes the 'MalformedFraming' error.
    """
    # 1. Strip headers if they exist to get just the base64 data
    clean = raw_key.replace("-----BEGIN PUBLIC KEY-----", "")
    clean = clean.replace("-----END PUBLIC KEY-----", "")
    # 2. Remove all whitespace, newlines, and spaces
    clean = "".join(clean.split())
    
    # 3. Reconstruct with a newline every 64 characters
    formatted = "-----BEGIN PUBLIC KEY-----\n"
    for i in range(0, len(clean), 64):
        formatted += clean[i:i+64] + "\n"
    formatted += "-----END PUBLIC KEY-----"
    return formatted

def encrypt_id(file_id):
    try:
        # Use the formatter to fix the GitHub Secret
        pem_formatted = format_pem_key(PUBLIC_KEY_RAW)
        public_key = serialization.load_pem_public_key(pem_formatted.encode())
        
        ciphertext = public_key.encrypt(
            file_id.encode(),
            padding.PKCS1v15() # Matches JSEncrypt default
        )
        return base64.b64encode(ciphertext).decode()
    except Exception as e:
        print(f"Encryption Error: {str(e)}")
        return None

def process():
    try:
        creds = Credentials(None, refresh_token=REFRESH_TOKEN, client_id=CLIENT_ID, 
                            client_secret=CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token")
        service = build('drive', 'v3', credentials=creds)

        # ... (Download and Compression code remains the same) ...
        print(f"Compressing file: {INPUT_FILE_ID}")
        
        # (Assuming upload is successful and we get uploaded_id)
        # For demonstration, let's say the upload finished:
        # uploaded_id = "1kGYe2asXDwAOdbPXnPSGBu7qsCqPqinD" 

        # --- AFTER UPLOAD ---
        # 1. PRINT THE RAW ID TO GITHUB LOGS
        print(f"RAW_UPLOADED_ID: {uploaded_id}")

        # 2. ENCRYPT
        if PUBLIC_KEY_RAW:
            secure_blob = encrypt_id(uploaded_id)
            if secure_blob:
                print("\n--- SECURE RESULT BEGIN ---")
                print(secure_blob)
                print("--- SECURE RESULT END ---")
        else:
            print("Error: RSA_PUBLIC_KEY not found in environment.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    process()
