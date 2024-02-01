import json
import socket
import time
import os


SERVICE_IP = os.environ['MY_POD_IP']
PORT = int(os.environ['TCP_MESSAGE_PORT'])
BUFFER_SIZE = 1024
DATA_VOLUME_PATH = os.environ['SHARE_PATH']


def call_service(send_message: str) -> bytes:
    print('socket start')
    t = time.time()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((SERVICE_IP, PORT))

        # SEND TO SERVICE
        if send_message:
            send_data = json.dumps({"filename": send_message}).encode()
            print('sending')
            s.sendall(send_data)
            s.shutdown(1)
            print('sent')

        # LISTENING
        print('wait for data')
        received_message = b''
        while True:
            chunk = s.recv(BUFFER_SIZE)
            if not chunk:
                break
            else:
                received_message += chunk
        received_json = json.loads(received_message.decode())
        print('recieved')

    print('socket time [ms]:'.ljust(20), (time.time() - t)*1000)

    data_path = os.path.join(DATA_VOLUME_PATH, received_json['filename'])
    with open(data_path, 'rb') as f:
        processed_data = f.read()

    return processed_data


if __name__ == '__main__':
    txt = 'hello, world!'
    with open('/data/sample.txt', 'wb') as f:
        f.write(txt.encode())
    processed_data = call_service('sample.txt')
    print(processed_data.decode())
