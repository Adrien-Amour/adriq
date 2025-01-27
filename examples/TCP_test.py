import socket
import threading
import keyboard  # You may need to install the 'keyboard' library

class TCPClient:
    def __init__(self, host, port):
        """
        Initialize the TCP client and connect to the server.
        """
        self.host = host
        self.port = port
        self.client_socket = None
        self.running = True

        try:
            # Create and connect the socket
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            print(f"Connected to server at {self.host}:{self.port}")
        except Exception as e:
            print(f"Failed to connect to the server: {e}")
            self.running = False

    def read_messages(self):
        """
        Read messages from the server until 'end' is received or stopped manually.
        """
        print("Reading messages from the server. Press 's' to stop.")
        try:
            while self.running:
                data = self.client_socket.recv(1024)  # Buffer size of 1024 bytes
                if not data:
                    print("No data received. Connection may have been closed.")
                    break

                # Decode the message
                message = data.decode('utf-8')
                print(f"Received: {message}")

                # Stop reading if the message ends with 'end'
                if message.lower().endswith('end'):
                    print("Received 'end'. Stopping read.")
                    break

                if keyboard.is_pressed('s'):  # Stop reading manually
                    print("Stopped reading manually.")
                    break
        except Exception as e:
            print(f"Error during reading: {e}")

    def write_messages(self):
        """
        Write messages to the server based on user input.
        """
        print("Writing messages to the server. Type 'exit' to stop.")
        try:
            while self.running:
                user_input = input("Enter a message to send to the server: ")
                if user_input.lower() == 'exit':
                    print("Exiting write mode.")
                    break
                self.client_socket.sendall(user_input.encode('utf-8'))
                print(f"Sent: {user_input}")
        except Exception as e:
            print(f"Error during writing: {e}")

    def close_connection(self):
        """
        Close the connection to the server and stop the client.
        """
        print("Closing connection to the server.")
        self.running = False
        if self.client_socket:
            self.client_socket.close()
        print("Connection closed.")

    def handle_keypress(self):
        """
        Monitor keyboard input to trigger actions: read, write, or exit.
        """
        print("Press 'r' to read, 'w' to write, 'e' to exit.")
        try:
            while self.running:
                if keyboard.is_pressed('r'):  # Read messages
                    print("Switching to read mode.")
                    self.read_messages()

                elif keyboard.is_pressed('w'):  # Write messages
                    print("Switching to write mode.")
                    self.write_messages()

                elif keyboard.is_pressed('e'):  # Exit
                    print("Exiting.")
                    self.close_connection()
                    break
        except Exception as e:
            print(f"Error handling keypress: {e}")

    def start(self):
        """
        Start the client and handle keypress-based actions.
        """
        if self.running:
            print("Client started. Use the keyboard to control actions.")
            self.handle_keypress()


# Example usage
if __name__ == "__main__":
    # Replace with the actual server's IP and port
    host = "127.0.0.1s"
    port = 5000

    # Initialize the client
    client = TCPClient(host, port)

    # Start the client
    client.start()
