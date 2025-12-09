import os
import sys
import django
import json
import re

# Django setup
sys.path.append(r'c:\Users\jam67\Desktop\ssafy\관통프로젝트\ChuraiGame')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ChuraiGame.settings')
django.setup()

from games.models import Game

def extract_app_id(game_id_str):
    """Extract numeric app ID from Steam game_id"""
    match = re.search(r'\d+', str(game_id_str))
    if match:
        return int(match.group())
    try:
        return int(game_id_str)
    except:
        return None

# Load JSON
json_path = r'c:\Users\jam67\Desktop\ssafy\관통프로젝트\ChuraiGame\users\steam_sale_dataset_fast.json'
with open(json_path, 'r', encoding='utf-8') as f:
    games_data = json.load(f)

print(f'Loading {len(games_data)} games...')

created = 0
updated = 0
skipped = 0

for i, game_data in enumerate(games_data):
    game_id_str = game_data.get('game_id')
    title = game_data.get('title')
    thumbnail = game_data.get('thumbnail', '')
    
    if not game_id_str or not title:
        skipped += 1
        continue
    
    app_id = extract_app_id(game_id_str)
    if not app_id:
        skipped += 1
        updated += 1
    
    if (i + 1) % 500 == 0:
        print(f'  Processed {i + 1} games...')

print(f'\nCompleted!')
print(f'  Created: {created}')
print(f'  Updated: {updated}')
print(f'  Skipped: {skipped}')
print(f'  Total in DB: {Game.objects.count()}')
