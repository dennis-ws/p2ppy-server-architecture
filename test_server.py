import pytest
import server

def test_basic_addition():
    assert 1 + 1 == 2

def test_server_main():
    # This test will check if the main function runs without errors.
    # Since the server runs indefinitely, we will run it in a separate thread and then stop it.
    import threading
    import time

    server_thread = threading.Thread(target=server.main)
    server_thread.daemon = True  # Allow the thread to be killed when the main program exits
    server_thread.start()

    # Give the server some time to start
    time.sleep(1)

    # Check if the server thread is alive
    assert server_thread.is_alive()

    # Stop the server thread (in a real scenario, you would have a way to gracefully shut down the server)
    # For this test, we will just exit the test, which will kill the daemon thread.