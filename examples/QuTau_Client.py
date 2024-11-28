import socket
import pickle
import time
from adriq.Servers import *
from adriq.Counters import *


class QuTauClient:
    def __init__(self, host='localhost', port=8001):
        self.host = host
        self.port = port

    def send_command(self, command):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.connect((self.host, self.port))
            client.sendall(pickle.dumps(command))
            response = pickle.loads(client.recv(4096))
        return response

    def get_last_timestamps(self):
        return self.send_command("GET_LAST_TIMESTAMPS")

if __name__ == "__main__":
    Server.status_check(QuTau_Reader, max_que=5)
    client = QuTauClient()

    start_time = time.time()
    timestamps = client.get_last_timestamps()
    end_time = time.time()

    elapsed_time = end_time - start_time
    print(f"Time taken to retrieve timestamps: {elapsed_time:.6f} seconds")
    print(f"Timestamps: {timestamps}")