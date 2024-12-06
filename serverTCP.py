import socket
import threading
import os

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
def handle_client(client_socket, metadata):
    try:
        while True:
            request = client_socket.recv(1024).decode()
            if not request:
                break
            
            command, *args = request.split()
            if command == "LIST":
                response = "\n".join(f"{name} {size} bytes" for name, size in metadata.items())
                client_socket.sendall(response.encode())
            elif command == "DOWNLOAD":
                file_name, offset, chunk_size = args
                offset, chunk_size = int(offset), int(chunk_size)
                
                if file_name not in metadata:
                    client_socket.sendall(b"ERROR: File not found")
                    continue

                file_path = os.path.join("server_files", file_name)
                with open(file_path, 'rb') as f:
                    f.seek(offset)
                    data = f.read(chunk_size)
                client_socket.sendall(data)
            else:
                client_socket.sendall(b"ERROR: Invalid command")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client_socket.close()

# Main server function
def start_server():
    metadata = load_file_metadata()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Server listening on {HOST}:{PORT}")
    
    while True:
        client_socket, addr = server_socket.accept()
        print(f"Connection from {addr}")
        client_handler = threading.Thread(target=handle_client, args=(client_socket, metadata))
        client_handler.start()

if __name__ == "__main__":
    start_server()
