import socket
import threading

def main():
    clients = []
    pairs = {}

    threading_lock = threading.Lock()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((socket.gethostname(), 5000))
    server.listen()
    print("Server is listening...")
        
    while True:
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

        thread = threading.Thread(
            target=handle_client,
            args=(clientsocket, address, clients, pairs, threading_lock),
            name=f"ClientThread-{address}"
        )

        thread.start()


def handle_client(clientsocket, address, clients, pairs, threading_lock):
    print("Connected: ", address)

    while True:
        try:
            data = clientsocket.recv(1024)
        
            if not data or data.decode() == "exit":
                break

            print(f"Message from {address}: {data.decode()}")

            with threading_lock:
                partner = pairs.get(clientsocket)

            print(f"Sending to partner for {address}: {partner}")
            if partner:
                try: 
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