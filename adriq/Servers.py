import socket
import threading
import pickle
import atexit
import time

import struct

def send_msg(sock, data):
    data = pickle.dumps(data)
    length = struct.pack('!I', len(data))
    sock.sendall(length + data)

def recv_msg(sock):
    raw_len = recvall(sock, 4)
    if not raw_len:
        return None
    msg_len = struct.unpack('!I', raw_len)[0]
    return pickle.loads(recvall(sock, msg_len))

def recvall(sock, n):
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

class Server:
    def __init__(self, service_class, max_que=5, *service_args, **service_kwargs):
        # Create an instance of the service class with the provided arguments
        self.service_instance = service_class(*service_args, **service_kwargs)
        self.service_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.service_socket.bind((self.service_instance.host, self.service_instance.port))
        self.service_socket.listen(max_que)
        self.running = True
        print(f"Server listening on port {self.service_instance.port}...")
        atexit.register(self.shutdown)
 
    def listen(self):
        while self.running:
            try:
                client_socket, addr = self.service_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
            except OSError:
                break
 
    def handle_client(self, client_socket):
        try:
            while True:
                command = recv_msg(client_socket)
                if not command:
                    break
                if command["method"] == "SHUTDOWN":
                    self.shutdown()
                    break

                method_name = command["method"]
                args = command["args"]
                kwargs = command["kwargs"]

                try:
                    method = getattr(self.service_instance, method_name)
                    result = method(*args, **kwargs)
                    response = {"success": True, "result": result}
                except Exception as e:
                    response = {"success": False, "error": str(e)}

                send_msg(client_socket, response)
        except Exception as e:
            print(f"Error in handle_client: {e}")
        finally:
            client_socket.close()
 
    def shutdown(self):
        if self.running:
            print("Shutting down server...")
            self.running = False
            self.service_socket.close()
            if hasattr(self.service_instance, "close"):
                self.service_instance.close()
                    
    @classmethod
    def master(cls, service_class, max_que, *service_args, **service_kwargs):
        try:
            print("Shutting down existing server...")
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((service_class.host, service_class.port))
            command = {"method": "SHUTDOWN", "args": [], "kwargs": {}}
            send_msg(client, command)  # Use the length-prefixed protocol!
            client.close()
            time.sleep(1)
        except ConnectionRefusedError:
            print("Server is not running.")
        print("Starting new server...")
        server_instance = cls(service_class, max_que, *service_args, **service_kwargs)
        threading.Thread(target=server_instance.listen, daemon=True).start()
        return server_instance.service_instance  # Return the service instance

class Client:
    def __init__(self, service_class, max_que=5):
        self.service_class = service_class
        self.host = service_class.host
        self.port = service_class.port
        self.max_que = max_que

    def __getattr__(self, name):
        def method_proxy(*args, **kwargs):
            retries = 3
            for attempt in range(retries):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                        client_socket.connect((self.host, self.port))
                        command = {
                            "method": name,
                            "args": args,
                            "kwargs": kwargs,
                        }
                        send_msg(client_socket, command)
                        response = recv_msg(client_socket)

                        if response["success"]:
                            return response["result"]
                        else:
                            raise Exception(f"Error calling {name}: {response['error']}")
                except ConnectionRefusedError:
                    if attempt < retries - 1:
                        print(f"Server is not running. Attempting to start... (Retry {attempt + 1}/{retries})")
                        self._start_server()
                        time.sleep(0.5)  # Allow the server time to start
                    else:
                        raise ConnectionRefusedError("Could not connect to the server after multiple retries.")
        return method_proxy

    def _start_server(self):
        server = Server(self.service_class, self.max_que)
        threading.Thread(target=server.listen, daemon=True).start()
        time.sleep(0.5)  # Allow server some time to initialize

    def shutdown(self):
        """Send a SHUTDOWN command to the server."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.connect((self.host, self.port))
                command = {"method": "SHUTDOWN", "args": [], "kwargs": {}}
                client_socket.sendall(pickle.dumps(command))
        except ConnectionRefusedError:
            print("Server is not running.")