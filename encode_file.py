from perp.encode import dump_encoded
from getpass import getpass
import json 
import os 

wallets_folder = "wallets_encoded"

if not os.path.isdir(wallets_folder):
    os.mkdir(wallets_folder)

filename = input("filename: ")
print()
output_name = input("output filename: ")
print()
password = getpass()

with open(filename) as file:
    data = json.load(file)

dump_encoded(data, password, os.path.join(wallets_folder,output_name))