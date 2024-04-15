import os 
import logging
from perp.main import Main
from perp.utils.funcs import run_with_traceback
import time 

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)
main = Main()
for pair in main.pairs:
    main.load_user_states(pair)
    main.update_positions(pair)
    main.remove_positions(pair)
                
    time.sleep(5)
    p1, p2 = pair
    open_positions = set(p1.positions.keys()) & set(p2.positions.keys())
    for coin in open_positions:
        run_with_traceback(main.close_position, logger, pair, coin)
    
if os.path.isfile("positions_state.json"):
    os.remove("positions_state.json")

