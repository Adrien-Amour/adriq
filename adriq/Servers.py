import socket
import threading
import pickle
import time
import atexit

class Server:
    def __init__(self, service_class, max_que):
        self.service_instance = service_class()  # Create an instance of the service class
        self.service_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.service_socket.bind((self.service_instance.host, self.service_instance.port))
        self.service_socket.listen(max_que)
        self.running = True
        print(f"Server listening on port {self.service_instance.port}...")
        
        # Register the close method to be called at exit
        atexit.register(self.shutdown)

    def listen(self):
        while self.running:
            try:
                client_socket, addr = self.service_socket.accept()
                # print(f"Accepted connection from {addr}")
                threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
            except OSError:
                break

    def handle_client(self, client_socket):
        try:
            while True:
                # Receive command as bytes (no decoding)
                command_data = client_socket.recv(4096)  # Adjust buffer size as needed
                if not command_data:
                    break
                
                # Deserialize the command using pickle
                command = pickle.loads(command_data)
                if command == "SHUTDOWN":
                    self.shutdown()
                    break
                else:
                    # Call the recv_command method on the instance of PMT_Reader
                    response = self.service_instance.recv_command(command)
                
                # Serialize the response using pickle before sending back
                client_socket.sendall(pickle.dumps(response))
        except (ConnectionResetError, ConnectionAbortedError) as e:
            print(f"Connection error: {e}")
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()

    def shutdown(self):
        if self.running:
            self.running = False
            self.service_socket.close()
            print("Server has been shut down.")
            self.service_instance.close()
            del self.service_instance

    @classmethod
    def status_check(cls, service_class, max_que):
        try:
            # Attempt to connect to the server to check if it's running
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((service_class.host, service_class.port))
            client.close()
            print("Server is already running.")
            return 1
        except ConnectionRefusedError:
            print("Server is not running. Starting server...")
            service_instance = cls(service_class, max_que)  # Start a new server instance
            threading.Thread(target=service_instance.listen, daemon=True).start()
            return 0
        
    @classmethod
    def master(cls, service_class, max_que):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((service_class.host, service_class.port))
            client.sendall(pickle.dumps("SHUTDOWN"))
            client.close()
            time.sleep(1)
        except ConnectionRefusedError:
            print("Server is not running.")
        
        print("Starting new server...")
        server_instance = cls(service_class, max_que)
        threading.Thread(target=server_instance.listen, daemon=True).start()
        return server_instance.service_instance  # Return the service instance

class Client:
    def __init__(self, service_class):
        self.service_class = service_class
        self.host = service_class.host
        self.port = service_class.port

    def send_command(self, command):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.host, self.port))
            
            # Serialize the command using pickle
            client_socket.sendall(pickle.dumps(command))
            
            # Receive the response from the server
            response_data = client_socket.recv(4096)  # Adjust buffer size as needed
            response = pickle.loads(response_data)
            
            client_socket.close()
            return response
        except ConnectionRefusedError:
            print("Server is not running. Attempting to restart...")
            Server.status_check(self.service_class, 5)
            time.sleep(1)  # Wait a moment to ensure the server starts
            return self.send_command(command)  # Retry sending the command
        except Exception as e:
            print(f"Error sending command: {e}")