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

def receive_until(client, expected, timeout=3):
    """Read data until expected bytes arrive or the timeout expires."""
    deadline = time.monotonic() + timeout
    received = b""

    while expected not in received and time.monotonic() < deadline:
        try:
            chunk = client.recv(4096)
            if not chunk:
                break
            received += chunk
        except socket.timeout:
            break

    return received


def test_multiple_messages_in_order(running_server):
    """A user can send several messages in sequence."""
    client_a = connect_client()
    client_b = connect_client()

    try:
        messages = [b"First", b"Second", b"Third"]

        for message in messages:
            client_a.sendall(message)
            received = receive_until(client_b, message)
            assert message in received

    finally:
        client_a.close()
        client_b.close()


def test_unicode_and_emoji_message(running_server):
    """Unicode text and emoji are forwarded without corruption."""
    client_a = connect_client()
    client_b = connect_client()

    try:
        message = "Hello 世界 🌏 café".encode("utf-8")
        client_a.sendall(message)

        received = receive_until(client_b, message)
        assert message in received
        assert received.decode("utf-8").find("🌏") != -1

    finally:
        client_a.close()
        client_b.close()


def test_empty_send_does_not_crash_connection(running_server):
    """An empty send is a no-op in TCP; later messages still work."""
    client_a = connect_client()
    client_b = connect_client()

    try:
        client_a.sendall(b"")

        message = b"Still connected"
        client_a.sendall(message)

        received = receive_until(client_b, message)
        assert message in received

    finally:
        client_a.close()
        client_b.close()


def test_three_clients_pair_correctly(running_server):
    """The first two clients pair; the third waits for another client."""
    client_a = connect_client()
    client_b = connect_client()
    client_c = connect_client()

    try:
        message = b"A to B"
        client_a.sendall(message)

        received = receive_until(client_b, message)
        assert message in received

        # The third client must not receive A's message.
        client_c.settimeout(0.3)
        try:
            unexpected = client_c.recv(1024)
            assert unexpected == b""
        except socket.timeout:
            pass

        # A fourth client should pair with the waiting third client.
        client_d = connect_client()

        try:
            message_cd = b"C to D"
            client_c.sendall(message_cd)

            received_cd = receive_until(client_d, message_cd)
            assert message_cd in received_cd

        finally:
            client_d.close()

    finally:
        client_a.close()
        client_b.close()
        client_c.close()


def test_two_pairs_are_isolated(running_server):
    """Messages from one pair must not reach another pair."""
    client_a = connect_client()
    client_b = connect_client()
    client_c = connect_client()
    client_d = connect_client()

    try:
        message_ab = b"Only for B"
        message_cd = b"Only for D"

        client_a.sendall(message_ab)
        client_c.sendall(message_cd)

        received_b = receive_until(client_b, message_ab)
        received_d = receive_until(client_d, message_cd)

        assert message_ab in received_b
        assert message_cd in received_d
        assert message_cd not in received_b
        assert message_ab not in received_d

    finally:
        client_a.close()
        client_b.close()
        client_c.close()
        client_d.close()


def test_partner_notified_when_client_disconnects(running_server):
    """An abruptly disconnected client notifies its partner."""
    client_a = connect_client()
    client_b = connect_client()

    try:
        # Ensure both clients have been paired before disconnecting A.
        message = b"Ready to disconnect"
        client_a.sendall(message)
        assert message in receive_until(client_b, message)

        client_a.close()
        client_a = None

        notification = receive_until(
            client_b, b"Your partner has disconnected."
        )
        assert b"Your partner has disconnected." in notification

    finally:
        if client_a is not None:
            client_a.close()
        client_b.close()


def test_server_accepts_new_connections_after_disconnect(running_server):
    """A client disconnecting does not take down the server."""
    client_a = connect_client()
    client_b = connect_client()

    try:
        message = b"Confirm pairing"
        client_a.sendall(message)
        assert message in receive_until(client_b, message)

        client_a.close()
        client_a = None

        notification = receive_until(
            client_b, b"Your partner has disconnected."
        )
        assert b"Your partner has disconnected." in notification

        # Connect a new pair after the previous pair has disconnected.
        client_c = connect_client()
        client_d = connect_client()

        try:
            new_message = b"New pair works"
            client_c.sendall(new_message)

            received = receive_until(client_d, new_message)
            assert new_message in received

        finally:
            client_c.close()
            client_d.close()

    finally:
        if client_a is not None:
            client_a.close()
        client_b.close()


def test_exit_command_disconnects_client(running_server):
    """Sending /exit closes the client connection and notifies its partner."""
    client_a = connect_client()
    client_b = connect_client()

    try:
        message = b"Pair established"
        client_a.sendall(message)
        assert message in receive_until(client_b, message)

        client_a.sendall(b"/exit")

        notification = receive_until(
            client_b, b"Your partner has disconnected."
        )
        assert b"Your partner has disconnected." in notification

    finally:
        client_a.close()
        client_b.close()


def test_server_stays_alive_after_client_disconnect(running_server):
    """A disconnected client does not crash the server."""
    client_a = connect_client()
    client_b = connect_client()

    try:
        message = b"Test before disconnect"
        client_a.sendall(message)
        assert message in receive_until(client_b, message)

        client_a.close()
        client_a = None

        notification = receive_until(
            client_b, b"Your partner has disconnected."
        )
        assert b"Your partner has disconnected." in notification

        # The server should still accept a new TCP connection.
        client_c = connect_client()
        client_c.close()

    finally:
        if client_a is not None:
            client_a.close()
        client_b.close()
