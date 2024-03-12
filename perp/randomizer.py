import random 
import perp.config as config

def random_int(min, max):
    return random.randrange(min, max)

def random_coins(open_positions, n):
    return random.sample([coin for coin in config.COINS if coin not in open_positions], n)

