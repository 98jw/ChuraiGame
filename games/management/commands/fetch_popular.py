from django.core.management.base import BaseCommand
from games.utils import (
    get_popular_games,
    get_top_rated_games,
    get_trending_games,
    get_new_releases,
    get_upcoming_games
)
import json

class Command(BaseCommand):
    help = 'Fetch popular, top-rated, or trending games from RAWG API'

    def add_arguments(self, parser):
        parser.add_argument(
            'category',
            type=str,
            choices=['popular', 'top-rated', 'trending', 'new-releases', 'upcoming'],
            help='Category of games to fetch'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Number of games to show (default: 10)'
        )
        parser.add_argument(
            '--save',
            action='store_true',
            help='Save results to JSON file'
        )

    def handle(self, *args, **options):
        category = options['category']
        limit = options['limit']
        save_to_file = options['save']

        # Function mapping
        category_functions = {
            'popular': get_popular_games,
            'top-rated': get_top_rated_games,
            'trending': get_trending_games,
            'new-releases': get_new_releases,
            'upcoming': get_upcoming_games
        }

        category_titles = {
            'popular': '인기 게임 (Most Popular)',
            'top-rated': '평점 높은 게임 (Top Rated)',
            'trending': '트렌딩 게임 (Highest Metacritic)',
            'new-releases': '신작 게임 (New Releases)',
            'upcoming': '출시 예정 게임 (Upcoming)'
        }

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS(f'  {category_titles[category]}'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        # Fetch games
        fetch_function = category_functions[category]
        results = fetch_function(page_size=limit)

        if not results:
            self.stdout.write(self.style.WARNING('No results found'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {len(results)} games:\n'))

        for idx, game in enumerate(results, 1):
            self.stdout.write(f"\n{idx}. {game['title']}")
            self.stdout.write(f"   RAWG ID: {game['rawg_id']}")
            
            if game.get('rating'):
                self.stdout.write(f"   Rating: ⭐ {game['rating']}")
            
            if game.get('metacritic'):
                self.stdout.write(f"   Metacritic: {game['metacritic']}")
            
            if game.get('released'):
                self.stdout.write(f"   Released: {game['released']}")
            
            if game.get('added'):
                self.stdout.write(f"   Added by: {game['added']:,} users")
            
            if game.get('genres'):
                self.stdout.write(f"   Genres: {', '.join(game['genres'][:3])}")

        if save_to_file:
            filename = f'{category}_games.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            self.stdout.write(self.style.SUCCESS(f'\n✓ Saved to {filename}'))

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
