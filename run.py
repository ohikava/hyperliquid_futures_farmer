from perp.main import Main 
import perp.config as config 
import logging 
from datetime import datetime    

if config.ON_SERVER:
    logging.basicConfig(format="%(asctime)s %(name)s [%(levelname)s] %(message)s", level=logging.INFO, datefmt='%I:%M:%S')
else:
    logging.basicConfig(format="%(asctime)s %(name)s [%(levelname)s] %(message)s", level=logging.INFO, filename=f"logs/{datetime.today().strftime('%Y-%m-%d')}.txt", datefmt='%I:%M:%S', filemode='a')

if __name__ == "__main__":
    main = Main()
    main.run()