import json
from projects.justbill import config
from projects.justbill.database import ItemDB

db = ItemDB(config)
items = db.load()

diamond_items = [i['name'] for i in items if 'diamond' in i['name'].lower()]
necklace_items = [i['name'] for i in items if 'necklace' in i['name'].lower()]
diamond_necklace_items = [i['name'] for i in items if 'diamond' in i['name'].lower() and 'necklace' in i['name'].lower()]

print("--- Diamond Items ---")
print(json.dumps(diamond_items, indent=2))
print("\n--- Necklace Items ---")
print(json.dumps(necklace_items, indent=2))
print("\n--- Diamond Necklace Items ---")
print(json.dumps(diamond_necklace_items, indent=2))
