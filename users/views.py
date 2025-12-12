from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
import json
import os
from django.conf import settings

from .forms import SignupForm, CustomLoginForm
from .models import User
from .steam_auth import (
    get_steam_login_url,
    validate_steam_login,
    get_steam_user_info,
    get_steam_owned_games,
    get_steam_recently_played,
    get_game_recommendations_from_library
)
# Game 모델이 users/models.py에 정의되어 있다고 가정합니다.
# 만약 games/models.py에 있다면 'from games.models import Game'으로 변경하세요.
from games.models import Game

# --- 1. 회원가입 (Create) ---
@require_http_methods(["GET", "POST"])
def signup_view(request):
    # 이미 로그인한 사용자는 메인으로 리다이렉트
    if request.user.is_authenticated:
        return redirect('home') # 'home'은 프로젝트 urls.py에서 설정한 메인 페이지 이름

    if request.method == 'POST':
        form = SignupForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user) # 가입 후 자동 로그인
            return redirect('home')
    else:
        form = SignupForm()

    return render(request, 'users/signup.html', {'form': form})

# --- 2. 로그인 (Read/Auth) ---
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = CustomLoginForm()

    return render(request, 'users/login.html', {'form': form})

# --- 3. 로그아웃 ---
def logout_view(request):
    logout(request)
    return redirect('users:login')

# --- 4. 마이페이지 (Read - Detail) ---
@login_required(login_url='users:login')
def profile_view(request):
    return render(request, 'users/profile.html', {
        'user': request.user
    })

# --- 5. 회원 탈퇴 (Delete) ---
@login_required
@require_http_methods(["POST"])
def delete_account_view(request):
    if request.method == 'POST':
        request.user.delete()
        logout(request)
        return redirect('users:login')

# --- 6. 메인 페이지 (Main View) ---
@login_required(login_url='users:login')
def main_view(request):
    # JSON 파일에서 게임 데이터 가져오기
    games_data = []
    best_prices = []
    
    try:
        # Try new format first
        new_json_path = os.path.join(settings.BASE_DIR, 'users', 'steam_sale_data.json')
        legacy_json_path = os.path.join(settings.BASE_DIR, 'users', 'steam_sale_dataset_fast.json')
        
        if os.path.exists(new_json_path):
            with open(new_json_path, 'r', encoding='utf-8') as f:
                sale_data = json.load(f)
                games_data = sale_data.get('current_sales', [])
                # Try historical_lows first, fall back to best_prices
                best_prices = sale_data.get('historical_lows', sale_data.get('best_prices', []))[:30]  # Top 30 best prices
        elif os.path.exists(legacy_json_path):
            with open(legacy_json_path, 'r', encoding='utf-8') as f:
                games_data = json.load(f)
        else:
            print(f"파일을 찾을 수 없습니다: {new_json_path}")

        games_json = json.dumps(games_data, cls=DjangoJSONEncoder)
        best_prices_json = json.dumps(best_prices, cls=DjangoJSONEncoder)

    except Exception as e:
        print(f"게임 데이터를 불러오는 중 오류 발생: {e}")
        games_json = "[]"
        best_prices_json = "[]"

    # Wishlist IDs
    wishlist_ids = list(request.user.wishlist.values_list('steam_appid', flat=True))
    wishlist_json = json.dumps(wishlist_ids, cls=DjangoJSONEncoder)

    return render(request, 'users/index.html', {
        'user': request.user,
        'games_json': games_json,
        'best_prices_json': best_prices_json,
        'wishlist_json': wishlist_json,
    })


# =============================================================================
# Steam OAuth Login Views
# =============================================================================

def steam_login(request):
    """
    Initiate Steam OpenID login
    Redirects user to Steam login page
    """
    # Build callback URL
    callback_url = request.build_absolute_uri('/users/steam/callback/')
    steam_url = get_steam_login_url(callback_url)
    
    # Store next URL if provided
    next_url = request.GET.get('next', '/')
    request.session['steam_login_next'] = next_url
    
    # Store if this is a link request (user already logged in)
    if request.user.is_authenticated:
        request.session['steam_link_mode'] = True
    else:
        request.session['steam_link_mode'] = False
    
    return redirect(steam_url)


def steam_callback(request):
    """
    Handle Steam OpenID callback
    Creates or logs in user based on Steam ID
    """
    # Validate Steam login
    steam_id = validate_steam_login(request.GET)
    
    if not steam_id:
        messages.error(request, 'Steam 로그인에 실패했습니다. 다시 시도해주세요.')
        return redirect('users:login')
    
    # Get Steam user info
    steam_info = get_steam_user_info(steam_id)
    
    # Check if this is a link request (user already logged in)
    is_link_mode = request.session.pop('steam_link_mode', False)
    next_url = request.session.pop('steam_login_next', '/')
    
    if is_link_mode and request.user.is_authenticated:
        # Link Steam account to existing user
        user = request.user
        
        # Check if Steam ID is already linked to another account
        existing_user = User.objects.filter(steam_id=steam_id).exclude(pk=user.pk).first()
        if existing_user:
            messages.error(request, '이 Steam 계정은 이미 다른 계정에 연동되어 있습니다.')
            return redirect(next_url)
        
        # Link Steam account
        user.steam_id = steam_id
        user.is_steam_linked = True
        if steam_info:
            # Optionally update avatar from Steam
            # user.avatar_url = steam_info.get('avatarfull', '')
            pass
        user.save()
        
        messages.success(request, f"Steam 계정 '{steam_info.get('personaname', steam_id)}'이(가) 연동되었습니다!")
        return redirect(next_url)
    
    else:
        # Login or register new user with Steam
        
        # Check if Steam ID already exists
        try:
            user = User.objects.get(steam_id=steam_id)
            # User exists, log them in
            login(request, user)
            messages.success(request, f"Steam으로 로그인되었습니다. 환영합니다, {user.nickname or user.username}님!")
            return redirect(next_url)
        
        except User.DoesNotExist:
            # Create new user with Steam account
            if steam_info:
                persona_name = steam_info.get('personaname', f'Steam_{steam_id[-6:]}')
                
                # Generate unique username
                base_username = f"steam_{steam_id[-8:]}"
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}_{counter}"
                    counter += 1
                
                # Create user
                user = User.objects.create_user(
                    username=username,
                    nickname=persona_name,
                    steam_id=steam_id,
                    is_steam_linked=True,
                )
                # Set unusable password since they'll login via Steam
                user.set_unusable_password()
                user.save()
                
                login(request, user)
                messages.success(request, f"Steam 계정으로 가입이 완료되었습니다! 환영합니다, {persona_name}님!")
                return redirect(next_url)
            else:
                messages.error(request, 'Steam 사용자 정보를 가져올 수 없습니다.')
                return redirect('users:login')


@login_required
def steam_unlink(request):
    """
    Unlink Steam account from user profile
    """
    if request.method == 'POST':
        user = request.user
        
        # Check if user has a password (can still login without Steam)
        if user.has_usable_password():
            user.steam_id = None
            user.is_steam_linked = False
            user.save()
            messages.success(request, 'Steam 계정 연동이 해제되었습니다.')
        else:
            messages.error(request, 'Steam으로만 가입한 계정입니다. 비밀번호를 설정한 후 연동 해제할 수 있습니다.')
        
        return redirect('home')
    
    return redirect('home')


@login_required
def steam_library_api(request):
    """
    API endpoint to fetch user's Steam library - WITH DB CACHING
    
    Flow:
    1. Check DB cache first (instant: 0.01s)
    2. If cache exists and fresh (< 24h) → return cached data
    3. If cache missing or stale → fetch from Steam API → update cache
    
    Query params:
        force_refresh: If 'true', always fetch fresh data from Steam
    """
    from .models import SteamLibraryCache
    
    user = request.user
    
    if not user.is_steam_linked or not user.steam_id:
        return JsonResponse({
            'error': 'Steam 계정이 연동되지 않았습니다.',
            'is_linked': False
        }, status=400)
    
    force_refresh = request.GET.get('force_refresh', 'false').lower() == 'true'
    
    # Step 1: Check DB cache
    try:
        cache = SteamLibraryCache.objects.get(user=user)
        cache_exists = True
        cache_is_fresh = not cache.is_stale(hours=24)
    except SteamLibraryCache.DoesNotExist:
        cache = None
        cache_exists = False
        cache_is_fresh = False
    
    # Step 2: Return cached data if fresh and not forcing refresh
    if cache_exists and cache_is_fresh and not force_refresh:
        print(f"[CACHE HIT] Returning cached library for {user.username}")
        return JsonResponse({
            'is_linked': True,
            'steam_id': user.steam_id,
            'library': cache.library_data,
            'total_games': cache.total_games,
            'total_playtime_hours': cache.total_playtime_hours,
            'cached': True,
            'cache_age_hours': round((timezone.now() - cache.last_updated).total_seconds() / 3600, 1)
        })
    
    # Step 3: Fetch from Steam API
    print(f"[CACHE MISS] Fetching fresh library from Steam for {user.username}")
    library_data = get_game_recommendations_from_library(user.steam_id)
    
    # Step 4: Update cache
    library_list = library_data.get('library', [])
    total_games = library_data.get('total_games', 0)
    total_hours = library_data.get('total_playtime_hours', 0)
    
    if cache_exists:
        cache.library_data = library_list
        cache.total_games = total_games
        cache.total_playtime_hours = total_hours
        cache.save()
    else:
        SteamLibraryCache.objects.create(
            user=user,
            library_data=library_list,
            total_games=total_games,
            total_playtime_hours=total_hours
        )
    
    print(f"[CACHE UPDATED] Saved {total_games} games to cache for {user.username}")
    
    return JsonResponse({
        'is_linked': True,
        'steam_id': user.steam_id,
        'library': library_list,
        'total_games': total_games,
        'total_playtime_hours': total_hours,
        'cached': False
    })


@login_required
def steam_recently_played_api(request):
    """
    API endpoint to fetch user's recently played games
    """
    user = request.user
    
    if not user.is_steam_linked or not user.steam_id:
        return JsonResponse({
            'error': 'Steam 계정이 연동되지 않았습니다.',
            'is_linked': False
        }, status=400)
    
    recently_played = get_steam_recently_played(user.steam_id, count=20)
    
    return JsonResponse({
        'is_linked': True,
        'recently_played': recently_played
    })


@login_required
def personalized_recommendations_api(request):
    """
    API endpoint for personalized game recommendations
    
    추천 소스:
    1. Steam 연동 사용자 → Steam 라이브러리 기반 추천
    2. 온보딩 완료 사용자 → DB 평가 데이터 기반 추천 (Item-Based CF)
    3. 둘 다 없음 → 온보딩 필요 안내
    """
    from .recommendation import get_personalized_recommendations, RAWG_API_KEY
    from .steam_auth import get_steam_owned_games
    from .onboarding import get_recommendations_for_user
    from .models import GameRating, OnboardingStatus
    
    user = request.user
    
    print(f"[DEBUG] personalized_recommendations_api called")
    print(f"[DEBUG] User: {user.email}, Steam linked: {user.is_steam_linked}")
    
    # 방법 1: Steam 연동 사용자 → 기존 로직
    if user.is_steam_linked and user.steam_id:
        print(f"[DEBUG] Using Steam library for recommendations")
        
        steam_library = get_steam_owned_games(user.steam_id)
        
        if steam_library:
            # Get sale games
            try:
                json_file_path = os.path.join(settings.BASE_DIR, 'users', 'steam_sale_dataset_fast.json')
                if os.path.exists(json_file_path):
                    with open(json_file_path, 'r', encoding='utf-8') as f:
                        sale_games = json.load(f)
                else:
                    sale_games = []
            except Exception as e:
                sale_games = []
            
            result = get_personalized_recommendations(
                steam_library=steam_library,
                sale_games=sale_games,
                limit=250
            )
            return JsonResponse(result)
    
    # 방법 2: 온보딩 완료 사용자 → DB 평가 데이터 기반 추천
    rating_count = GameRating.objects.filter(user=user, score__gt=0).count()
    
    if rating_count >= 3:  # 최소 3개 이상 평가해야 추천 가능
        print(f"[DEBUG] Using onboarding ratings for recommendations ({rating_count} ratings)")
        
        result = get_recommendations_for_user(user, limit=50)
        
        if not result.get('needs_onboarding') and result.get('recommendations'):
            return JsonResponse({
                'is_personalized': True,
                'recommendations': result['recommendations'],
                'message': f'평가 데이터({rating_count}개) 기반 추천입니다.',
                'genres_analysis': None,
                'method': result.get('method', 'onboarding_based')
            })
    
    # 방법 3: 둘 다 없음 → 온보딩 필요
    print(f"[DEBUG] No recommendation source available, needs onboarding")
    
    # 온보딩 상태 확인
    try:
        onboarding = OnboardingStatus.objects.get(user=user)
        onboarding_status = onboarding.status
    except OnboardingStatus.DoesNotExist:
        onboarding_status = 'not_started'
    
    if onboarding_status in ['completed', 'skipped'] and rating_count > 0:
        message = f'평가 데이터가 부족합니다. (현재 {rating_count}개, 최소 3개 필요)'
    else:
        message = '게임 취향 분석을 위해 온보딩을 완료해주세요. 또는 Steam을 연동하세요.'
    
    return JsonResponse({
        'is_personalized': False,
        'recommendations': [],
        'message': message,
        'genres_analysis': None,
        'needs_onboarding': onboarding_status not in ['completed', 'skipped'],
        'rating_count': rating_count
    })


# =============================================================================
# AI Game Recommendation Chatbot (GPT-5 Nano)
# =============================================================================

import requests
from django.views.decorators.csrf import csrf_exempt

@login_required
@require_http_methods(["POST"])
def ai_chat_api(request):
    """
    AI Game Recommendation Chatbot API
    Uses GPT-5 Nano via GMS API for personalized game recommendations
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get API key from environment
    api_key = os.getenv('GMS_API_KEY')
    
    if not api_key:
        return JsonResponse({
            'error': 'API 키가 설정되지 않았습니다.',
            'success': False
        }, status=500)
    
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        chat_history = data.get('history', [])
        
        if not user_message:
            return JsonResponse({
                'error': '메시지를 입력해주세요.',
                'success': False
            }, status=400)
        
        # Get user's Steam library info for context
        user = request.user
        steam_context = ""
        onboarding_context = ""
        is_steam_linked = user.is_steam_linked and user.steam_id
        user_nickname = user.nickname or user.username or "게이머"
        
        # Games to exclude from recommendations (user's library + rated games)
        owned_games_list = []
        rated_games_list = []
        low_playtime_games = []  # Games with < 2 hours playtime
        
        # ========================================
        # 1. 온보딩 평가 데이터 수집 (모든 사용자 공통)
        # ========================================
        from .models import GameRating
        
        user_ratings = GameRating.objects.filter(
            user=user
        ).select_related('game').order_by('-score', '-created_at')
        
        if user_ratings.exists():
            # 좋아하는 게임 (점수 3.5 이상)
            liked_games = []
            # 싫어하는 게임 (점수 0 이하)
            disliked_games = []
            # 모든 평가한 게임 (추천 제외용)
            all_rated = []
            
            for rating in user_ratings:
                game = rating.game
                game_name = game.title
                genre = game.genre if game.genre and game.genre != 'Unknown' else ''
                score = rating.score
                
                all_rated.append(game_name)
                
                if score >= 3.5:
                    if genre:
                        liked_games.append(f"- {game_name} ({genre}) - ⭐{score}")
                    else:
                        liked_games.append(f"- {game_name} - ⭐{score}")
                elif score <= 0:
                    disliked_games.append(f"- {game_name}")
            
            rated_games_list = all_rated
            
            # 장르 분석
            genre_counts = {}
            for rating in user_ratings.filter(score__gte=3.5):
                if rating.game.genre and rating.game.genre != 'Unknown':
                    for genre in rating.game.genre.split(', '):
                        genre = genre.strip()
                        if genre:
                            genre_counts[genre] = genre_counts.get(genre, 0) + 1
            
            # 가장 선호하는 장르 추출
            top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            favorite_genres = [g[0] for g in top_genres] if top_genres else []
            
            onboarding_context = f"""

[유저 게임 평가 데이터 - {user_nickname}님의 취향 분석]
📊 총 평가한 게임: {user_ratings.count()}개

❤️ 좋아하는 게임 (높은 평점):
{chr(10).join(liked_games[:10]) if liked_games else '- 아직 없음'}

🎯 선호 장르: {', '.join(favorite_genres) if favorite_genres else '분석 중...'}

👎 싫어하는/안 맞는 게임:
{chr(10).join(disliked_games[:5]) if disliked_games else '- 없음'}

⚠️ 이미 평가한 게임 (추천에서 제외):
{', '.join(all_rated[:15])}{'...(총 ' + str(len(all_rated)) + '개)' if len(all_rated) > 15 else ''}"""
            
            print(f"[DEBUG] Onboarding context added: {user_ratings.count()} rated games, favorite genres: {favorite_genres}")
        
        # ========================================
        # 2. Steam 라이브러리 데이터 수집 (연동된 경우)
        # ========================================
        if is_steam_linked:
            try:
                steam_library = get_steam_owned_games(user.steam_id)
                if steam_library:
                    # Get top played games with playtime
                    sorted_games = sorted(steam_library, key=lambda x: x.get('playtime_forever', 0), reverse=True)
                    
                    # All owned game names for exclusion
                    owned_games_list = [g.get('name', '') for g in steam_library if g.get('name')]
                    
                    # Format top played games with playtime info
                    game_list = []
                    for g in sorted_games[:7]:
                        name = g.get('name', '')
                        playtime_hours = round(g.get('playtime_forever', 0) / 60, 1)
                        if name and playtime_hours > 0:
                            game_list.append(f"- {name} ({playtime_hours}시간)")
                    
                    # Find games with low playtime (< 2 hours) - potential recommendations
                    for g in steam_library:
                        name = g.get('name', '')
                        playtime_hours = round(g.get('playtime_forever', 0) / 60, 1)
                        if name and 0 < playtime_hours < 2:
                            low_playtime_games.append(f"{name} ({playtime_hours}시간)")
                    
                    # Get recently played games
                    recently_played = get_steam_recently_played(user.steam_id, count=5)
                    recent_list = [g.get('name', '') for g in recently_played if g.get('name')] if recently_played else []
                    
                    # Calculate total stats
                    total_games = len(steam_library)
                    total_hours = round(sum(g.get('playtime_forever', 0) for g in steam_library) / 60, 1)
                    
                    steam_context = f"""

[유저 Steam 라이브러리 분석 - {user_nickname}님의 플레이 기록]
📊 총 보유 게임: {total_games}개 | 총 플레이 시간: {total_hours}시간

🎮 가장 많이 플레이한 게임 (취향 분석용):
{chr(10).join(game_list) if game_list else '- 정보 없음'}

🕹️ 최근 플레이한 게임: {', '.join(recent_list[:5]) if recent_list else '정보 없음'}

⏳ 플레이 시간이 짧은 보유 게임 (숨겨진 명작일 수 있음):
{', '.join(low_playtime_games[:5]) if low_playtime_games else '없음'}

⚠️ 보유 중인 게임 (추천에서 제외, 일부만 표시):
{', '.join(owned_games_list[:20])}{'...(총 ' + str(len(owned_games_list)) + '개)' if len(owned_games_list) > 20 else ''}"""
                    
                    print(f"[DEBUG] Steam context added: {len(steam_library)} games, {total_hours} hours, {len(low_playtime_games)} low-playtime games")
            except Exception as e:
                print(f"Steam library fetch error: {e}")
        
        # 전체 제외 게임 목록 합치기 (중복 제거)
        all_excluded_games = list(set(owned_games_list + rated_games_list))
        
        # Build the system prompt (developer role in GPT-5)
        system_prompt = f"""당신은 '게임 큐레이터 AI'입니다. 게임 추천 전문가로서 다음 역할을 수행합니다:

🎮 **전문 분야**
- 모든 플랫폼(PC, 콘솔, 모바일)의 게임에 대한 깊은 지식
- 장르별 특성과 대표 게임들을 잘 알고 있음
- 최신 인기 게임과 숨겨진 명작까지 폭넓게 추천 가능
- Steam, Epic Games, PlayStation, Xbox, Nintendo 등 모든 플랫폼 게임 추천

📊 **추천 스타일**
- 유저의 취향과 플레이 스타일을 파악하여 맞춤 추천
- 게임의 장점, 특징, 플레이 시간, 난이도 등을 설명
- 이모지를 활용하여 친근하고 재미있게 대화

🚫 **중요: 추천 규칙**
1. 유저가 이미 평가하거나 보유한 게임은 새 게임 추천에서 **반드시 제외**합니다
2. 추천할 때 반드시 유저가 플레이/평가한 게임과 비교하며 설명해주세요:
   - "'{user_nickname}님이 좋아하신 OO 게임처럼 △△한 요소가 있어서..."
   - "OO 게임과 장르가 비슷하고, 스토리 전개 방식도 닮아있어요"
   - "OO를 즐기셨다면 이 게임의 ◇◇ 시스템도 마음에 드실 거예요"
3. 유저의 선호 장르와 좋아하는 게임의 공통점을 분석해서 추천 이유를 구체적으로 설명해주세요
4. 유저가 싫어한 게임과 비슷한 장르/스타일은 피해주세요 (있다면)
5. 보유했지만 플레이타임이 짧은 게임이 있다면 마지막에 "💡 참고로, 이미 가지고 계신 'OO'도 한번 플레이해보세요! 숨겨진 명작일 수 있어요" 추가

💡 **응답 규칙**
- 항상 한국어로 답변
- 게임 이름은 정확하게 표기 (원제 + 한글명 병기 권장)
- 1-5개 정도의 게임을 추천할 때는 번호 리스트로 정리
- 각 게임마다 장르, 특징, **왜 유저 취향에 맞는지** 구체적으로 설명
- 마지막에 추가 질문을 유도하는 문구 추가
{onboarding_context}
{steam_context}

사용자가 게임 외의 질문을 하면, 친절하게 게임 추천 관련 질문으로 유도해주세요."""

        # Build messages for API
        messages = [
            {
                "role": "developer",
                "content": system_prompt
            }
        ]
        
        # Add chat history (limit to last 10 messages)
        for msg in chat_history[-10:]:
            messages.append({
                "role": msg.get('role', 'user'),
                "content": msg.get('content', '')
            })
        
        # Add current user message
        messages.append({
            "role": "user", 
            "content": user_message
        })
        
        # Call GPT-5 Nano API
        response = requests.post(
            "https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "model": "gpt-5-nano",
                "messages": messages,
                "max_completion_tokens": 16000
            },
            timeout=120  # 2분 타임아웃 (reasoning model은 시간이 더 필요)
        )
        
        print(f"[DEBUG] GPT Response Status: {response.status_code}")
        print(f"[DEBUG] GPT Response Body: {response.text[:500]}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"[DEBUG] Parsed Result: {result}")
            
            # Handle different response structures
            choices = result.get('choices', [])
            if choices and len(choices) > 0:
                message_obj = choices[0].get('message', {})
                ai_message = message_obj.get('content', '')
            else:
                ai_message = ''
            
            print(f"[DEBUG] AI Message: {ai_message[:200] if ai_message else 'EMPTY'}")
            
            if ai_message:
                return JsonResponse({
                    'success': True,
                    'message': ai_message,
                    'role': 'assistant'
                })
            else:
                return JsonResponse({
                    'error': 'AI 응답을 받지 못했습니다.',
                    'success': False,
                    'debug': str(result)[:500]
                }, status=500)
        else:
            print(f"GPT API Error: {response.status_code} - {response.text}")
            return JsonResponse({
                'error': f'AI 서버 오류가 발생했습니다. (Status: {response.status_code})',
                'success': False
            }, status=response.status_code)
            
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        return JsonResponse({
            'error': '잘못된 요청 형식입니다.',
            'success': False
        }, status=400)
    except requests.Timeout:
        return JsonResponse({
            'error': 'AI 서버 응답 시간이 초과되었습니다. 다시 시도해주세요.',
            'success': False
        }, status=504)
    except Exception as e:
        import traceback
        print(f"AI Chat Error: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': f'서버 오류가 발생했습니다: {str(e)}',
            'success': False
        }, status=500)


@login_required
@require_http_methods(["POST"])
def translate_text_api(request):
    """
    Translate game description to Korean using Gemini 2.0 Flash Lite
    Much faster than GPT!
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get API key from environment
    api_key = os.getenv('GMS_API_KEY')
    
    if not api_key:
        return JsonResponse({
            'error': 'API 키가 설정되지 않았습니다.',
            'success': False
        }, status=500)
    
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        
        if not text:
            return JsonResponse({
                'error': '번역할 텍스트가 없습니다.',
                'success': False
            }, status=400)
        
        # Limit text length to prevent abuse
        if len(text) > 5000:
            text = text[:5000]
        
        # Build translation prompt for Gemini - Professional Game Translator Persona
        prompt = f"""당신은 10년 경력의 전문 게임 로컬라이제이션 번역가입니다. 
수많은 AAA 타이틀과 인디 게임의 한국어화 작업을 담당해온 베테랑으로, 게임 문화와 한국 게이머들의 언어 습관을 깊이 이해하고 있습니다.

🎮 **번역 전문 분야:**
- RPG, 액션, 어드벤처, 호러, 시뮬레이션 등 모든 장르
- 스팀, 플레이스테이션, Xbox, 닌텐도 등 모든 플랫폼
- 게임 스토리, UI 텍스트, 마케팅 문구

📜 **번역 원칙:**
1. **고유명사 보존**: 게임 타이틀, 캐릭터명, 지명, 아이템명 등은 원어 그대로 유지
   - 예: "Geralt of Rivia" → "리비아의 게랄트" (유명한 경우 한글화된 이름 사용)
   - 예: "Dark Souls" → "Dark Souls" (게임 타이틀은 그대로)

2. **게임 용어 현지화**: 한국 게이머들에게 익숙한 표현 사용
   - 예: "roguelike" → "로그라이크", "dungeon crawler" → "던전 크롤러"
   - 예: "open world" → "오픈 월드", "sandbox" → "샌드박스"

3. **자연스러운 한국어**: 번역투가 아닌 자연스러운 문장
   - 직역 금지, 의역을 통해 매끄러운 한국어로 표현
   - 한국어 어순과 표현에 맞게 재구성

4. **마케팅 톤 유지**: 원문의 흥미와 기대감을 살려서 번역
   - 게임의 분위기와 장르에 맞는 어조 사용
   - 호러는 긴장감 있게, 어드벤처는 설렘 있게

5. **출력 규칙**: 오직 번역된 텍스트만 출력. 설명, 주석, "번역:" 같은 라벨 없이 깔끔하게.

---
영어 원문:
{text}

한국어 번역:"""
        
        # Call Gemini 2.0 Flash Lite API (much faster!)
        response = requests.post(
            f"https://gms.ssafy.io/gmsapi/generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={api_key}",
            headers={
                "Content-Type": "application/json"
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
            },
            timeout=30  # Gemini is much faster
        )
        
        print(f"[DEBUG] Gemini Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Parse Gemini response format
            candidates = result.get('candidates', [])
            if candidates and len(candidates) > 0:
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                if parts and len(parts) > 0:
                    translated_text = parts[0].get('text', '')
                    
                    if translated_text:
                        return JsonResponse({
                            'success': True,
                            'translated': translated_text.strip()
                        })
            
            print(f"[DEBUG] Gemini result structure: {result}")
            return JsonResponse({
                'error': '번역 결과를 받지 못했습니다.',
                'success': False
            }, status=500)
        else:
            print(f"[DEBUG] Gemini error response: {response.text}")
            return JsonResponse({
                'error': f'번역 서버 오류 (Status: {response.status_code})',
                'success': False
            }, status=response.status_code)
            
    except requests.Timeout:
        return JsonResponse({
            'error': '번역 서버 응답 시간이 초과되었습니다.',
            'success': False
        }, status=504)
    except Exception as e:
        import traceback
        print(f"Translation Error: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': f'번역 오류: {str(e)}',
            'success': False
        }, status=500)


# =============================================================================
# Onboarding API (왓챠 스타일 게임 평가 시스템)
# =============================================================================

@login_required
def onboarding_status_api(request):
    """
    온보딩 상태 확인 API
    
    Returns:
        - needs_onboarding: 온보딩이 필요한지 여부
        - status: 현재 온보딩 상태
        - total_ratings: 총 평가 수
    """
    from .models import OnboardingStatus, GameRating
    
    user = request.user
    
    # Steam 연동된 사용자는 온보딩 스킵
    if user.is_steam_linked and user.steam_id:
        return JsonResponse({
            'needs_onboarding': False,
            'reason': 'steam_linked',
            'status': 'completed'
        })
    
    # 온보딩 상태 확인
    try:
        status = OnboardingStatus.objects.get(user=user)
        needs_onboarding = status.status in ['not_started', 'in_progress']
    except OnboardingStatus.DoesNotExist:
        status = None
        needs_onboarding = True
    
    # 이미 평가 데이터가 충분하면 온보딩 필요 없음
    rating_count = GameRating.objects.filter(user=user).count()
    if rating_count >= 5:
        needs_onboarding = False
    
    return JsonResponse({
        'needs_onboarding': needs_onboarding,
        'status': status.status if status else 'not_started',
        'current_step': status.current_step if status else 0,
        'total_ratings': rating_count
    })


@login_required
def onboarding_games_api(request):
    """
    온보딩 게임 목록 API
    
    Query params:
        - step: 현재 단계 (0-4)
    """
    from .models import GameRating
    from .onboarding import get_onboarding_games
    
    step = int(request.GET.get('step', 0))
    
    # 이미 평가한 게임 ID 목록
    rated_games = list(GameRating.objects.filter(
        user=request.user
    ).values_list('game__rawg_id', flat=True))
    
    result = get_onboarding_games(step=step, exclude_rated=rated_games)
    
    return JsonResponse(result)


@login_required
@require_http_methods(["POST"])
def onboarding_rate_api(request):
    """
    게임 평가 저장 API
    
    Body:
        - game_id: RAWG 게임 ID
        - game_title: 게임 제목 (DB에 없을 경우 생성용)
        - game_image: 게임 이미지 URL
        - score: 평점 (-1, 0, 3.5, 5)
    """
    from .onboarding import save_user_rating
    from .models import OnboardingStatus
    from games.models import Game
    
    try:
        data = json.loads(request.body)
        game_id = data.get('game_id')
        game_title = data.get('game_title', f'Game {game_id}')
        game_image = data.get('game_image', '')
        score = float(data.get('score', 0))
        
        if not game_id:
            return JsonResponse({'error': '게임 ID가 필요합니다.'}, status=400)
        
        # 게임이 DB에 없으면 생성
        game, created = Game.objects.get_or_create(
            rawg_id=game_id,
            defaults={
                'title': game_title,
                'image_url': game_image,
                'genre': 'Unknown'
            }
        )
        
        # 평가 저장
        rating = save_user_rating(
            user=request.user,
            game_id=game.id,
            score=score,
            is_onboarding=True
        )
        
        # 온보딩 상태 업데이트
        status, _ = OnboardingStatus.objects.get_or_create(user=request.user)
        
        return JsonResponse({
            'success': True,
            'rating_id': rating.id,
            'total_ratings': status.total_ratings,
            'game_title': game.title,
            'score': score
        })
        
    except Exception as e:
        import traceback
        print(f"Rating error: {e}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def onboarding_next_step_api(request):
    """
    온보딩 다음 단계로 이동
    """
    from .models import OnboardingStatus
    
    try:
        data = json.loads(request.body)
        next_step = int(data.get('step', 0))
        
        status, _ = OnboardingStatus.objects.get_or_create(user=request.user)
        status.current_step = next_step
        
        if status.status == 'not_started':
            status.status = 'in_progress'
            status.started_at = timezone.now()
        
        status.save()
        
        return JsonResponse({
            'success': True,
            'current_step': status.current_step
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def onboarding_complete_api(request):
    """
    온보딩 완료/스킵 처리 API
    
    Body:
        - skipped: 스킵 여부 (boolean)
    """
    from .onboarding import complete_onboarding
    
    try:
        data = json.loads(request.body)
        skipped = data.get('skipped', False)
        
        status = complete_onboarding(request.user, skipped=skipped)
        
        return JsonResponse({
            'success': True,
            'status': status.status,
            'total_ratings': status.total_ratings
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def onboarding_recommendations_api(request):
    """
    온보딩 기반 게임 추천 API
    """
    from .onboarding import get_recommendations_for_user
    
    result = get_recommendations_for_user(request.user, limit=20)
    
    return JsonResponse(result)


@login_required
def get_game_rating_api(request, rawg_id):
    """
    특정 게임에 대한 사용자의 평가 조회 API
    
    Args:
        rawg_id: RAWG 게임 ID
    
    Returns:
        {score: float} or {score: null}
    """
    from .models import GameRating
    from games.models import Game
    
    try:
        game = Game.objects.get(rawg_id=rawg_id)
        rating = GameRating.objects.get(user=request.user, game=game)
        return JsonResponse({'score': rating.score, 'game_id': game.id})
    except (Game.DoesNotExist, GameRating.DoesNotExist):
        return JsonResponse({'score': None})
