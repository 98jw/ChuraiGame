"""
JSON 데이터셋에서 게임을 DB로 적재하는 management command

사용법:
    python manage.py load_games

이 스크립트는 steam_sale_dataset_fast.json 파일을 읽어서
Game 테이블에 데이터를 추가합니다.
"""

import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from games.models import Game


class Command(BaseCommand):
    help = 'Load games from steam_sale_dataset_fast.json into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of games to import (default: all)'
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing games as well'
        )

    def handle(self, *args, **options):
        limit = options.get('limit')
        update_existing = options.get('update', False)
        
        # 1. JSON 파일 경로 설정
        json_path = os.path.join(settings.BASE_DIR, 'users', 'steam_sale_dataset_fast.json')
        
        if not os.path.exists(json_path):
            json_path = os.path.join(settings.BASE_DIR, 'steam_sale_dataset_fast.json')
        
        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f'JSON file not found at {json_path}'))
            return

        self.stdout.write(f"📂 Loading data from: {json_path}")

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            total = len(data)
            if limit:
                data = data[:limit]
                self.stdout.write(f"📊 Processing {limit} of {total} games...")
            else:
                self.stdout.write(f"📊 Processing all {total} games...")

            created_count = 0
            updated_count = 0
            skipped_count = 0
            
            for i, item in enumerate(data):
                steam_id = item.get('steam_app_id')
                if not steam_id:
                    skipped_count += 1
                    continue
                
                try:
                    steam_id_int = int(steam_id)
                except (ValueError, TypeError):
                    skipped_count += 1
                    continue
                
                # 게임 데이터 준비
                game_data = {
                    'title': item.get('title', f'Game {steam_id}'),
                    'image_url': item.get('thumbnail', ''),
                    'genre': 'Unknown',  # 나중에 RAWG에서 업데이트
                }
                
                # Steam App ID를 rawg_id 필드에 저장 (고유 식별자로 사용)
                try:
                    game, created = Game.objects.get_or_create(
                        rawg_id=steam_id_int,
                        defaults={
                            **game_data,
                            'steam_appid': steam_id_int,  # Steam App ID도 저장
                        }
                    )
                    
                    if created:
                        created_count += 1
                    elif update_existing:
                        # 기존 게임 업데이트
                        for key, value in game_data.items():
                            setattr(game, key, value)
                        game.steam_appid = steam_id_int
                        game.save()
                        updated_count += 1
                    
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Error with {item.get('title')}: {e}"))
                    skipped_count += 1
                    continue
                
                # 진행 상황 표시
                if (i + 1) % 100 == 0:
                    self.stdout.write(f"⏳ Processed {i + 1}/{len(data)} games...")

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(f"✅ Import completed!"))
            self.stdout.write(f"   📥 Created: {created_count} new games")
            if update_existing:
                self.stdout.write(f"   🔄 Updated: {updated_count} existing games")
            self.stdout.write(f"   ⏭️  Skipped: {skipped_count} games")
            self.stdout.write(f"   📊 Total in DB: {Game.objects.count()} games")

        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f'Invalid JSON file: {e}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error occurred: {str(e)}'))
