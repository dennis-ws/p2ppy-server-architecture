import pytest
import server
import socket
import threading
import time

HOST = socket.gethostname()
PORT = 5000

def test_basic_addition():
    assert 1 + 1 == 2
def test_server_main():
    """Test that the server starts and shuts down cleanly."""
    stop_event = threading.Event()

    server_thread = threading.Thread(
        target=server.main,
        args=(stop_event,),
        daemon=True,
    )

    server_thread.start()

    try:
        # Wait until the server is listening for connections.
        deadline = time.monotonic() + 5

        while True:
            try:
                with socket.create_connection(
                    (HOST, PORT), timeout=0.2
                ):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    pytest.fail("Server did not start")
                time.sleep(0.05)

        # If we connected successfully, the server is running.
        assert server_thread.is_alive()

    finally:
        # Request a graceful shutdown.
        stop_event.set()

        # Wait for the server thread to finish.
        server_thread.join(timeout=3)

    assert not server_thread.is_alive(), "Server did not stop"

@pytest.fixture
def running_server():
    """Start the server before a test and stop it afterward."""
    stop_event = threading.Event()

    server_thread = threading.Thread(
        target=server.main,
        args=(stop_event,),
        daemon=True,
    )
    server_thread.start()

    # Wait until the server is accepting connections.
    deadline = time.monotonic() + 5

    while True:
        try:
            print("Attempting to connect to the server with a probe...")
            probe = socket.create_connection((HOST, PORT), timeout=0.2)
            print("Successfully connected to the server with a probe.")
            probe.close()
            print("Closed the probe connection.")
            break
        except OSError:
            if time.monotonic() >= deadline:
                stop_event.set()
                server_thread.join(timeout=2)
                pytest.fail("Server failed to start")
            time.sleep(0.05)

    yield

    # Stop the server after the test finishes.
    stop_event.set()
    server_thread.join(timeout=3)


def connect_client():
    """Connect a test client to the server."""
    print("Connecting a test client to the server...")
    client = socket.create_connection((HOST, PORT), timeout=3)
    print(f"Test client connected to the server at {HOST}:{PORT}")
    client.settimeout(3)
    return client


def test_client_can_connect(running_server):
    """Test 1: A client can connect to the server."""
    client = connect_client()

    try:
        assert client.fileno() != -1
    finally:
        client.close()


def test_client_can_send_message(running_server):
    """Test 2: A client can send data without a socket error."""
    client_a = connect_client()
    client_b = connect_client()

    try:
        # Sending requires a live TCP connection.
        message = b"Hello server!"
        client_a.sendall(message)

        # Verify the server processed the message by checking
        # that the paired client receives it.
        received = client_b.recv(1024)
        assert received == message
    finally:
        client_a.close()
        client_b.close()


def test_server_receives_message(running_server, capsys):
    """Test 3: The server receives and logs a client's message."""
    print("Starting test_server_receives_message")
    client_a = connect_client()
    print("Client A connected")
    client_b = connect_client()
    print("Client B connected")

    try:
        message = b"Test server receipt"
        client_a.sendall(message)

        # Wait for the server's handler to print the message.
        deadline = time.monotonic() + 3
        output = ""

        while time.monotonic() < deadline:
            output = capsys.readouterr().out
            print(f"Captured output: {output}")
            if message.decode() in output:
                break
            time.sleep(0.05)

        assert message.decode() in output
    finally:
        client_a.close()
        client_b.close()


def test_client_can_receive_message(running_server):
    """Test 4: A client receives a message from its partner."""
    client_a = connect_client()
    client_b = connect_client()

    try:
        message = b"Hello from Client A!"
        client_a.sendall(message)

        received = client_b.recv(1024)

        assert received == message
    finally:
        client_a.close()
        client_b.close()