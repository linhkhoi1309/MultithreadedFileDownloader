import socket
import os
import time
import hashlib
from threading import Thread

# Client configuration
HOST = '192.168.45.128'
PORT = 5000
INPUT_FILE = 'input.txt'
DOWNLOAD_FOLDER = 'downloads'
CHUNK_SIZE = 1024  # Size of each packet
RETRY_LIMIT = 5  # Number of retries for dropped packets
file_metadata = {}

# Ensure download folder exists
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def calculate_checksum(file_path, algo='md5'):
    hasher = hashlib.new(algo)
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def send_packet(sock, addr, packet):
    sock.sendto(packet, addr)

def receive_packet(sock):
    return sock.recvfrom(CHUNK_SIZE + 64)

def download_chunk(file_name, offset, chunk_size, part, progress):
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.settimeout(2)

        part_file = os.path.join(DOWNLOAD_FOLDER, f"{file_name}.part{part}")
        with open(part_file, 'wb') as f:
            received_size = 0
            seq_num = 0
            retries = 0

            while received_size < chunk_size and retries < RETRY_LIMIT:
                packet = f"REQUEST {file_name} {offset + received_size} {CHUNK_SIZE} {seq_num}".encode()
                send_packet(client_socket, (HOST, PORT), packet)

                try:
                    data, _ = receive_packet(client_socket)
                    header, payload = data[:64].decode(), data[64:]
                    ack_seq = int(header.split()[1])

                    if ack_seq == seq_num:
                        f.write(payload)
                        received_size += len(payload)
                        progress[part - 1] = (received_size / chunk_size) * 100
                        seq_num ^= 1  # Toggle sequence number

                        # Send acknowledgment
                        ack = f"ACK {seq_num}".encode()
                        send_packet(client_socket, (HOST, PORT), ack)
                        retries = 0  # Reset retries after successful transfer
                except socket.timeout:
                    print(f"Timeout on chunk {part}, retrying... ({retries + 1}/{RETRY_LIMIT})")
                    retries += 1

            if retries >= RETRY_LIMIT:
                print(f"Failed to download chunk {part} after {RETRY_LIMIT} retries.")

        client_socket.close()
    except Exception as e:
        print(f"Error downloading chunk: {e}")

# Merge file chunks
def merge_file(file_name, total_parts):
    final_file_path = os.path.join(DOWNLOAD_FOLDER, file_name)
    with open(final_file_path, 'wb') as final_file:
        for i in range(1, total_parts + 1):
            part_file = os.path.join(DOWNLOAD_FOLDER, f"{file_name}.part{i}")
            with open(part_file, 'rb') as f:
                final_file.write(f.read())
            os.remove(part_file)
    print(f"Download complete: {file_name}")

    # Calculate and display checksum
    checksum = calculate_checksum(final_file_path, algo='sha256')
    #print(f"Checksum (SHA256) for {file_name}: {checksum}")

# Download a file
def download_file(file_name, file_size):
    num_parts = 4
    chunk_size = file_size // num_parts
    progress = [0] * num_parts
    threads = []

    for part in range(num_parts):
        offset = part * chunk_size
        size = chunk_size if part < num_parts - 1 else file_size - (num_parts - 1) * chunk_size
        thread = Thread(target=download_chunk, args=(file_name, offset, size, part + 1, progress))
        threads.append(thread)
        thread.start()

    try:
        while any(t.is_alive() for t in threads):
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"Downloading {file_name}:")
            for part in range(num_parts):
                print(f"Part {part + 1} .... {progress[part]:.0f}%")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nDownload interrupted.")
        for thread in threads:
            thread.join()
        return

    for thread in threads:
        thread.join()

    merge_file(file_name, num_parts)

def wait_for_user():
    input("\nPress Enter to start downloading the files...")

def display_file_list():
    # Helper to convert size to human-readable format
    def format_size(size):
        if size >= 1024 * 1024 * 1024:  # Size in GB
            return f"{size / (1024 * 1024 * 1024):.1f}GB"
        elif size >= 1024 * 1024:  # Size in MB
            return f"{size / (1024 * 1024):.1f}MB"
        elif size >= 1024:  # Size in KB
            return f"{size / 1024:.1f}KB"
        else:  # Size in bytes
            return f"{size}B"

    # Generate formatted file list
    file_list = []
    max_file_name_length = max(len(file) for file in file_metadata)
    for file, size in file_metadata.items():
        size_str = format_size(size)
        file_list.append(f"{file.ljust(max_file_name_length)} {size_str}")

    # Determine box dimensions
    box_width = max(len(line) for line in file_list) + 4
    horizontal_border = "+" + "-" * (box_width - 2) + "+"

    # Print the file list in the box
    print(horizontal_border)
    for line in file_list:
        print(f"| {line.ljust(box_width - 4)} |")
    print(horizontal_border)

# Main client function
def start_client():
    downloaded_files = set()
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    client_socket.sendto("LIST".encode(), (HOST, PORT))
    file_list, _ = client_socket.recvfrom(4096)
    client_socket.close()

    for line in file_list.decode().split("\n"):
        parts = line.rsplit(" ", 2)
        if len(parts) == 3 and parts[2] == "bytes":
            name, size, _ = parts
            file_metadata[name] = int(size)

    print("FILE LIST AVAILABLE FOR DOWNLOAD:")
    display_file_list()
    wait_for_user()

    try:
        while True:
            with open(INPUT_FILE, 'r') as f:
                files_to_download = {line.strip() for line in f}

            new_files = files_to_download - downloaded_files
            if new_files:
                for file_name in new_files:
                    if file_name in file_metadata:
                        print(f"Starting download: {file_name}")
                        download_file(file_name, file_metadata[file_name])
                        downloaded_files.add(file_name)
                    else:
                        print(f"File not found: {file_name}")

            time.sleep(5)
    except KeyboardInterrupt:
        print("\nQuiting the program...")
    finally:
        print("Goodbye!")

if __name__ == "__main__":
    start_client()
