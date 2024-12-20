import socket
import os
import struct
import time
import threading

HOST = '192.168.56.1'
PORT = 5000
FILE_LIST = 'file_list.txt'

PACKET_SIZE = 1024
TIMEOUT = 2.0
WINDOW_SIZE = 4

def load_file_metadata():
    metadata = {}
    with open(FILE_LIST, 'r') as f:
        for line in f:
            name, size_with_unit = line.strip().split()
            size_with_unit = size_with_unit.lower()

            if "mb" in size_with_unit:
                size_in_bytes = int(size_with_unit.replace("mb", "")) * (1024 ** 2)
            elif "gb" in size_with_unit:
                size_in_bytes = int(size_with_unit.replace("gb", "")) * (1024 ** 3)
            else:
                raise ValueError(f"Unsupported size format: {size_with_unit}")
            metadata[name] = size_in_bytes
    return metadata

def send_file_gbn(server_socket, client_address, file_path, offset, chunk_size):
    # Similar GBN logic as before
    server_socket.setblocking(True)
    total_packets = (chunk_size + PACKET_SIZE - 1) // PACKET_SIZE
    header = struct.pack('!Q I', chunk_size, total_packets)
    server_socket.sendto(header, client_address)

    with open(file_path, 'rb') as f:
        f.seek(offset)
        packets = []
        for seq_num in range(total_packets):
            data = f.read(PACKET_SIZE)
            packet = struct.pack('!I', seq_num) + data
            packets.append(packet)

    base = 0
    next_seq_num = 0
    start_time = None

    # Set timeout for the GBN process only
    server_socket.settimeout(TIMEOUT)

    try:
        while base < total_packets:
            # Send packets within the window
            while next_seq_num < total_packets and next_seq_num < base + WINDOW_SIZE:
                server_socket.sendto(packets[next_seq_num], client_address)
                next_seq_num += 1

            try:
                # Wait for ACKs
                ack_data, _ = server_socket.recvfrom(1024)
                if ack_data.startswith(b'ACK'):
                    ack_seq = struct.unpack('!I', ack_data[3:7])[0]
                    if ack_seq >= base:
                        base = ack_seq + 1  # Slide window
            except socket.timeout:
                # Timeout occurred, retransmit from base
                for seq_num in range(base, min(base + WINDOW_SIZE, total_packets)):
                    server_socket.sendto(packets[seq_num], client_address)
            except BlockingIOError:
                    time.sleep(0.01)
    finally:
        server_socket.settimeout(None)

    print(f"Finished sending offset {offset}, size {chunk_size} to {client_address}")

def handle_client_request(server_socket, metadata, request, client_address):
    command_parts = request.decode('utf-8', errors='ignore').strip().split()
    if len(command_parts) == 0:
        return

    cmd = command_parts[0]
    if cmd == "LIST":
        response = "\n".join(f"{name} {size} bytes" for name, size in metadata.items())
        server_socket.sendto(response.encode(), client_address)
    elif cmd == "DOWNLOAD" and len(command_parts) == 4:
        file_name = command_parts[1]
        try:
            offset = int(command_parts[2])
            chunk_size = int(command_parts[3])
        except ValueError:
            server_socket.sendto(b"ERROR: Invalid offset/size", client_address)
            return

        if file_name not in metadata:
            server_socket.sendto(b"ERROR: File not found", client_address)
            return

        file_path = os.path.join("server_files", file_name)
        if not os.path.exists(file_path):
            server_socket.sendto(b"ERROR: File not found on server", client_address)
            return

        send_file_gbn(server_socket, client_address, file_path, offset, chunk_size)
    else:
        server_socket.sendto(b"ERROR: Invalid command", client_address)

def handle_client(server_socket, metadata):
    # Ensure the main listening socket does NOT have a timeout
    server_socket.settimeout(None)
    while True:
        try:
            request, client_address = server_socket.recvfrom(4096)
        except socket.timeout:
            # If we ever set a timeout above, handle it gracefully
            continue
        except OSError:
            # Socket closed or error
            break

        # Handle request in a new thread for concurrency
        t = threading.Thread(target=handle_client_request, args=(server_socket, metadata, request, client_address))
        t.start()

def start_server():
    metadata = load_file_metadata()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((HOST, PORT))
    print(f"Server listening on {HOST}:{PORT}")

    handle_client(server_socket, metadata)

if __name__ == "__main__":
    start_server()