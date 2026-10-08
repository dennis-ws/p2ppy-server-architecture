import socket
import threading

def main():
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
    server.bind((socket.gethostname(), 5000))
    server.listen()
    print("Server is listening...")
        
    while True:
        # Wait for a connection
        clientsocket, address = server.accept()

        with threading_lock:
            clients.append(clientsocket)

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
            name=f"ClientThread-{address}"
        )

        thread.start()

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

            # If no data is received or the client sends "exit", break the loop
            if not data or data.decode() == "exit":
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
    
    clientsocket.close()
    print("Disconnected: ", address)

if __name__ == '__main__':
    main()