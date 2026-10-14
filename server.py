import socket
import threading

class ChatServer:
    def __init__(self, host=None, port=5000):
        self.host = host
        self.port = port
        self.waiting_clients = []
        self.active_clients = []
        self.pairs = {}
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.threads = []

    def start(self):
        """Starts the TCP server, accepts incoming client connections,
        and pairs clients together. Each connected client is handled
        in a separate thread. If a client disconnects, the server notifies the partner.
        """
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen()
        server_socket.settimeout(1)  # Set a timeout for the accept() call to allow periodic checks for stop_event
        print(f"Server is listening on {self.host}:{self.port}")

        try:
            # Start a thread to handle server commands
            command_thread = threading.Thread(
                target=self.server_command, 
                name="CommandThread", 
                daemon=True)
            command_thread.start()
            while not self.stop_event.is_set():
                try:
                    client_socket, address = server_socket.accept()
                except socket.timeout:
                    continue

                with self.lock:
                    self.waiting_clients.append(client_socket)

                    # Remove closed sockets from the waiting clients list
                    self.waiting_clients = [client for client in self.waiting_clients if client.fileno() != -1]

                    # Create a pair if there are at least two waitingclients
                    if len(self.waiting_clients) >= 2:
                        self.pair_clients()

                # Start a new thread to handle the client
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address),
                    name=f"ClientThread-{address}",
                    daemon=True  # Allow the thread to be killed when the main program exits
                )
                thread.start()
        finally:
            print("Server is closing.")
            self.close_socket(server_socket)

    def server_command(self):
        """Handles server commands from the console."""
        while not self.stop_event.is_set():
            command = input("Enter command (type 'exit' to stop the server): ")
            self.handle_command(command)

    def handle_command(self, command):
        """Handles server commands from the console."""
        match command.strip().lower():
            case "exit":
                print("Stopping the server...")
                self.stop_event.set()
            case "status":
                print("Server Status:")
                print(f"  Waiting Clients: {self.waiting_clients_count()}")
                print(f"  Active Clients: {self.active_clients_count()}")
                print(f"  Pairs: {self.pairs_count()}")
                print(f"  Active Threads: {self.get_thread_count()}")
            case "list waiting":
                print("Waiting Clients:")
                for client in self.waiting_clients_list():
                    print(f"  {client}")
            case "list active":
                print("Active Clients:")
                for client in self.active_clients_list():
                    print(f"  {client}")
            case "list threads":
                print("Active Threads:")
                for thread in self.get_thread():
                    print(f"  {thread.name}")
            case "help":
                print("Available commands:")
                print("  exit - Stop the server")
                print("  status - Show server status")
                print("  list waiting - List waiting clients")
                print("  list active - List active clients")
                print("  list threads - List active threads")
                print("  help - Show this help message")
            case _:
                print(f"Unknown command: {command}")

    def waiting_clients_count(self):
        """Returns the number of clients currently waiting to be paired."""
        with self.lock:
            return len(self.waiting_clients)

    def waiting_clients_list(self):
        """Returns a list of clients currently waiting to be paired."""
        with self.lock:
            return [client.getpeername() for client in self.waiting_clients if client.fileno() != -1]

    def active_clients_count(self):
        """Returns the number of clients currently active (paired)."""
        with self.lock:
            return len(self.active_clients)

    def active_clients_list(self):
        """Returns a list of clients currently active (paired)."""
        with self.lock:
            return [client.getpeername() for client in self.active_clients if client.fileno() != -1]

    def pairs_count(self):
        """Returns the number of active pairs."""
        with self.lock:
            return len(self.pairs) // 2  # Each pair consists of two clients

    def current_host(self):
        """Returns the current host of the server."""
        return self.host

    def current_port(self):
        """Returns the current port of the server."""
        return self.port

    def get_thread_count(self):
        """Returns the number of active threads."""
        return threading.active_count()

    def get_thread(self):
        """Returns a list of active threads."""
        return threading.enumerate()

    def close_socket(self, soc: socket.socket):
        """Close a socket and handle any exceptions."""
        with self.lock:
            try:
                soc.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # Socket is already closed or not connected

            try:
                soc.close()
            except OSError:
                pass  # Socket is already closed

    def pair_clients(self):
        """
            Pairs two clients together for communication. 
            Note: The lock happens in the calling function, so this function assumes that the lock is already acquired.
        """

        client1 = self.waiting_clients.pop(0)
        client2 = self.waiting_clients.pop(0)

        self.pairs[client1] = client2
        self.pairs[client2] = client1

        self.active_clients.append(client1)
        self.active_clients.append(client2)

        print(f"Created a pair! {client1} with {client2}")
        try:
            client1.sendall(b"You have been paired with a partner!")
            client2.sendall(b"You have been paired with a partner!")
        except (BrokenPipeError, ConnectionResetError, OSError):
            print(f"Error occurred while notifying clients of pairing.")
            # Clean up if sending fails
            if client1 in self.active_clients:
                self.active_clients.remove(client1)
            if client2 in self.active_clients:
                self.active_clients.remove(client2)
            if client1 in self.pairs:
                self.pairs.pop(client1, None)
            if client2 in self.pairs:
                self.pairs.pop(client2, None)
            

    def disconnect_client(self, client_socket):
        """Disconnects a client and notifies its partner if connected."""
        partner = None 

        with self.lock:
            partner = self.pairs.pop(client_socket, None)
            # Remove the partner from the pairs dictionary if it exists
            if partner is not None:
                self.pairs.pop(partner, None)
                # Remove the partner from active clients if it's still there
                if self.pairs.get(partner) is client_socket:
                    self.pairs.pop(partner, None)
                # Remove the partner from active clients if it's still there
                if partner in self.active_clients:
                    self.active_clients.remove(partner)
            # Remove the client from active clients if it's still there
            if client_socket in self.active_clients:
                self.active_clients.remove(client_socket)
            # Add the partner back to waiting clients if it's still connected and not already waiting
            if partner is not None and partner.fileno() != -1 and partner not in self.waiting_clients:
                self.waiting_clients.append(partner)
        # Close the client socket
        self.close_socket(client_socket)

        # if the partner is still connected, notify them about the disconnection
        if partner is not None and partner.fileno() != -1:
            try:
                partner.sendall(b"Your partner has disconnected. You are now waiting for a new partner.")
            except (BrokenPipeError, ConnectionResetError, OSError):
                print(f"Error occurred while notifying partner of disconnection.")

    def handle_client(self, client_socket, address):
        """Handles communication with a connected client.

        Receives messages, forwards them to the client's partner,
        and cleans up the client's connection when they disconnect.
        """
        print(f"Connected: {address} with thread {threading.current_thread().name}")

        while True:
            try:
                data = client_socket.recv(1024)

                if not data or data.decode() == "/exit":
                    break

                print(f"Message from {address}: {data.decode()}")

                with self.lock:
                    partner = self.pairs.get(client_socket)

                print(f"Sending to partner for {address}: {partner}")
                if partner:
                    try:
                        partner.sendall(data)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        print(f"Error occurred while sending message to {address}")
                else:
                    print(f"No partner found for {address}. Message not sent.")
                    client_socket.sendall(b"No partner found. Please wait for a partner to connect.")

            except (ConnectionResetError, ConnectionAbortedError, OSError):
                print(f"Connection lost with {address}")
                break

        self.disconnect_client(client_socket)
        print(f"Disconnected: {address} with thread {threading.current_thread().name}")

        # Check if there are waiting clients to pair after a client disconnects
        if len(self.waiting_clients) > 0:
            with self.lock:
                self.pair_clients()

if __name__ == '__main__':
    try:
        server = ChatServer(socket.gethostname(), 5000)
        server.start()
    except KeyboardInterrupt:
        print("Server is shutting down due to KeyboardInterrupt.")
    except Exception as e:
        print(f"An error occurred: {e}")