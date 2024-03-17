from perp.main import Main 
import logging 
from datetime import datetime    
    

logging.basicConfig(format="%(asctime)s %(name)s [%(levelname)s] %(message)s", level=logging.INFO, filename=f"logs/{datetime.today().strftime('%Y-%m-%d')}.txt", datefmt='%I:%M:%S', filemode='w')

if __name__ == "__main__":
    main = Main()
    try:
        main.run()
    finally:
        main.clean()