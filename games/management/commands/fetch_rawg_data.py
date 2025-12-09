from django.core.management.base import BaseCommand
from django.db.models import Q
from games.models import Game
from games.utils import update_game_with_rawg
import time
import logging

# Configure logging for this command
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class Command(BaseCommand):
    help = 'Fetch RAWG data (images, descriptions, trailers) for games in database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of games to update'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if RAWG data already exists'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Delay between API requests in seconds (default: 0.5)'
        )
        parser.add_argument(
            '--appid',
            type=int,
            default=None,
            help='Update only a specific game by Steam AppID'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        force = options['force']
        delay = options['delay']
        appid = options['appid']

        # Statistics
        stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0
        }

        # Query games to update
        if appid:
            games = Game.objects.filter(steam_appid=appid)
            if not games.exists():
                self.stdout.write(self.style.ERROR(f'No game found with AppID {appid}'))
                return
        else:
            games = Game.objects.all()
        
        # Filter based on force flag
        if not force:
            # Only update games that don't have RAWG data
            games = games.filter(
                Q(rawg_id__isnull=True) | 
                Q(background_image='') | 
                Q(description='')
            ).distinct()
        
        # Apply limit
        if limit:
            games = games[:limit]
        
        stats['total'] = games.count()
        
        if stats['total'] == 0:
            self.stdout.write(self.style.WARNING('No games to update. Use --force to update all games.'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\n{"="*70}'))
        self.stdout.write(self.style.SUCCESS(f'  RAWG Data Enrichment'))
        self.stdout.write(self.style.SUCCESS(f'{"="*70}'))
        self.stdout.write(f'Total games to process: {stats["total"]}')
        self.stdout.write(f'Force update: {force}')
        self.stdout.write(f'API delay: {delay}s')
        self.stdout.write(self.style.SUCCESS(f'{"="*70}\n'))
        
        # Process games
        for idx, game in enumerate(games, 1):
            progress = f'[{idx}/{stats["total"]}]'
            self.stdout.write(f'\n{progress} Processing: {game.title} (AppID: {game.steam_appid})')
            
            try:
                success = update_game_with_rawg(game, force_refresh=force)
                
                if success:
                    stats['success'] += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Successfully updated'))
                else:
                    stats['skipped'] += 1
                    self.stdout.write(self.style.WARNING(f'  ⊘ Skipped or no data found'))
                
                # Rate limiting to respect API quotas
                # RAWG free tier: 20,000 requests/month ≈ 650/day ≈ 27/hour
                time.sleep(delay)
                
            except Exception as e:
                stats['failed'] += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))
        
        # Print summary
        self.stdout.write(self.style.SUCCESS(f'\n{"="*70}'))
        self.stdout.write(self.style.SUCCESS(f'  Summary'))
        self.stdout.write(self.style.SUCCESS(f'{"="*70}'))
        self.stdout.write(f'Total processed: {stats["total"]}')
        self.stdout.write(self.style.SUCCESS(f'Successful: {stats["success"]}'))
        self.stdout.write(self.style.WARNING(f'Skipped: {stats["skipped"]}'))
        self.stdout.write(self.style.ERROR(f'Failed: {stats["failed"]}'))
        self.stdout.write(self.style.SUCCESS(f'{"="*70}\n'))
