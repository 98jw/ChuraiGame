import os
import requests
import logging
from django.conf import settings
from .models import Game, GameScreenshot, GameTrailer

# Configure logging
logger = logging.getLogger(__name__)

RAWG_API_KEY = os.getenv('RAWG_API_KEY')
BASE_URL = "https://api.rawg.io/api"

def get_rawg_game_id(game_title, steam_appid=None):
    """
    Search for a game by title and optionally Steam AppID, return its RAWG ID.
    Tries to find the best match using Steam store link if available.
    """
    if not RAWG_API_KEY:
        logger.warning("RAWG_API_KEY not found in environment variables.")
        return None

    # Strategy 1: Search by Steam AppID (most accurate)
    if steam_appid:
        try:
            params = {
                'key': RAWG_API_KEY,
                'stores': '1',  # 1 = Steam
                'search': game_title,
                'page_size': 5
            }
            response = requests.get(f"{BASE_URL}/games", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Check if any result has matching Steam AppID in stores
            for result in data.get('results', []):
                game_id = result['id']
                # Fetch detailed info to check Steam store
                details = fetch_rawg_game_details(game_id)
                if details and 'stores' in details:
                    for store in details.get('stores', []):
                        if store.get('store', {}).get('id') == 1:  # Steam store
                            store_url = store.get('url', '')
                            if f'/{steam_appid}' in store_url or f'app/{steam_appid}' in store_url:
                                logger.info(f"Found exact Steam match for {game_title} (AppID: {steam_appid})")
                                return game_id
        except requests.RequestException as e:
            logger.error(f"Error searching by Steam AppID for {game_title}: {e}")

    # Strategy 2: Precise title search
    params = {
        'key': RAWG_API_KEY,
        'search': game_title,
        'search_precise': True,
        'page_size': 1
    }
    try:
        response = requests.get(f"{BASE_URL}/games", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('results'):
            game_id = data['results'][0]['id']
            logger.info(f"Found RAWG game for '{game_title}': ID {game_id}")
            return game_id
        else:
            logger.warning(f"No RAWG results found for '{game_title}'")
    except requests.RequestException as e:
        logger.error(f"Error searching for game '{game_title}': {e}")
    
    return None

def fetch_rawg_game_details(game_id):
    """
    Fetch detailed game information from RAWG.
    """
    if not RAWG_API_KEY:
        return None

    try:
        response = requests.get(
            f"{BASE_URL}/games/{game_id}", 
            params={'key': RAWG_API_KEY},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching details for RAWG game {game_id}: {e}")
        return None

def fetch_rawg_screenshots(game_id, limit=10):
    """
    Fetch screenshots from RAWG.
    """
    if not RAWG_API_KEY:
        return []

    try:
        params = {
            'key': RAWG_API_KEY,
            'page_size': limit
        }
        response = requests.get(
            f"{BASE_URL}/games/{game_id}/screenshots", 
            params=params,
            timeout=10
        )
        response.raise_for_status()
        results = response.json().get('results', [])
        logger.info(f"Fetched {len(results)} screenshots for RAWG game {game_id}")
        return results
    except requests.RequestException as e:
        logger.error(f"Error fetching screenshots for RAWG game {game_id}: {e}")
        return []

def fetch_rawg_trailers(game_id):
    """
    Fetch trailers/movies from RAWG.
    """
    if not RAWG_API_KEY:
        return []

    try:
        response = requests.get(
            f"{BASE_URL}/games/{game_id}/movies", 
            params={'key': RAWG_API_KEY},
            timeout=10
        )
        response.raise_for_status()
        results = response.json().get('results', [])
        logger.info(f"Fetched {len(results)} trailers for RAWG game {game_id}")
        return results
    except requests.RequestException as e:
        logger.error(f"Error fetching trailers for RAWG game {game_id}: {e}")
        return []

def update_game_with_rawg(game, force_refresh=False):
    """
    Update a Game instance with enriched data from RAWG API.
    
    Args:
        game: Game instance to update
        force_refresh: If True, fetch data even if already exists
    
    Returns:
        bool: True if successfully updated, False otherwise
    """
    if not RAWG_API_KEY:
        logger.warning("Cannot update game - RAWG_API_KEY not configured")
        return False
    
    # Check if update is needed
    if not force_refresh and game.rawg_id and game.description and game.background_image:
        logger.debug(f"Game '{game.title}' already has RAWG data, skipping.")
        return True
    
    # Get or find RAWG ID
    if game.rawg_id:
        rawg_id = game.rawg_id
        logger.info(f"Using existing RAWG ID {rawg_id} for '{game.title}'")
    else:
        rawg_id = get_rawg_game_id(game.title, steam_appid=game.steam_appid)
        if not rawg_id:
            logger.warning(f"Could not find RAWG ID for '{game.title}'")
            return False
        game.rawg_id = rawg_id
        game.save(update_fields=['rawg_id'])
        logger.info(f"Saved RAWG ID {rawg_id} for '{game.title}'")

    # Fetch and update game details
    details = fetch_rawg_game_details(rawg_id)
    if details:
        # Update description (prefer raw text over HTML)
        description = details.get('description_raw', '') or details.get('description', '')
        if description:
            game.description = description
        
        # Update background image (high quality poster)
        background_image = details.get('background_image', '')
        if background_image:
            game.background_image = background_image
        
        # Update metacritic score
        metacritic_score = details.get('metacritic')
        if metacritic_score:
            game.metacritic_score = metacritic_score
        
        # Update genre if still default/empty
        if game.genre in ['Unknown', '게임', ''] and details.get('genres'):
            genres = [g['name'] for g in details['genres'][:3]]  # Top 3 genres
            game.genre = ', '.join(genres)
        
        game.save()
        logger.info(f"Updated game details for '{game.title}'")
    else:
        logger.warning(f"Could not fetch details for RAWG game {rawg_id}")
        return False

    # Fetch and save screenshots (avoid duplicates)
    screenshots = fetch_rawg_screenshots(rawg_id, limit=10)
    screenshot_count = 0
    for ss in screenshots:
        _, created = GameScreenshot.objects.get_or_create(
            game=game,
            image_url=ss['image']
        )
        if created:
            screenshot_count += 1
    
    if screenshot_count > 0:
        logger.info(f"Added {screenshot_count} new screenshots for '{game.title}'")

    # Fetch and save trailers (avoid duplicates)
    trailers = fetch_rawg_trailers(rawg_id)
    trailer_count = 0
    for tr in trailers:
        # Check if trailer data has required fields
        if 'data' not in tr or '480' not in tr['data'] or 'max' not in tr['data']:
            logger.warning(f"Skipping trailer '{tr.get('name', 'Unknown')}' - missing video data")
            continue
            
        _, created = GameTrailer.objects.get_or_create(
            game=game,
            name=tr['name'],
            defaults={
                'preview_url': tr.get('preview', ''),
                'data_480': tr['data']['480'],
                'data_max': tr['data']['max']
            }
        )
        if created:
            trailer_count += 1
    
    if trailer_count > 0:
        logger.info(f"Added {trailer_count} new trailers for '{game.title}'")

    logger.info(f"Successfully updated RAWG data for '{game.title}'")
    return True


# ============================================================================
# B. 게임 검색 및 매핑
# ============================================================================

def search_games(query, platforms='4', page_size=20):
    """
    Search for games on RAWG by title.
    
    Args:
        query: Game title to search for
        platforms: Platform ID (4 = PC, default)
        page_size: Number of results to return (default: 20)
    
    Returns:
        list: List of game dictionaries with basic info
    """
    if not RAWG_API_KEY:
        logger.warning("RAWG_API_KEY not configured")
        return []
    
    try:
        params = {
            'key': RAWG_API_KEY,
            'search': query,
            'platforms': platforms,
            'page_size': page_size
        }
        response = requests.get(f"{BASE_URL}/games", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for game in data.get('results', []):
            results.append({
                'rawg_id': game['id'],
                'title': game['name'],
                'image_url': game.get('background_image', ''),
                'rating': game.get('rating'),
                'released': game.get('released'),
                'genres': [g['name'] for g in game.get('genres', [])],
                'metacritic': game.get('metacritic')
            })
        
        logger.info(f"Found {len(results)} games for query '{query}'")
        return results
    
    except requests.RequestException as e:
        logger.error(f"Error searching games for '{query}': {e}")
        return []


# ============================================================================
# C. 분류 및 태그 (UI 필터용)
# ============================================================================

def get_genres(page_size=50):
    """
    Get list of all game genres from RAWG.
    
    Returns:
        list: List of genre dictionaries with id, name, slug, and image
    """
    if not RAWG_API_KEY:
        logger.warning("RAWG_API_KEY not configured")
        return []
    
    try:
        params = {
            'key': RAWG_API_KEY,
            'page_size': page_size
        }
        response = requests.get(f"{BASE_URL}/genres", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        genres = []
        for genre in data.get('results', []):
            genres.append({
                'id': genre['id'],
                'name': genre['name'],
                'slug': genre['slug'],
                'games_count': genre.get('games_count', 0),
                'image_background': genre.get('image_background', '')
            })
        
        logger.info(f"Fetched {len(genres)} genres from RAWG")
        return genres
    
    except requests.RequestException as e:
        logger.error(f"Error fetching genres: {e}")
        return []


def get_platforms(page_size=50):
    """
    Get list of all gaming platforms from RAWG.
    
    Returns:
        list: List of platform dictionaries with id, name, and slug
    """
    if not RAWG_API_KEY:
        logger.warning("RAWG_API_KEY not configured")
        return []
    
    try:
        params = {
            'key': RAWG_API_KEY,
            'page_size': page_size
        }
        response = requests.get(f"{BASE_URL}/platforms", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        platforms = []
        for platform in data.get('results', []):
            platforms.append({
                'id': platform['id'],
                'name': platform['name'],
                'slug': platform['slug'],
                'games_count': platform.get('games_count', 0),
                'image_background': platform.get('image_background', '')
            })
        
        logger.info(f"Fetched {len(platforms)} platforms from RAWG")
        return platforms
    
    except requests.RequestException as e:
        logger.error(f"Error fetching platforms: {e}")
        return []


def get_games_by_genre(genre_slug, page_size=20):
    """
    Get games filtered by genre.
    
    Args:
        genre_slug: Genre slug (e.g., 'action', 'rpg', 'strategy')
        page_size: Number of results to return
    
    Returns:
        list: List of games in that genre
    """
    if not RAWG_API_KEY:
        logger.warning("RAWG_API_KEY not configured")
        return []
    
    try:
        params = {
            'key': RAWG_API_KEY,
            'genres': genre_slug,
            'page_size': page_size,
            'platforms': '4'  # PC only
        }
        response = requests.get(f"{BASE_URL}/games", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for game in data.get('results', []):
            results.append({
                'rawg_id': game['id'],
                'title': game['name'],
                'image_url': game.get('background_image', ''),
                'rating': game.get('rating'),
                'genres': [g['name'] for g in game.get('genres', [])],
                'metacritic': game.get('metacritic')
            })
        
        logger.info(f"Found {len(results)} games for genre '{genre_slug}'")
        return results
    
    except requests.RequestException as e:
        logger.error(f"Error fetching games by genre '{genre_slug}': {e}")
        return []


# ============================================================================
# D. 인기순/정렬 기능 ('요즘 뜨는 게임' 섹션용)
# ============================================================================

def get_games_by_ordering(ordering='-added', page_size=20, platforms='4'):
    """
    Get games sorted by various criteria.
    
    Args:
        ordering: Sorting option (default: '-added' for most popular)
            Available options:
            - '-added': Most added to libraries (인기순)
            - '-rating': Highest rated (평점 높은 순)
            - '-metacritic': Highest metacritic score (메타크리틱 높은 순)
            - '-released': Recently released (최신 출시순)
            - 'name': Alphabetical order (가나다순)
            - '-created': Recently created (최근 생성순)
            - '-updated': Recently updated (최근 업데이트순)
        page_size: Number of results to return
        platforms: Platform ID (4 = PC, default)
    
    Returns:
        list: List of games sorted by the specified criteria
    """
    if not RAWG_API_KEY:
        logger.warning("RAWG_API_KEY not configured")
        return []
    
    try:
        params = {
            'key': RAWG_API_KEY,
            'ordering': ordering,
            'page_size': page_size,
            'platforms': platforms
        }
        response = requests.get(f"{BASE_URL}/games", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for game in data.get('results', []):
            results.append({
                'rawg_id': game['id'],
                'slug': game.get('slug', ''),
                'title': game['name'],
                'image_url': game.get('background_image', ''),
                'rating': game.get('rating'),
                'released': game.get('released'),
                'genres': [g['name'] for g in game.get('genres', [])],
                'metacritic': game.get('metacritic'),
                'added': game.get('added', 0)  # Number of users who added this
            })
        
        logger.info(f"Fetched {len(results)} games with ordering '{ordering}'")
        return results
    
    except requests.RequestException as e:
        logger.error(f"Error fetching games with ordering '{ordering}': {e}")
        return []


def get_popular_games(page_size=20):
    """
    Get most popular games (most added to user libraries).
    Perfect for '요즘 뜨는 게임' section.
    
    Args:
        page_size: Number of results (default: 20)
    
    Returns:
        list: Most popular games
    """
    return get_games_by_ordering(ordering='-added', page_size=page_size)


def get_top_rated_games(page_size=20):
    """
    Get highest rated games.
    
    Args:
        page_size: Number of results (default: 20)
    
    Returns:
        list: Top rated games
    """
    return get_games_by_ordering(ordering='-rating', page_size=page_size)


def get_trending_games(page_size=20):
    """
    Get games with highest metacritic scores.
    
    Args:
        page_size: Number of results (default: 20)
    
    Returns:
        list: Games sorted by metacritic score
    """
    return get_games_by_ordering(ordering='-metacritic', page_size=page_size)


def get_new_releases(page_size=20):
    """
    Get recently released games.
    
    Args:
        page_size: Number of results (default: 20)
    
    Returns:
        list: Recently released games
    """
    return get_games_by_ordering(ordering='-released', page_size=page_size)


def get_upcoming_games(page_size=20):
    """
    Get upcoming games (to be released).
    
    Args:
        page_size: Number of results (default: 20)
    
    Returns:
        list: Upcoming games
    """
    if not RAWG_API_KEY:
        logger.warning("RAWG_API_KEY not configured")
        return []
    
    try:
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        
        params = {
            'key': RAWG_API_KEY,
            'dates': f'{today},2026-12-31',  # From today to future
            'ordering': 'released',  # Soonest first
            'page_size': page_size,
            'platforms': '4'  # PC only
        }
        response = requests.get(f"{BASE_URL}/games", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for game in data.get('results', []):
            results.append({
                'rawg_id': game['id'],
                'title': game['name'],
                'image_url': game.get('background_image', ''),
                'rating': game.get('rating'),
                'released': game.get('released'),
                'genres': [g['name'] for g in game.get('genres', [])],
                'metacritic': game.get('metacritic')
            })
        
        logger.info(f"Fetched {len(results)} upcoming games")
        return results
    
    except requests.RequestException as e:
        logger.error(f"Error fetching upcoming games: {e}")
        return []
