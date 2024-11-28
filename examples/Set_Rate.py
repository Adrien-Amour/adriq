import socket
import pickle
from adriq.Counters import *

def send_set_rate_command(host, port, new_rate):
    command = f"SET_RATE {new_rate}"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((host, port))
            client_socket.sendall(pickle.dumps(command))
            response = pickle.loads(client_socket.recv(4096))
            print(f"Response: {response}")
    except ConnectionRefusedError:
        print("Failed to connect to the server. Is it running?")

if __name__ == "__main__":
    host = QuTau_Reader.host
    port = QuTau_Reader.port
    new_rate = input("Enter new rate: ")
    send_set_rate_command(host, port, new_rate)