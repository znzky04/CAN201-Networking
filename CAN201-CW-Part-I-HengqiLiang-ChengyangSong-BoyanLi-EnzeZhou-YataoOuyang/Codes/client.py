import socket
import json
import struct
import hashlib
import base64
import os
import math
import time
import argparse

SERVER_PORT = 1379  # Server port; ensure it matches the port number in server.py

MAX_PACKET_SIZE = 20480

# Constant definitions
OP_LOGIN = 'LOGIN'
OP_SAVE = 'SAVE'
OP_UPLOAD = 'UPLOAD'
OP_GET = 'GET'
DIR_REQUEST = 'REQUEST'
DIR_RESPONSE = 'RESPONSE'
TYPE_AUTH = 'AUTH'
TYPE_FILE = 'FILE'
FIELD_OPERATION = 'operation'
FIELD_DIRECTION = 'direction'
FIELD_TYPE = 'type'
FIELD_USERNAME = 'username'
FIELD_PASSWORD = 'password'
FIELD_TOKEN = 'token'
FIELD_STATUS = 'status'
FIELD_STATUS_MSG = 'status_msg'
FIELD_KEY = 'key'
FIELD_SIZE = 'size'
FIELD_TOTAL_BLOCK = 'total_block'
FIELD_BLOCK_SIZE = 'block_size'
FIELD_BLOCK_INDEX = 'block_index'
FIELD_MD5 = 'md5'


def _argparse():
    parse = argparse.ArgumentParser()
    parse.add_argument("--server_ip", type=str, required=True, help="Server IP address")
    parse.add_argument("--id", type=str, required=True, help="User ID")
    parse.add_argument("--f", type=str, required=True, help="Path to the file to upload")
    return parse.parse_args()


def make_packet(json_data, bin_data=None):
    """
    Creates a data packet following the STEP protocol
    """
    j = json.dumps(dict(json_data), ensure_ascii=False)
    j_len = len(j)
    if bin_data is None:
        return struct.pack('!II', j_len, 0) + j.encode()
    else:
        return struct.pack('!II', j_len, len(bin_data)) + j.encode() + bin_data


def get_tcp_packet(conn, max_retries=3):
    for attempt in range(max_retries):
        try:
            bin_data = b''
            while len(bin_data) < 8:
                data_rec = conn.recv(8)
                if data_rec == b'':
                    return None, None
                bin_data += data_rec
            data = bin_data[:8]
            bin_data = bin_data[8:]
            j_len, b_len = struct.unpack('!II', data)
            while len(bin_data) < j_len:
                data_rec = conn.recv(j_len)
                if data_rec == b'':
                    return None, None
                bin_data += data_rec
            j_bin = bin_data[:j_len]
            try:
                json_data = json.loads(j_bin.decode())
            except Exception:
                return None, None
            bin_data = bin_data[j_len:]
            while len(bin_data) < b_len:
                data_rec = conn.recv(b_len)
                if data_rec == b'':
                    return None, None
                bin_data += data_rec
            return json_data, bin_data
        except ConnectionResetError:
            if attempt < max_retries - 1:
                print(f"Connection reset, trying to reconnect... (Try {attempt + 1}/{max_retries})")
                time.sleep(2)  # Wait for 2 seconds before retrying
                continue
            else:
                raise  # Raise an exception if max retries are exceeded


def login(username, password):
    """
    Login function
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((SERVER_IP, SERVER_PORT))
        except ConnectionRefusedError:
            print(
                "Cannot connect to the server. Make sure that the server is running and that the IP address and port number are correct.")
            return None

        # Create login request
        login_request = {
            FIELD_OPERATION: OP_LOGIN,
            FIELD_DIRECTION: DIR_REQUEST,
            FIELD_TYPE: TYPE_AUTH,
            FIELD_USERNAME: username,
            FIELD_PASSWORD: hashlib.md5(password.encode()).hexdigest()
        }

        # Send login request
        s.sendall(make_packet(login_request))

        # Receive server response
        json_data, _ = get_tcp_packet(s)

        if json_data and json_data.get(FIELD_STATUS) == 200:
            print("Log in successfully!")
            return json_data.get(FIELD_TOKEN)
        else:
            print(f"Login Failure: {json_data.get(FIELD_STATUS_MSG) if json_data else 'unknown error'}")
            return None


def save_token(token):
    """
    Save token to file
    """
    with open("token.txt", "w") as f:
        f.write(token)
    print("Token has been saved to the token.txt file")


def upload_file(token, file_path, max_retries=3):
    for attempt in range(max_retries):
        try:
            # Get file size
            file_size = os.path.getsize(file_path)

            # Add file size check (10MB = 10 * 1024 * 1024 bytes)
            size_limit = 10 * 1024 * 1024  # 10MB in bytes
            if file_size > size_limit:
                print(f"Warning: File size ({file_size / 1024 / 1024:.2f}MB) exceeds the recommended limit of 10MB")
                user_input = input("Do you want to continue anyway? (y/n): ")
                if user_input.lower() != 'y':
                    print("Upload cancelled by user")
                    return False

            # Convert file size to human-readable format
            def convert_size(size_bytes):
                if size_bytes == 0:
                    return "0B"
                size_name = ("B", "KB", "MB", "GB", "TB")
                i = int(math.floor(math.log(size_bytes, 1024)))
                p = math.pow(1024, i)
                s = round(size_bytes / p, 2)
                return f"{s} {size_name[i]}"

            readable_size = convert_size(file_size)
            print(f"Start uploading files: {os.path.basename(file_path)} (Size: {readable_size})")

            # Start timing
            start_time = time.time()

            # Step 1: Request upload operation
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.connect((SERVER_IP, SERVER_PORT))
                except ConnectionRefusedError:
                    print(
                        f"Unable to connect to the server {SERVER_IP}:{SERVER_PORT}. Make sure the server is running.")
                    return

                save_request = {
                    FIELD_OPERATION: OP_SAVE,
                    FIELD_DIRECTION: DIR_REQUEST,
                    FIELD_TYPE: TYPE_FILE,
                    FIELD_TOKEN: token,
                    FIELD_KEY: os.path.basename(file_path),
                    FIELD_SIZE: file_size
                }

                s.sendall(make_packet(save_request))

                # Step 2: Receive upload plan
                json_data, _ = get_tcp_packet(s)

                if json_data is None:
                    raise Exception("The server did not return a valid response.")

                if json_data.get(FIELD_STATUS) != 200:
                    raise Exception(
                        f"Failed to upload: Status Code {json_data.get(FIELD_STATUS)}, error message: {json_data.get(FIELD_STATUS_MSG)}")

                # Step 3: Upload file in blocks
                with open(file_path, 'rb') as file:
                    total_block = json_data.get(FIELD_TOTAL_BLOCK)
                    block_size = json_data.get(FIELD_BLOCK_SIZE)
                    key = json_data.get(FIELD_KEY)

                    # Show upload progress
                    uploaded_size = 0
                    for block_index in range(total_block):
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.connect((SERVER_IP, SERVER_PORT))

                            file.seek(block_index * block_size)
                            block_data = file.read(block_size)
                            uploaded_size += len(block_data)

                            # Calculate upload progress percentage
                            progress = (uploaded_size / file_size) * 100

                            upload_request = {
                                FIELD_OPERATION: OP_UPLOAD,
                                FIELD_DIRECTION: DIR_REQUEST,
                                FIELD_TYPE: TYPE_FILE,
                                FIELD_TOKEN: token,
                                FIELD_KEY: key,
                                FIELD_BLOCK_INDEX: block_index
                            }

                            s.sendall(make_packet(upload_request, block_data))

                            json_data, _ = get_tcp_packet(s)

                            if json_data and json_data[FIELD_STATUS] == 200:
                                print(f"block {block_index + 1}/{total_block} Uploaded successfully ({progress:.1f}%)")
                            else:
                                print(
                                    f"block {block_index + 1}/{total_block} Upload Failed: {json_data[FIELD_STATUS_MSG] if json_data else 'unknown error'}")
                                return False

            # End timing and calculate time and average speed
            end_time = time.time()
            upload_time = end_time - start_time
            speed = file_size / upload_time / 1024 / 1024  # MB/s

            print(f"\nUpload completed:")
            print(f"file size: {readable_size}")
            print(f"Taking time:: {upload_time:.2f} seconds")
            print(f"average speed: {speed:.2f} MB/s")

            # Add MD5 display after upload is complete
            if json_data and json_data.get(FIELD_MD5):
                print(f"\nServer file MD5: {json_data[FIELD_MD5]}")
                # Calculate the MD5 of local files
                with open(file_path, 'rb') as f:
                    local_md5 = hashlib.md5(f.read()).hexdigest()
                print(f"Local file MD5: {local_md5}")

                if json_data[FIELD_MD5] == local_md5:
                    print("MD5 verification successful - File uploaded correctly")
                else:
                    print("MD5 verification failed - File might be corrupted")

            return True

        except Exception as e:
            print(f"Try {attempt + 1}/{max_retries} failed: {str(e)}")
            if attempt < max_retries - 1:
                print("Waiting 5 seconds before retrying...")
                time.sleep(5)
            else:
                print("Upload failed, maximum retry attempts reached")
                return False


def verify_server_file(token, file_key):
    """
    Send a GET request to the server to verify the MD5 of the uploaded file
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((SERVER_IP, SERVER_PORT))

        verify_request = {
            FIELD_OPERATION: OP_GET,
            FIELD_DIRECTION: DIR_REQUEST,
            FIELD_TYPE: TYPE_FILE,
            FIELD_TOKEN: token,
            FIELD_KEY: file_key
        }

        s.sendall(make_packet(verify_request))
        json_data, _ = get_tcp_packet(s)

        if json_data and json_data.get(FIELD_MD5):
            return json_data[FIELD_MD5]
    return None


def verify_token(token):
    """
    Verify the validity of the token
    """
    try:
        # Decode the Base64 token
        decoded = base64.b64decode(token).decode()
        parts = decoded.split('.')

        if len(parts) != 4:
            print("Token format error: should have 4 parts")
            return False

        user_str = ".".join(parts[:3])
        md5_auth = parts[3]

        # Generate MD5 with the same key as the server
        expected_md5 = hashlib.md5(f'{user_str}kjh20)*(1'.encode()).hexdigest()

        if expected_md5.lower() == md5_auth.lower():
            print("Token verification successful")
            print(f"Username: {parts[0]}")
            print(f"Timestamp: {parts[1]}")
            return True
        else:
            print("Token verification failed")
            return False

    except Exception as e:
        print(f"Token verification error: {str(e)}")
        return False


def main():
    args = _argparse()

    # Using command line parameters
    global SERVER_IP
    SERVER_IP = args.server_ip
    username = args.id
    file_path = args.f
    password = username

    token = login(username, password)
    if token:
        print(f"Token: {token}")
        # Add token verification
        if verify_token(token):
            save_token(token)
            if os.path.exists(file_path):
                success = upload_file(token, file_path)
                if not success:
                    print("File upload failed")
            else:
                print(f"File does not exist: {file_path}")
        else:
            print("Invalid token received from server")
    else:
        print("Login failed")


if __name__ == "__main__":
    main()