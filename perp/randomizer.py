import random 
import perp.config as config
from copy import copy 
import math 
import perp.constants as constants 

def random_int(min, max):
    if max - min == 1:
        return min 
    return random.randrange(min, max)

def random_coins(open_positions, n, coins):
    return random.sample([coin for coin in coins if coin not in open_positions], n)


def random_sides(current_sides, n):
    count_a = current_sides.count(constants.LONG)
    count_b = current_sides.count(constants.SHORT)
    
    res = []
    i = 0
    while i < n:
        if count_a > count_b:
            res += [constants.SHORT]
            count_b += 1 
        else:
            res += [constants.LONG]
            count_a += 1
        i += 1
    random.shuffle(res)
    return res 



