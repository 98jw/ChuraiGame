"""
RAWG API를 사용하여 게임 장르를 업데이트하는 management command

사용법:
    python manage.py update_genres
    python manage.py update_genres --limit=100  # 처음 100개만

이 스크립트는 DB에서 장르가 없거나 'Unknown'인 게임을 찾아
RAWG API에서 장르 정보를 가져와 업데이트합니다.
"""

import time
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Q
from games.models import Game


class Command(BaseCommand):
    help = 'Fetch and update missing genres from RAWG API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of games to process (default: all)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.6,
            help='Delay between API calls in seconds (default: 0.6)'
        )

    def handle(self, *args, **options):
        limit = options.get('limit')
        delay = options.get('delay', 0.6)
        
        # RAWG API 키 가져오기
        rawg_api_key = getattr(settings, 'RAWG_API_KEY', None)
        
        if not rawg_api_key:
            self.stdout.write(self.style.ERROR('❌ RAWG_API_KEY is missing in settings!'))
            self.stdout.write('   Add RAWG_API_KEY = "your_key" to settings.py')
            return

        # 장르가 없거나 Unknown인 게임만 가져오기
        games_to_update = Game.objects.filter(
            Q(genre__isnull=True) | Q(genre='') | Q(genre='Unknown')
        )
        
        if limit:
            games_to_update = games_to_update[:limit]
        
        total = games_to_update.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('✅ All games already have genres!'))
            return
            
        self.stdout.write(f"🔍 Found {total} games without genres...")
        self.stdout.write(f"⏱️  API delay: {delay}s per request")
        self.stdout.write(f"⏰ Estimated time: ~{int(total * delay / 60)} minutes")
        self.stdout.write("")

        success_count = 0
        failed_count = 0
        
        for i, game in enumerate(games_to_update):
            try:
                # RAWG API 검색
                url = "https://api.rawg.io/api/games"
                params = {
                    'key': rawg_api_key,
                    'search': game.title,
                    'page_size': 1,
                    'search_precise': True
                }
                
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get('results', [])

                    if results:
                        best_match = results[0]
                        
                        # 장르 추출
                        genres = [g['name'] for g in best_match.get('genres', [])]
                        genre_str = ", ".join(genres) if genres else "Unknown"
                        
                        # 추가 정보도 업데이트
                        game.genre = genre_str
                        
                        # RAWG에서 더 좋은 이미지가 있으면 업데이트
                        bg_image = best_match.get('background_image')
                        if bg_image and not game.background_image:
                            game.background_image = bg_image
                        
                        # 메타크리틱 점수
                        metacritic = best_match.get('metacritic')
                        if metacritic and not game.metacritic_score:
                            game.metacritic_score = metacritic
                        
                        game.save()
                        
                        success_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"[{i+1}/{total}] ✅ {game.title} → {genre_str}")
                        )
                    else:
                        failed_count += 1
                        self.stdout.write(
                            self.style.WARNING(f"[{i+1}/{total}] ⚠️  No match: {game.title}")
                        )
                        
                elif response.status_code == 429:
                    # Rate limit - 잠시 대기 후 재시도
                    self.stdout.write(self.style.WARNING("⏳ Rate limited, waiting 30 seconds..."))
                    time.sleep(30)
                    # 재시도하지 않고 다음으로 넘어감
                    failed_count += 1
                else:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"[{i+1}/{total}] ❌ API Error {response.status_code}: {game.title}")
                    )

            except requests.Timeout:
                failed_count += 1
                self.stdout.write(
                    self.style.WARNING(f"[{i+1}/{total}] ⏱️  Timeout: {game.title}")
                )
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"[{i+1}/{total}] ❌ Error: {game.title} - {e}")
                )
            
            # API 속도 제한 방지
            time.sleep(delay)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("🎉 Genre update completed!"))
        self.stdout.write(f"   ✅ Success: {success_count}")
        self.stdout.write(f"   ❌ Failed: {failed_count}")
        
        # 현재 상태 표시
        remaining = Game.objects.filter(
            Q(genre__isnull=True) | Q(genre='') | Q(genre='Unknown')
        ).count()
        self.stdout.write(f"   📊 Remaining without genre: {remaining}")
