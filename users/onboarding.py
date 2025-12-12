"""
온보딩 시스템 및 Item-Based Collaborative Filtering
왓챠 스타일의 콜드 스타트 해결

알고리즘 전략:
1. 온보딩 단계 (Rule-Based): 인기 게임(리뷰 많은 순) 표시 - JSON에서 로드
2. 평가 진행 중 (Content-Based): 평가한 게임과 유사한 게임 추천
3. 데이터 축적 후 (Item-Based CF): 게임 간 유사도 기반 추천
"""

import json
import os
import pandas as pd
import numpy as np
from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.conf import settings
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)

# JSON에서 온보딩 게임 로드 (캐시)
_onboarding_games_cache = None

def load_onboarding_games_from_json():
    """
    JSON 데이터셋에서 리뷰가 많은 인기 게임을 로드하여 온보딩용 데이터로 변환
    Steam CDN 썸네일 사용 (빠른 로딩)
    """
    global _onboarding_games_cache
    
    if _onboarding_games_cache is not None:
        return _onboarding_games_cache
    
    json_path = os.path.join(settings.BASE_DIR, 'users', 'steam_sale_dataset_fast.json')
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 1. Steam 평점 80% 이상, 리뷰 1000개 이상인 게임만 필터링
        quality_games = [
            g for g in data 
            if g.get('steam_rating', 0) >= 80 
            and g.get('review_count', 0) >= 1000
        ]
        
        # 2. 리뷰 수(review_count) 기준으로 내림차순 정렬 (인기 게임 추출)
        sorted_games = sorted(
            quality_games, 
            key=lambda x: x.get('review_count', 0), 
            reverse=True
        )
        
        # 3. 상위 100개 게임만 추출
        top_games = sorted_games[:100]
        
        # 4. 온보딩 형식에 맞게 데이터 가공 (Steam CDN 이미지 사용!)
        formatted_games = []
        for game in top_games:
            formatted_games.append({
                'title': game['title'],
                'rawg_id': int(game['steam_app_id']),  # steam_app_id를 rawg_id 대신 사용
                'steam_app_id': game.get('steam_app_id'),
                'image': game['thumbnail'],  # Steam CDN 이미지 (빠름!)
                'steam_rating': game.get('steam_rating', 0),
                'review_count': game.get('review_count', 0),
            })
        
        # 5. 캐시 저장
        _onboarding_games_cache = {
            'popular': formatted_games
        }
        
        logger.info(f"Loaded {len(formatted_games)} games from JSON for onboarding")
        return _onboarding_games_cache
        
    except Exception as e:
        logger.error(f"Error loading onboarding games from JSON: {e}")
        return {'popular': []}


# 온보딩 단계별 설정 (인기 게임 단일 단계로 간소화)
ONBOARDING_STEPS = [
    {'name': '인기 게임', 'genre': 'popular', 'description': '평가가 많은 인기 게임들이에요. 아는 게임을 평가해주세요!'},
]


def get_onboarding_games(step=0, exclude_rated=None):
    """
    온보딩 단계별 게임 목록 반환
    
    Args:
        step: 현재 단계 (0만 사용)
        exclude_rated: 이미 평가한 게임 ID 리스트
    
    Returns:
        dict: {games: [...], step_info: {...}}
    """
    # JSON에서 게임 로드
    onboarding_games = load_onboarding_games_from_json()
    
    if step >= len(ONBOARDING_STEPS):
        return {'games': [], 'step_info': None, 'is_complete': True}
    
    step_info = ONBOARDING_STEPS[step]
    genre = step_info['genre']
    games = onboarding_games.get(genre, [])
    
    # 이미 평가한 게임 제외
    if exclude_rated:
        games = [g for g in games if g['rawg_id'] not in exclude_rated]
    
    return {

        'games': games,
        'step_info': step_info,
        'current_step': step,
        'total_steps': len(ONBOARDING_STEPS),
        'is_complete': False
    }


def calculate_game_similarity_batch():
    """
    배치 작업: 게임 간 유사도 계산
    
    매일 새벽에 실행하여 GameSimilarity 테이블 갱신
    - Item-Based Collaborative Filtering 사용
    - 희소 행렬로 메모리 효율화
    - transaction.atomic()으로 안전한 데이터 갱신
    """
    from django.db import transaction
    from .models import GameRating, GameSimilarity
    from games.models import Game
    
    logger.info("Starting game similarity batch calculation...")
    
    # 1. 모든 평가 데이터 가져오기 (필요한 컬럼만)
    ratings = list(GameRating.objects.filter(score__gt=0).values('user_id', 'game_id', 'score'))
    
    if len(ratings) < 10:
        logger.warning("Not enough rating data for similarity calculation")
        return
    
    df = pd.DataFrame(ratings)
    
    # 2. 희소 행렬 생성 (게임 x 유저)
    # Category 코드로 변환하여 인덱싱
    user_cat = df['user_id'].astype('category')
    game_cat = df['game_id'].astype('category')
    
    user_codes = user_cat.cat.codes
    game_codes = game_cat.cat.codes
    
    # 희소 행렬 생성 (행: 게임, 열: 유저, 값: 점수)
    sparse_matrix = csr_matrix(
        (df['score'], (game_codes, user_codes)),
        shape=(len(game_cat.cat.categories), len(user_cat.cat.categories))
    )
    
    # 3. 게임 간 코사인 유사도 계산
    similarity_matrix = cosine_similarity(sparse_matrix)
    
    # 4. 유사도 저장 준비 (상위 50개만 저장하여 DB 절약)
    game_ids = game_cat.cat.categories.tolist()
    
    similarities_to_create = []
    for i, game_a_id in enumerate(game_ids):
        # 유사도가 높은 상위 50개 게임 찾기
        sim_scores = similarity_matrix[i]
        top_indices = np.argsort(sim_scores)[::-1][1:51]  # 자기 자신 제외
        
        for j in top_indices:
            if sim_scores[j] > 0.1:  # 유사도 0.1 이상만 저장
                game_b_id = game_ids[j]
                similarities_to_create.append(GameSimilarity(
                    game_a_id=game_a_id,
                    game_b_id=game_b_id,
                    similarity_score=float(sim_scores[j])
                ))
    
    # 5. 트랜잭션으로 안전하게 저장 (삭제 + 생성이 원자적으로 처리)
    try:
        with transaction.atomic():
            # 기존 데이터 삭제
            GameSimilarity.objects.all().delete()
            # 새 데이터 벌크 생성
            GameSimilarity.objects.bulk_create(similarities_to_create, batch_size=1000)
        
        logger.info(f"Created {len(similarities_to_create)} similarity records")
    except Exception as e:
        logger.error(f"Batch calculation failed: {e}")
        # 트랜잭션 덕분에 에러 시 delete()도 롤백되어 기존 데이터 유지



def get_recommendations_for_user(user, limit=50):
    """
    사용자에게 게임 추천
    
    전략:
    1. 평가 데이터가 없으면 -> JSON 인기 게임 반환 (빠름!)
    2. 평가 데이터가 있으면 -> DB 기반 추천 시도
    3. DB 추천 결과가 부족하면 -> JSON 인기 게임으로 보충
    
    Args:
        user: User 객체
        limit: 반환할 추천 게임 수
    
    Returns:
        dict: {needs_onboarding, recommendations, method}
    """
    from .models import GameRating, GameSimilarity
    from games.models import Game
    
    def format_json_games(json_games, base_score=80, rated_ids=None):
        """JSON 게임 데이터를 프론트엔드 형식으로 변환"""
        rated_ids = rated_ids or []
        result = []
        for i, game in enumerate(json_games):
            # 이미 평가한 게임 제외
            steam_id = int(game.get('steam_app_id', 0) or 0)
            if steam_id in rated_ids:
                continue
            
            steam_rating = game.get('steam_rating', 0)
            review_count = game.get('review_count', 0)
            
            # 추천 점수 = 기본점수 + Steam평점/5 - 순서 패널티
            score = base_score + (steam_rating / 5) - (len(result) * 0.3)
            score = max(50, min(100, score))
            
            result.append({
                'id': None,  # DB ID 없음
                'rawg_id': steam_id,  # Steam App ID를 rawg_id로 사용
                'steam_app_id': game.get('steam_app_id'),
                'title': game['title'],
                'image_url': game.get('thumbnail', ''),  # Steam CDN (빠름!)
                'rating': round(steam_rating / 20, 1) if steam_rating else 0,
                'metacritic': game.get('metacritic_score'),
                'genres': [],  # JSON에 장르 없음
                'recommendation_score': round(score, 1),
                'is_on_sale': game.get('is_on_sale', False),
                'discount_rate': round(game.get('discount_rate', 0) * 100),
                'current_price': game.get('current_price'),
                'original_price': game.get('original_price'),
                'review_count': review_count,
            })
            
            if len(result) >= limit:
                break
                
        return result
    
    def format_db_games(games_queryset, base_score=80):
        """DB 게임 데이터를 프론트엔드 형식으로 변환"""
        result = []
        for i, game in enumerate(games_queryset):
            metacritic = float(game.metacritic_score) if game.metacritic_score else 0
            score = base_score + (metacritic / 5) - (i * 0.5)
            score = max(50, min(100, score))
            image = getattr(game, 'image_url', '') or getattr(game, 'background_image', '') or ''
            
            result.append({
                'id': game.id,
                'rawg_id': game.rawg_id,
                'title': game.title,
                'image_url': image,
                'rating': round(metacritic / 20, 1) if metacritic else 0,
                'metacritic': int(metacritic) if metacritic else None,
                'genres': game.genre.split(',')[:3] if game.genre else [],
                'recommendation_score': round(score, 1),
                'is_on_sale': False,
            })
        return result
    
    # JSON 인기 게임 로드 (폴백용)
    json_data = load_onboarding_games_from_json()
    popular_from_json = json_data.get('popular', [])
    
    # 사용자의 평가 데이터 가져오기
    user_ratings = GameRating.objects.filter(user=user, score__gt=0)
    rated_game_ids = list(user_ratings.values_list('game_id', flat=True))
    rated_steam_ids = list(user_ratings.values_list('game__rawg_id', flat=True))
    
    # 1. 평가 데이터가 없으면 -> JSON 인기 게임 반환 (빠름!)
    if len(rated_game_ids) == 0:
        return {
            'needs_onboarding': False,  # 온보딩 모달 대신 바로 추천 보여줌
            'recommendations': format_json_games(popular_from_json, 80, []),
            'method': 'popular_json',
            'message': '인기 게임을 추천해드려요! 게임을 평가하면 맞춤 추천이 더 정확해져요.'
        }
    
    # 2. 사용자가 좋아한 게임 (따봉 이상)
    liked_games = user_ratings.filter(score__gte=3.5).values_list('game_id', flat=True)
    
    if len(liked_games) == 0:
        # 아직 좋아하는 게임이 없음 -> JSON 인기 게임 (이미 평가한 것 제외)
        return {
            'needs_onboarding': False,
            'recommendations': format_json_games(popular_from_json, 75, rated_steam_ids),
            'method': 'popular_json_filtered',
            'message': '아직 좋아하는 게임이 없네요. 마음에 드는 게임에 👍를 눌러주세요!'
        }
    
    # 3. Item-Based CF 시도 (DB 기반)
    try:
        similar_games = GameSimilarity.objects.filter(
            game_a_id__in=liked_games
        ).exclude(
            game_b_id__in=rated_game_ids
        ).values('game_b_id').annotate(
            total_score=Avg('similarity_score')
        ).order_by('-total_score')[:limit]
        
        if similar_games.exists():
            game_ids = [g['game_b_id'] for g in similar_games]
            games = Game.objects.filter(id__in=game_ids)
            db_recommendations = format_db_games(games, 85)
            
            if len(db_recommendations) >= limit // 2:
                return {
                    'needs_onboarding': False,
                    'recommendations': db_recommendations,
                    'method': 'item_based_cf',
                    'message': f'좋아하신 게임과 비슷한 게임을 추천해드려요!'
                }
    except Exception as e:
        logger.error(f"Item-based CF failed: {e}")
    
    # 4. 장르 기반 추천 시도 (Content-Based)
    try:
        liked_game_objs = Game.objects.filter(id__in=liked_games)
        liked_genres = set()
        for game in liked_game_objs:
            if game.genre:
                liked_genres.update(game.genre.split(','))
        
        if liked_genres:
            genre_filter = Q()
            for genre in liked_genres:
                genre_filter |= Q(genre__icontains=genre.strip())
            
            similar_by_genre = Game.objects.filter(genre_filter).exclude(
                id__in=rated_game_ids
            ).order_by('-metacritic_score')[:limit]
            
            db_recommendations = format_db_games(similar_by_genre, 75)
            
            if len(db_recommendations) >= limit // 2:
                return {
                    'needs_onboarding': False,
                    'recommendations': db_recommendations,
                    'method': 'content_based',
                    'message': f'좋아하시는 장르({", ".join(list(liked_genres)[:3])})의 게임을 추천해드려요!'
                }
    except Exception as e:
        logger.error(f"Content-based failed: {e}")
    
    # 5. 최후의 폴백: JSON 인기 게임 (항상 성공)
    return {
        'needs_onboarding': False,
        'recommendations': format_json_games(popular_from_json, 70, rated_steam_ids),
        'method': 'popular_json_fallback',
        'message': '인기 게임을 추천해드려요! 더 많은 게임을 평가하면 맞춤 추천이 정확해져요.'
    }


def save_user_rating(user, game_id, score, is_onboarding=False):
    """
    사용자 평가 저장
    
    Args:
        user: User 객체
        game_id: 게임 ID (RAWG ID 또는 DB ID)
        score: 점수 (-1, 0, 3.5, 5)
        is_onboarding: 온보딩 평가 여부
    
    Returns:
        GameRating 객체
    """
    from .models import GameRating, OnboardingStatus
    from games.models import Game
    
    # 게임 찾기 (RAWG ID로 먼저 시도)
    try:
        game = Game.objects.get(rawg_id=game_id)
    except Game.DoesNotExist:
        try:
            game = Game.objects.get(id=game_id)
        except Game.DoesNotExist:
            # 게임이 DB에 없으면 생성 (최소 정보만)
            game = Game.objects.create(
                rawg_id=game_id,
                title=f"Game {game_id}",
                genre="Unknown"
            )
    
    # 평가 생성 또는 업데이트
    rating, created = GameRating.objects.update_or_create(
        user=user,
        game=game,
        defaults={
            'score': score,
            'is_onboarding': is_onboarding
        }
    )
    
    # 온보딩 상태 업데이트
    if is_onboarding:
        status, _ = OnboardingStatus.objects.get_or_create(user=user)
        if status.status == 'not_started':
            status.status = 'in_progress'
            status.started_at = timezone.now()
        status.total_ratings = GameRating.objects.filter(user=user).count()
        status.save()
    
    return rating


def complete_onboarding(user, skipped=False):
    """
    온보딩 완료 처리
    
    Args:
        user: User 객체
        skipped: 스킵 여부
    """
    from .models import OnboardingStatus
    
    status, _ = OnboardingStatus.objects.get_or_create(user=user)
    status.status = 'skipped' if skipped else 'completed'
    status.completed_at = timezone.now()
    status.save()
    
    return status
