import socket
import os
import threading
import hashlib

# Server configuration
HOST = '192.168.56.1'
PORT = 5000
FILE_LIST = 'file_list.txt'
CHUNK_SIZE = 1024

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
            elif "kb" in size_with_unit:
                size_in_bytes = int(size_with_unit.replace("kb", "")) * 1024
            elif "b" in size_with_unit:
                size_in_bytes = int(size_with_unit.replace("b", ""))
            else:
                raise ValueError(f"Unsupported size format: {size_with_unit}")

            metadata[name] = size_in_bytes
    return metadata

# Handle client request
def handle_client(data, addr, server_socket, metadata):
    try:
        request = data.decode()
        #print(f"Received request from {addr}: {request}")

        # Split the request into parts and validate
        parts = request.split()
        if not parts:
            raise ValueError("Empty or invalid request format")

        command = parts[0]
        args = parts[1:]

        if command == "LIST":
            # Handle file list request
            response = "\n".join(f"{name} {size} bytes" for name, size in metadata.items())
            server_socket.sendto(response.encode(), addr)

        elif command == "REQUEST":
            # Validate the REQUEST format
            if len(args) != 4:
                raise ValueError("Invalid REQUEST format")

            file_name, offset, chunk_size, seq_num = args
            offset, chunk_size, seq_num = int(offset), int(chunk_size), int(seq_num)

            if file_name not in metadata:
                error_msg = "ERROR: File not found"
                server_socket.sendto(error_msg.encode(), addr)
                return

            file_path = os.path.join("server_files", file_name)
            with open(file_path, 'rb') as f:
                f.seek(offset)
                data = f.read(chunk_size)

            # Prepare and send the data packet
            header = f"DATA {seq_num}".ljust(64).encode()
            packet = header + data
            server_socket.sendto(packet, addr)

        elif command == "ACK":
            # Handle ACK message
            if len(args) != 1:
                raise ValueError("Invalid ACK format")
            seq_num = int(args[0])
            #print(f"ACK received for sequence number: {seq_num}")

        else:
            # Handle unknown commands
            error_msg = "ERROR: Invalid command"
            server_socket.sendto(error_msg.encode(), addr)

    except ValueError as ve:
        print(f"Error handling client (ValueError): {ve}")
    except Exception as e:
        print(f"Error handling client: {e}")

        
# Main server function
def start_server():
    metadata = load_file_metadata()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((HOST, PORT))
    print(f"Server listening on {HOST}:{PORT}")

    # Flag to ensure the server serves only one client
    client_serving = False

    while True:
        try:
            # If the server is already serving a client, ignore new connections
            if client_serving:
                data, addr = server_socket.recvfrom(CHUNK_SIZE + 64)
                print(f"Server is already serving a client. Ignoring new request from {addr}")
                continue  # Skip to the next iteration (do not process this request)

            # Accept a new client (only one client will be served)
            data, addr = server_socket.recvfrom(CHUNK_SIZE + 64)
            client_serving = True  # Set the flag to True, indicating the server is serving a client
            #print(f"New client connected: {addr}")

            # Handle the client in a separate thread
            threading.Thread(target=handle_client, args=(data, addr, server_socket, metadata)).start()

            # Reset the client_serving flag when the client has finished
            client_serving = False

        except KeyboardInterrupt:
            print("Shutting down server...")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    start_server()

