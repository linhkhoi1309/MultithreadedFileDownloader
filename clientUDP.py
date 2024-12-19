import socket
import os
import time
import struct
from threading import Thread

HOST = '192.168.56.1'
PORT = 5000
INPUT_FILE = 'input.txt'
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

PACKET_SIZE = 1024
TIMEOUT = 2.0

def gbn_download_chunk(file_name, offset, chunk_size, part, total_parts, progress):
    # GBN download for a specified portion of the file
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    command = f"DOWNLOAD {file_name} {offset} {chunk_size}"
    client_socket.sendto(command.encode(), (HOST, PORT))

    header, _ = client_socket.recvfrom(1024)
    if header.startswith(b"ERROR"):
        print(header.decode())
        client_socket.close()
        return

    part_size, total_packets = struct.unpack('!Q I', header)
    received_data = bytearray(part_size)

    expected_seq = 0
    last_ack_sent = -1

    # Prepare to save the downloaded part
    part_file = os.path.join(DOWNLOAD_FOLDER, f"{file_name}.part{part}")

    try:
        while expected_seq < total_packets:
            try:
                # Receive packet from server
                packet, _ = client_socket.recvfrom(PACKET_SIZE + 4)
                seq_num = struct.unpack('!I', packet[:4])[0]
                data = packet[4:]
                if seq_num == expected_seq:
                    # Correct packet received, save it in the buffer
                    start_index = seq_num * PACKET_SIZE
                    end_index = start_index + len(data)
                    received_data[start_index:end_index] = data
                    expected_seq += 1
                    last_ack_sent = seq_num

                    # Update progress
                    progress[part - 1] = (expected_seq / total_packets) * 100

                # Send cumulative ACK
                ack_packet = b'ACK' + struct.pack('!I', last_ack_sent)
                client_socket.sendto(ack_packet, (HOST, PORT))
            except socket.timeout:
                # Timeout occurred, resend last cumulative ACK
                if last_ack_sent >= 0:
                    ack_packet = b'ACK' + struct.pack('!I', last_ack_sent)
                    client_socket.sendto(ack_packet, (HOST, PORT))
            
        # Save the downloaded chunk to file
        with open(part_file, 'wb') as f:
            f.write(received_data)

        print(f"Part {part} downloaded successfully.")
    except Exception as e:
        print(f"Error during download of part {part}: {e}")
    finally:
        client_socket.close()

def merge_file(file_name, total_parts):
    final_path = os.path.join(DOWNLOAD_FOLDER, file_name)
    with open(final_path, 'wb') as final_file:
        for i in range(1, total_parts + 1):
            part_file = os.path.join(DOWNLOAD_FOLDER, f"{file_name}.part{i}")
            with open(part_file, 'rb') as pf:
                final_file.write(pf.read())
            os.remove(part_file)
    print(f"Download complete: {file_name}")

def download_file(file_name, file_size):
    total_parts = 5
    chunk_size = file_size // total_parts
    # Handle remainder for the last chunk
    sizes = [chunk_size]*4 + [file_size - 4*chunk_size]

    progress = [0]*total_parts
    threads = []
    for i in range(total_parts):
        offset = i * chunk_size if i < 4 else 4*chunk_size
        t = Thread(target=gbn_download_chunk, args=(file_name, offset, sizes[i], i+1, total_parts, progress))
        threads.append(t)
        t.start()

    # Display progress until all threads done
    while any(t.is_alive() for t in threads):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"Downloading {file_name}:")
        for i in range(total_parts):
            print(f"Part {i+1}: {progress[i]:.0f}%")
        time.sleep(0.5)

    for t in threads:
        t.join()

    merge_file(file_name, total_parts)

def start_client():
    downloaded_files = set()
    try:
        while True:
            with open(INPUT_FILE, 'r') as f:
                files_to_download = {line.strip() for line in f if line.strip()}

            new_files = files_to_download - downloaded_files
            if new_files:
                # Get file list from server
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_socket.sendto(b"LIST", (HOST, PORT))
                file_list, _ = client_socket.recvfrom(4096)
                file_metadata = {}
                for line in file_list.decode().split("\n"):
                    parts = line.rsplit(" ", 2)
                    if len(parts) == 3 and parts[2] == "bytes":
                        name, size, _ = parts
                        file_metadata[name] = int(size)

                for file_name in new_files:
                    if file_name in file_metadata:
                        print(f"Starting download: {file_name}")
                        download_file(file_name, file_metadata[file_name])
                        downloaded_files.add(file_name)
                        time.sleep(2)
                    else:
                        print(f"File not found: {file_name}")
                client_socket.close()

            time.sleep(5)
    except KeyboardInterrupt:
        print("\nQuiting the program...")
    finally:
        print("Goodbye!")
if __name__ == "__main__":
    start_client()