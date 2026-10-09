import socket
import threading

def close_socket(socket):
    """Close a socket and handle any exceptions."""
    try:
        socket.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass  # Socket is already closed or not connected

    try:
        socket.close()
    except OSError:
        pass  # Socket is already closed

def main(stop_event):
    """
    Starts the TCP server, accepts incoming client connections,
    and pairs clients together. Each connected client is handled
    in a separate thread. If a client disconnects, the server notifies the partner.
    """
    clients = []
    pairs = {}
    # Protects shared mutable data structures (clients and pairs) from concurrent access
    threading_lock = threading.Lock() 

    # TCP server setup, and bind it to port 5000 on local machine
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reuse of the address
    server.bind((socket.gethostname(), 5000))
    server.listen()
    server.settimeout(1)  # Set a timeout for the accept() call to allow periodic checks for stop_event
    print("Server is listening...")

    try:
        while not stop_event.is_set():
            # Wait for a connection
            try:
                clientsocket, address = server.accept()
            except socket.timeout:
                continue

            with threading_lock:
                clients.append(clientsocket)

                for client in clients:
                    if client.fileno() == -1:  # Check if the socket is closed
                        clients.remove(client)

                # create a pair
                if len(clients) >= 2:
                    client1 = clients.pop(0)
                    client2 = clients.pop(0)

                    pairs[client1] = client2
                    pairs[client2] = client1

                    print(f"Created a pair! {client1} with {client2} ")

            # Start a new thread to handle the client
            thread = threading.Thread(
                target=handle_client,
                args=(clientsocket, address, clients, pairs, threading_lock),
                name=f"ClientThread-{address},",
                daemon=True  # Allow the thread to be killed when the main program exits
            )

            thread.start()
    finally:
        # Clean up server socket
        print("Server is closing.")
        close_socket(server)

def handle_client(clientsocket, address, clients, pairs, threading_lock):
    """
    Handles communication with a connected client.

    Receives messages, forwards them to the client's partner,
    and cleans up the client's connection when they disconnect.
    """
    print("Connected: ", address)

    while True:
        try:
            # Receive data from the client
            data = clientsocket.recv(1024)

            # If no data is received or the client sends "/exit", break the loop
            if not data or data.decode() == "/exit":
                break

            print(f"Message from {address}: {data.decode()}")

            with threading_lock:
                partner = pairs.get(clientsocket)

            print(f"Sending to partner for {address}: {partner}")
            if partner:
                try: 
                    # Send the received data to the partner client
                    partner.sendall(data)
                except (BrokenPipeError, ConnectionResetError):
                    print(f"Error occurred while sending message to {address}")

        except (ConnectionResetError, ConnectionAbortedError, OSError):
            print(f"Connection lost with {address}")
            break
        
    # Remove the pair when a client disconnects
    with threading_lock:
        partner = pairs.pop(clientsocket, None)
        if partner:
            pairs.pop(partner, None)
    if partner:
        try:
            partner.sendall(b"Your partner has disconnected.")
        except (BrokenPipeError, ConnectionResetError):
            print(f"Error occurred while notifying partner of {address} disconnection.")
    
    close_socket(clientsocket)
    print("Disconnected: ", address)

if __name__ == '__main__':
    try:
        main(threading.Event())  # Pass a dummy Event for standalone execution
    except KeyboardInterrupt:
        print("Server is shutting down due to KeyboardInterrupt.")
    except Exception as e:
        print(f"An error occurred: {e}")