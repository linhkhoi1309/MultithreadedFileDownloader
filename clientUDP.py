import socket
import os
import time
import struct
from threading import Thread

# Client configuration
HOST = '192.168.56.1'
PORT = 5000
INPUT_FILE = 'input.txt'
DOWNLOAD_FOLDER = 'downloads'
ACK_TIMEOUT = 1  # Timeout for ACK in seconds

# Ensure download folder exists
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Download a file chunk
def download_chunk(file_name, offset, chunk_size, part, total_parts, progress):
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        request = struct.pack('!I I I', offset, chunk_size, part)  # Pack offset, chunk_size, part
        client_socket.sendto(request, (HOST, PORT))

        received_size = 0
        part_file = os.path.join(DOWNLOAD_FOLDER, f"{file_name}.part{part}")
        with open(part_file, 'wb') as f:
            while received_size < chunk_size:
                # Wait for data or ACK
                client_socket.settimeout(ACK_TIMEOUT)
                try:
                    data, _ = client_socket.recvfrom(4096)
                    if data.startswith(b'ACK'):
                        # Received ACK for the chunk
                        ack_part = struct.unpack('!I', data[3:7])[0]
                        if ack_part == part:
                            print(f"Part {part} received successfully.")
                            break
                    else:
                        # Write data to file
                        f.write(data)
                        received_size += len(data)
                        # Send ACK
                        ack_message = struct.pack('!I', part)
                        client_socket.sendto(b'ACK' + ack_message, (HOST, PORT))

                        progress[part - 1] = (received_size / chunk_size) * 100

                except socket.timeout:
                    # Resend request if no ACK received
                    print(f"Timeout waiting for ACK for part {part}. Resending...")
                    client_socket.sendto(request, (HOST, PORT))

        client_socket.close()
    except Exception as e:
        print(f"Error downloading chunk: {e}")

# Merge file chunks
def merge_file(file_name, total_parts):
    with open(os.path.join(DOWNLOAD_FOLDER, file_name), 'wb') as final_file:
        for i in range(1, total_parts + 1):
            part_file = os.path.join(DOWNLOAD_FOLDER, f"{file_name}.part{i}")
            with open(part_file, 'rb') as f:
                final_file.write(f.read())
            os.remove(part_file)
    print(f"Download complete: {file_name}")

# Download a file
def download_file(file_name, file_size):
    chunk_size = file_size // 4
    progress = [0] * 4  # Track progress for each part
    threads = []

    for part in range(4):
        offset = part * chunk_size
        size = chunk_size if part < 3 else file_size - 3 * chunk_size
        thread = Thread(target=download_chunk, args=(file_name, offset, size, part + 1, 4, progress ))
        threads.append(thread)
        thread.start()
        # download_chunk(file_name, offset, size, part + 1, 4, progress)

    while any(t.is_alive() for t in threads):
        # Clear screen and reprint progress
        os.system('cls' if os.name == 'nt' else 'clear')
        #print(f"Downloading {file_name}:")
        for part in range(4):
            print(f"Downloading {file_name} Part {part + 1} .... {progress[part]:.0f}%")
        time.sleep(0.5)

    for thread in threads:
        thread.join()

    merge_file(file_name, 4)

# Main client function
def start_client():
    downloaded_files = set()

    while True:
        with open(INPUT_FILE, 'r') as f:
            files_to_download = {line.strip() for line in f}

        new_files = files_to_download - downloaded_files
        if new_files:
            for file_name in new_files:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_socket.sendto(b"LIST", (HOST, PORT))
                file_list, _ = client_socket.recvfrom(4096)

                file_metadata = {}
                for line in file_list.decode().split("\n"):
                    parts = line.rsplit(" ", 2)  # Split into [name, size, "bytes"]
                    if len(parts) == 3 and parts[2] == "bytes":
                        name, size, _ = parts
                        file_metadata[name] = int(size)  # Convert size to integer

                if file_name in file_metadata:
                    print(f"Starting download: {file_name}")
                    download_file(file_name, file_metadata[file_name])
                    downloaded_files.add(file_name)
                else:
                    print(f"File not found: {file_name}")

        time.sleep(5)

if __name__ == "__main__":
    start_client()