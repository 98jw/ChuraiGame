"""
Django Management Command: Update Steam Sales Data
Fetches latest Steam sale data from steamsale.windbell.co.kr API.

Usage:
    python manage.py update_steam_sales

Data Structure:
- Current Sales: Games currently on sale (end_dt >= today)
- Top Sales: Top discounted games sorted by discount rate
- Best Historical Prices: Lowest price each game has ever been
"""
import requests
import json
import time
import os
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Fetch and update Steam sale data from steamsale.windbell.co.kr API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=2000,
            help='Number of sale items to fetch (default: 2000)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Items per API request (default: 100, max: 100)'
        )

    def handle(self, *args, **options):
        target_count = options['count']
        batch_size = min(options['batch_size'], 100)
        
        API_URL = "https://steamsale.windbell.co.kr/api/v1/sales"
        
        all_sales = []
        page = 1
        today = datetime.now().strftime('%Y%m%d')
        
        self.stdout.write(
            self.style.NOTICE(f"🚀 Starting Steam sale data update: Target {target_count} items")
        )
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://steamsale.windbell.co.kr/'
        }

        # Fetch all sale data
        while len(all_sales) < target_count:
            try:
                params = {
                    'keyword': '',
                    'page': page,
                    'size': batch_size
                }
                
                response = requests.get(API_URL, params=params, headers=headers, timeout=30)
                
                if response.status_code != 200:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Page {page} request failed: {response.status_code}")
                    )
                    break
                
                data = response.json()
                items = data.get('list', [])
                
                if not items:
                    self.stdout.write(self.style.WARNING("🏁 No more data available."))
                    break
                
                all_sales.extend(items)
                
                if page % 5 == 0:
                    self.stdout.write(f"   ✅ Page {page} done (Total: {len(all_sales)} items)")
                
                page += 1
                time.sleep(0.2)
                
            except requests.RequestException as e:
                self.stdout.write(self.style.ERROR(f"⚠️ Request error: {e}"))
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"⚠️ Error: {e}"))
                break

        # Process data into categories
        current_sales = []  # Currently on sale
        top_sales = []      # Top discounted
        best_prices = {}    # Best historical price per game
        skipped_scam = 0    # Counter for filtered scam/suspicious games
        
        for item in all_sales:
            game_id = item.get('game_id')
            end_dt = item.get('end_dt') or ''
            discount_rt = item.get('discount_rt') or 0
            sale_price = item.get('sale_price_va') or 0
            full_price = item.get('full_price_va') or 0
            sale_count = item.get('sale_cn', 0)
            
            # ========== SCAM/BUG FILTER ==========
            # 1. Skip if discount rate > 100% (bug or scam like -3200%)
            if discount_rt > 1.0:
                skipped_scam += 1
                continue
            
            # 2. Skip if original price is suspiciously high (> 500,000 won)
            if full_price > 500000:
                skipped_scam += 1
                continue
            
            # 3. Skip if high discount (90%+) but still expensive (> 30,000 won after discount)
            if discount_rt >= 0.9 and sale_price > 30000:
                skipped_scam += 1
                continue
            
            # 4. Skip if very low sale count (< 3) with very high discount (95%+)
            # This catches newly created scam games
            if sale_count < 3 and discount_rt >= 0.95:
                skipped_scam += 1
                continue
            
            # 5. Skip if title contains common scam patterns (optional)
            title = item.get('title_nm', '').lower()
            scam_keywords = ['puzzle pack', 'dlc bundle', 'soundtrack', 'ost', 'artbook']
            if discount_rt >= 0.95 and any(kw in title for kw in scam_keywords):
                skipped_scam += 1
                continue
            # ========== END FILTER ==========
            
            game_info = {
                'game_id': game_id,
                'title': item.get('title_nm'),
                'current_price': sale_price,
                'original_price': full_price,
                'discount_rate': discount_rt,
                'thumbnail': item.get('img_lk'),
                'store_link': item.get('store_lk'),
                'end_date': end_dt,
                'sale_count': sale_count
            }
            
            # Current Sales: end_dt >= today (or empty means ongoing)
            if end_dt >= today or end_dt == '':
                if discount_rt and discount_rt > 0:
                    current_sales.append(game_info)
            
            # Track best historical price per game
            if game_id and sale_price and sale_price > 0:
                if game_id not in best_prices or sale_price < best_prices[game_id]['current_price']:
                    best_prices[game_id] = {
                        **game_info,
                        'is_best_price': True
                    }
        
        self.stdout.write(f"   ⚠️ Filtered {skipped_scam} suspicious/scam games")
        
        # Sort current sales by discount rate (highest first)
        current_sales.sort(key=lambda x: x.get('discount_rate', 0) or 0, reverse=True)
        
        # Top Sales: Top 50 by sale_count (popularity - more sales = more popular)
        # Filter to only include games with good discounts (>= 50%)
        popular_sales = [g for g in current_sales if (g.get('discount_rate') or 0) >= 0.5]
        popular_sales.sort(key=lambda x: x.get('sale_count', 0) or 0, reverse=True)
        top_sales = popular_sales[:50]
        
        # Convert best_prices dict to list
        best_prices_list = list(best_prices.values())
        best_prices_list.sort(key=lambda x: x.get('discount_rate', 0) or 0, reverse=True)
        
        # Create combined result
        result = {
            'updated_at': datetime.now().isoformat(),
            'current_sales': current_sales[:500],  # Limit to 500
            'top_sales': top_sales[:50],           # Top 50
            'best_prices': best_prices_list[:200], # Top 200 best prices
            'stats': {
                'total_fetched': len(all_sales),
                'current_count': len(current_sales),
                'top_count': len(top_sales),
                'best_prices_count': len(best_prices_list)
            }
        }

        # Save to file
        file_path = os.path.join(settings.BASE_DIR, 'users', 'steam_sale_data.json')
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            self.stdout.write(
                self.style.SUCCESS(f"\n🎉 Complete!")
            )
            self.stdout.write(f"   📊 Total fetched: {len(all_sales)}")
            self.stdout.write(f"   🔥 Current sales: {len(current_sales)}")
            self.stdout.write(f"   ⭐ Top sales: {len(top_sales)}")
            self.stdout.write(f"   💰 Best prices tracked: {len(best_prices_list)}")
            self.stdout.write(f"   📁 Saved to: {file_path}")
            
        except IOError as e:
            raise CommandError(f"Failed to save file: {e}")

        # Also update the legacy format for backward compatibility
        legacy_path = os.path.join(settings.BASE_DIR, 'users', 'steam_sale_dataset_fast.json')
        try:
            with open(legacy_path, 'w', encoding='utf-8') as f:
                json.dump(current_sales[:target_count], f, ensure_ascii=False, indent=2)
            self.stdout.write(f"   📁 Legacy file updated: {legacy_path}")
        except IOError as e:
            self.stdout.write(self.style.WARNING(f"Failed to update legacy file: {e}"))
