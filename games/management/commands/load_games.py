from django.core.management.base import BaseCommand
from games.models import Game
import json
import os
from django.conf import settings
import re

class Command(BaseCommand):
    help = 'Load game data from Steam sale JSON files into database'

    def extract_app_id(self, game_id_str):
        """Extract numeric app ID from Steam game_id"""
        match = re.search(r'\d+', str(game_id_str))
        if match:
            return int(match.group())
        try:
            return int(game_id_str)
        except:
            return None

    def handle(self, *args, **options):
        # Try new format first, then legacy
        new_json_path = os.path.join(settings.BASE_DIR, 'users', 'steam_sale_data.json')
        legacy_json_path = os.path.join(settings.BASE_DIR, 'users', 'steam_sale_dataset_fast.json')
        
        games_data = []
        
        if os.path.exists(new_json_path):
            self.stdout.write(f'Loading games from {new_json_path}...')
            with open(new_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Combine current_sales and best_prices
                games_data = data.get('current_sales', [])
                # Also add best_prices for historical games
                for game in data.get('best_prices', []):
                    if game.get('game_id') not in [g.get('game_id') for g in games_data]:
                        games_data.append(game)
        elif os.path.exists(legacy_json_path):
            self.stdout.write(f'Loading games from {legacy_json_path}...')
            with open(legacy_json_path, 'r', encoding='utf-8') as f:
                games_data = json.load(f)
        else:
            self.stdout.write(self.style.ERROR(f'No game data file found!'))
            return
        
        self.stdout.write(f'Found {len(games_data)} games to process...')
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for game_data in games_data:
            game_id_str = game_data.get('game_id')
            title = game_data.get('title')
            thumbnail = game_data.get('thumbnail', '')
            store_link = game_data.get('store_link', '')
            
            if not game_id_str or not title:
                skipped_count += 1
                continue
            
            # Extract numeric app ID
            app_id = self.extract_app_id(game_id_str)
            if not app_id:
                self.stdout.write(self.style.WARNING(f'Could not extract app_id from: {game_id_str}'))
                skipped_count += 1
                continue
            
            # Create or update game
            game, created = Game.objects.update_or_create(
                steam_appid=app_id,
                defaults={
                    'title': title,
                    'genre': 'Unknown',  # JSON doesn't have genre info
                    'image_url': thumbnail or 'https://via.placeholder.com/460x215',
                }
            )
            
            if created:
                created_count += 1
                if created_count % 100 == 0:
                    self.stdout.write(f'  Created {created_count} games...')
            else:
                updated_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'\nCompleted!\n'
            f'  Created: {created_count}\n'
            f'  Updated: {updated_count}\n'
            f'  Skipped: {skipped_count}\n'
            f'  Total: {Game.objects.count()} games in database'
        ))
