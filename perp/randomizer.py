import random 
import perp.config as config
from copy import copy 
import math 
import perp.constants as constants 

def random_int(min, max):
    return random.randrange(min, max)

def random_coins(open_positions, n):
    return random.sample([coin for coin in config.COINS if coin not in open_positions], n)

def random_sides(coins):
    if not len(coins):
        return {}
    
    coins = copy(coins)
    random.shuffle(coins)
    sep = math.ceil(len(coins) / 2)
    first_half = [constants.LONG] * sep
    second_half = [constants.SHORT] * (len(coins) - sep)

    r = first_half + second_half
    r = [(i, k) for i, k in zip(coins, r)]
    random.shuffle(r)
    return dict(r)



