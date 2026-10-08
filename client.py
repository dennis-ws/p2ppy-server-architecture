import socket
import threading

stop_event = threading.Event()

# keep receiving data, break if it not data
def receive():
    while not stop_event.is_set():
        try: 
            data = client.recv(1024)

            if not data:
                stop_event.set()
                break

            # we received something, decode it
            print(f"\nReceived: {data.decode()}\nSend a message: ")
        except (ConnectionResetError, ConnectionAbortedError, OSError):
            print("Connection lost with the server.")
            stop_event.set()
            break


client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((socket.gethostname(), 5000))
print("Connected!")

threading.Thread(
    target=receive,
    name=f"ReceiveThread{client.getsockname()}"
).start()

while not stop_event.is_set():
    try: 
        tosend = input("Send a message: ")

        if tosend == "exit":
            stop_event.set()
            break

        client.sendall(tosend.encode())
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
        print("Connection lost with the server.")
        stop_event.set()
        break
print("Disconnected!")
client.close()