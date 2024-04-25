import hashlib 
from cryptography.fernet import Fernet 
import json 

def encode(data, password):
    key = hashlib.sha256(password.encode()).hexdigest()[:43] + "="
    f = Fernet(key)

    encrypted = f.encrypt(json.dumps(data).encode())

    return encrypted

def decode(encoded_data, password):
    key = hashlib.sha256(password.encode()).hexdigest()[:43] + "="
    f = Fernet(key)

    try:
        decrypted = f.decrypt(encoded_data).decode()
    except:
        print("Invalid token")
        return None 
    

    return decrypted

def dump_encoded(data, password, filename):
    encoded = encode(data, password)

    with open(filename, 'wb') as file:
        file.write(encoded)

def load_encoded(password, filename):
    with open(filename, "rb") as file:
        data = file.read()

    return json.loads(decode(data, password))
