import perp.constants as constants
from platform import system
import json 
import traceback
from perp.utils.types import Proxy

PLATFORM = system()

def calculate_profit(open, close):
    is_buy = 1 if open["side"] == constants.LONG else -1 

    return is_buy * (close["px"] - open["px"]) * open["sz"]


def get_correct_path(path: str) -> str:
    if PLATFORM == "Windows":
        return path.replace("/", "\\")
    elif PLATFORM == "Darwin":
        return path.replace("\\", "/")


def load_json_file(path: str) -> dict:
    _path = get_correct_path(path)
    with open(_path, encoding="utf-8") as file:
        return json.load(file)
    
def dump_json(file_path: str, data: dict) -> None:
    with open(get_correct_path(file_path), "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

def run_with_traceback(func, logger, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(traceback.format_exc())
        return None
    
def extract_info_from_proxy_row(proxy_row: str) -> Proxy:
    first_half, second_half = proxy_row.split("@")
    print(first_half)
    _, login, password = first_half.split(":")
    login = login.replace('//', '')
    ip, port = second_half.split(":")
    return {
        "host": ip,
        "port": int(port),
        "username": login,
        "password": password
    }
