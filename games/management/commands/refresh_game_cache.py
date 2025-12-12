"""
게임 목록 캐시를 갱신하는 management command

사용법:
    python manage.py refresh_game_cache

이 스크립트는 RAWG API에서 인기 게임, 평점 높은 게임, 신작 게임 등을
가져와서 DB 캐시에 저장합니다. 메인 페이지 로딩 속도가 크게 향상됩니다.
"""

from django.core.management.base import BaseCommand
from games.models import CachedGameList
from games.utils import (
    get_popular_games,
    get_top_rated_games,
    get_trending_games,
    get_new_releases,
    get_upcoming_games,
)


class Command(BaseCommand):
    help = 'Refresh cached game lists from RAWG API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--category',
            type=str,
            default='all',
            help='Category to refresh: popular, top_rated, trending, new_releases, upcoming, or all'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=40,
            help='Number of games to cache per category (default: 40)'
        )

    def handle(self, *args, **options):
        category = options.get('category', 'all')
        limit = options.get('limit', 40)
        
        categories_to_refresh = []
        
        if category == 'all':
            categories_to_refresh = ['popular', 'top_rated', 'trending', 'new_releases']
        else:
            categories_to_refresh = [category]
        
        self.stdout.write(f"🔄 Refreshing game cache for: {', '.join(categories_to_refresh)}")
        self.stdout.write(f"📊 Limit per category: {limit} games\n")
        
        for cat in categories_to_refresh:
            try:
                self.stdout.write(f"  ⏳ Fetching {cat}...")
                
                if cat == 'popular':
                    games = get_popular_games(page_size=limit, all_time=False)
                elif cat == 'top_rated':
                    games = get_top_rated_games(page_size=limit)
                elif cat == 'trending':
                    games = get_trending_games(page_size=limit)
                elif cat == 'new_releases':
                    games = get_new_releases(page_size=limit)
                elif cat == 'upcoming':
                    games = get_upcoming_games(page_size=limit)
                else:
                    self.stdout.write(self.style.WARNING(f"  ⚠️ Unknown category: {cat}"))
                    continue
                
                if games:
                    CachedGameList.set_cached_games(cat, games)
                    self.stdout.write(self.style.SUCCESS(f"  ✅ {cat}: {len(games)} games cached"))
                else:
                    self.stdout.write(self.style.WARNING(f"  ⚠️ {cat}: No games fetched"))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ {cat}: Error - {e}"))
        
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("🎉 Cache refresh completed!"))
        
        # 현재 캐시 상태 표시
        self.stdout.write("\n📊 Current cache status:")
        for cache in CachedGameList.objects.all():
            self.stdout.write(f"   - {cache.category}: {len(cache.games_data)} games (updated: {cache.updated_at})")
