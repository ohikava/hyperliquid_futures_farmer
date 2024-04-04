import os 
from perp.stats import get_profit
from datetime import datetime
start_date = input()
end_date=input()
start_date = datetime.strptime(start_date, "%Y-%m-%d")
end_date = datetime.strptime(end_date, "%Y-%m-%d")


files = os.listdir("fills")

res = []
for file in files:
    if datetime.strptime(file.replace(".txt", ""), "%Y-%m-%d") < start_date:
        continue 
    if datetime.strptime(file.replace(".txt", ""), "%Y-%m-%d") > end_date:
        continue 
    res.append(file)

profits = [get_profit(f"fills/{file}") for file in res]

w1_profit = sum(i[2] for i in profits)
w2_profit = sum(i[3] for i in profits)

print(f"{profits[0][0][:15]}: {w1_profit}")
print(f"{profits[0][1][:15]}: {w2_profit}")
print(f"TOTAL: {w1_profit + w2_profit}")

