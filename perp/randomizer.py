import random 
import perp.config as config
import perp.constants as constants


class Randomizer:
    def get_random_time(self):
        return random.randrange(config.MIN_POSITION_TIME, config.MAX_POSITION_TIME)
    
    def get_random_sides(self):
        return random.choice([constants.LONG_PERP1_SHORT_PERP2, constants.LONG_PERP2_SHORT_PERP1])

    def get_random_leverage(self):
        return random.randrange(config.MIN_LEVERAGE, config.MAX_LEVERAGE)
    
    def get_random_coin(self):
        return random.choice(config.COINS)
    def get_random_sleep_time(self):
        return random.randrange(config.MIN_SLEEP_TIME, config.MAX_SLEEP_TIME)
    def get_random_order(self):
        return random.choice([-1, 1])
    