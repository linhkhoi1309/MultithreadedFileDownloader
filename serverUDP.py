import socket
import os
import struct 
# Server configuration
HOST = '192.168.56.1'
PORT = 5000
FILE_LIST = 'file_list.txt'  # Text file containing file information

# Load file metadata
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

# Handle client request
def handle_client(server_socket, metadata):
    try:
        while True:
            request, client_address = server_socket.recvfrom(4096)
            if not request:
                break
            
            try:
                command = request.decode('utf-8')
            except UnicodeDecodeError as e:
                #print(f"Decoding error: {e}. Raw data: {request}")
                server_socket.sendto(b"ERROR: Invalid request format", client_address)
                continue

            if command == "LIST":
                response = "\n".join(f"{name} {size} bytes" for name, size in metadata.items())
                server_socket.sendto(response.encode(), client_address)
            elif command.startswith("DOWNLOAD"):
                _, file_name, offset, chunk_size = command.split()
                offset, chunk_size = int(offset), int(chunk_size)
                
                if file_name not in metadata:
                    server_socket.sendto(b"ERROR: File not found", client_address)
                    continue

                file_path = os.path.join("server_files", file_name)
                with open(file_path, 'rb') as f:
                    f.seek(offset)
                    data = f.read(chunk_size)
                    # Send data with a sequence number
                    seq_number = struct.pack('!I', int(offset / chunk_size))
                    server_socket.sendto(seq_number + data, client_address)

                # Wait for ACK
                ack, _ = server_socket.recvfrom(1024)
                if ack.startswith(b'ACK'):
                    ack_part = struct.unpack('!I', ack[3:7])[0]
                    print(f"ACK received for part {ack_part}.")
            else:
                server_socket.sendto(b"ERROR: Invalid command", client_address)
    except Exception as e:
        print(f"Error: {e}")

# Main server function
def start_server():
    metadata = load_file_metadata()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((HOST, PORT))
    print(f"Server listening on {HOST}:{PORT}")
    
    while True:
        handle_client(server_socket, metadata)
    

if __name__ == "__main__":
    start_server()