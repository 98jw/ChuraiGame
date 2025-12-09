from django.core.management.base import BaseCommand
from games.utils import search_games
import json

class Command(BaseCommand):
    help = 'Search for games on RAWG API'

    def add_arguments(self, parser):
        parser.add_argument(
            'query',
            type=str,
            help='Game title to search for'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Number of results to show (default: 10)'
        )
        parser.add_argument(
            '--save',
            action='store_true',
            help='Save results to JSON file'
        )

    def handle(self, *args, **options):
        query = options['query']
        limit = options['limit']
        save_to_file = options['save']

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS(f'  Searching RAWG for: "{query}"'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        results = search_games(query, page_size=limit)

        if not results:
            self.stdout.write(self.style.WARNING('No results found'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {len(results)} games:\n'))

        for idx, game in enumerate(results, 1):
            self.stdout.write(f"\n{idx}. {game['title']}")
            self.stdout.write(f"   RAWG ID: {game['rawg_id']}")
            self.stdout.write(f"   Rating: {game.get('rating', 'N/A')}")
            self.stdout.write(f"   Released: {game.get('released', 'N/A')}")
            if game.get('genres'):
                self.stdout.write(f"   Genres: {', '.join(game['genres'])}")
            if game.get('metacritic'):
                self.stdout.write(f"   Metacritic: {game['metacritic']}")

        if save_to_file:
            filename = f'search_{query.replace(" ", "_")}.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            self.stdout.write(self.style.SUCCESS(f'\n✓ Saved to {filename}'))

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
