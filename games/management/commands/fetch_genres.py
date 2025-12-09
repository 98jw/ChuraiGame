from django.core.management.base import BaseCommand
from games.utils import get_genres
import json

class Command(BaseCommand):
    help = 'Fetch and display genre list from RAWG API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--save',
            action='store_true',
            help='Save genres to JSON file'
        )

    def handle(self, *args, **options):
        save_to_file = options['save']

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('  Fetching Genres from RAWG'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        genres = get_genres()

        if not genres:
            self.stdout.write(self.style.ERROR('Failed to fetch genres'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {len(genres)} genres:\n'))

        for genre in genres:
            self.stdout.write(
                f"  • {genre['name']:20} "
                f"(slug: {genre['slug']:15}) "
                f"- {genre['games_count']} games"
            )

        if save_to_file:
            filename = 'rawg_genres.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(genres, f, indent=2, ensure_ascii=False)
            self.stdout.write(self.style.SUCCESS(f'\n✓ Saved to {filename}'))

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
