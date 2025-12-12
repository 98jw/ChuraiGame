from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    # 기본 필드 (username, password, email 등)는 상속받음
    
    # 프로필 관련 커스텀 필드
    nickname = models.CharField("닉네임", max_length=50, blank=True)
    avatar = models.ImageField("프로필 사진", upload_to="avatars/", null=True, blank=True)
    
    # 스팀 연동 관련
    steam_id = models.CharField("스팀 ID", max_length=50, unique=True, null=True, blank=True)
    
    # 소셜 연동 여부 플래그
    is_steam_linked = models.BooleanField(default=False)
    is_naver_linked = models.BooleanField(default=False)
    is_google_linked = models.BooleanField(default=False)
    
    # 추천 시스템을 위한 유사 유저 목록 (Many-to-Many)
    similar_users = models.ManyToManyField('self', blank=True)

    # 찜한 게임 목록
    wishlist = models.ManyToManyField('games.Game', related_name='wishlisted_by', blank=True)

    # --- [충돌 해결을 위한 추가 코드] ---
    # related_name을 설정하여 기본 auth.User 모델과의 충돌을 방지합니다.
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_name="custom_user_set",  # 여기를 수정
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="custom_user_set", # 여기를 수정
        related_query_name="user",
    )

    def __str__(self):
        return self.username


class SteamLibraryCache(models.Model):
    """
    Steam 라이브러리 캐시 - API 호출 최소화
    
    - 첫 로딩 시 Steam API 호출 후 DB에 저장
    - 이후 요청은 DB에서 즉시 반환 (0.01초)
    - 24시간마다 백그라운드 업데이트
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='steam_library_cache'
    )
    
    # Steam 라이브러리 데이터 (JSON)
    library_data = models.JSONField(default=list, help_text="Steam 라이브러리 게임 목록 JSON")
    
    # 통계
    total_games = models.IntegerField(default=0)
    total_playtime_hours = models.FloatField(default=0)
    
    # 캐시 관리
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Steam 라이브러리 캐시"
        verbose_name_plural = "Steam 라이브러리 캐시"
    
    def __str__(self):
        return f"{self.user.username}의 Steam 라이브러리 ({self.total_games}개)"
    
    def is_stale(self, hours=24):
        """캐시가 오래되었는지 확인 (기본 24시간)"""
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() - self.last_updated > timedelta(hours=hours)


class GameRating(models.Model):
    """
    사용자 게임 평가 모델 (왓챠 스타일)
    
    점수 체계:
    - DISLIKE (-1): 역따봉 (별로예요)
    - SKIP (0): 스킵/모르겠음
    - LIKE (3.5): 따봉 (재밌어요)
    - LOVE (5): 쌍따봉 (인생게임)
    """
    RATING_CHOICES = [
        (-1, '역따봉'),
        (0, '스킵'),
        (3.5, '따봉'),
        (5, '쌍따봉'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='game_ratings')
    game = models.ForeignKey('games.Game', on_delete=models.CASCADE, related_name='user_ratings')
    score = models.FloatField("평점", choices=RATING_CHOICES)
    
    # 평가 소스 (온보딩 vs 일반)
    is_onboarding = models.BooleanField("온보딩 평가 여부", default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "게임 평가"
        verbose_name_plural = "게임 평가"
        unique_together = ['user', 'game']  # 한 유저가 한 게임에 하나의 평가만
        indexes = [
            models.Index(fields=['user', 'score']),
            models.Index(fields=['game', 'score']),
        ]
    
    def __str__(self):
        rating_map = {-1: '역따봉', 0: '스킵', 3.5: '따봉', 5: '쌍따봉'}
        return f"{self.user.username} - {self.game.title}: {rating_map.get(self.score, self.score)}"


class OnboardingStatus(models.Model):
    """
    사용자 온보딩 상태 추적
    
    온보딩 단계:
    1. NOT_STARTED: 시작 안함
    2. IN_PROGRESS: 진행 중
    3. COMPLETED: 완료
    4. SKIPPED: 건너뜀
    """
    STATUS_CHOICES = [
        ('not_started', '시작 안함'),
        ('in_progress', '진행 중'),
        ('completed', '완료'),
        ('skipped', '건너뜀'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='onboarding_status')
    status = models.CharField("상태", max_length=20, choices=STATUS_CHOICES, default='not_started')
    
    # 진행 상황 추적
    current_step = models.IntegerField("현재 단계", default=0)  # 0: 초기, 1-5: 장르별 단계
    total_ratings = models.IntegerField("총 평가 수", default=0)
    
    # 날짜 추적
    started_at = models.DateTimeField("시작 시간", null=True, blank=True)
    completed_at = models.DateTimeField("완료 시간", null=True, blank=True)
    
    class Meta:
        verbose_name = "온보딩 상태"
        verbose_name_plural = "온보딩 상태"
    
    def __str__(self):
        return f"{self.user.username}: {self.get_status_display()}"


class GameSimilarity(models.Model):
    """
    게임 간 유사도 (미리 계산된 데이터)
    
    - 매일 배치 작업으로 계산
    - Item-Based Collaborative Filtering에 사용
    """
    game_a = models.ForeignKey('games.Game', on_delete=models.CASCADE, related_name='similarity_from')
    game_b = models.ForeignKey('games.Game', on_delete=models.CASCADE, related_name='similarity_to')
    similarity_score = models.FloatField("유사도 점수")  # 0 ~ 1
    
    # 배치 관리
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "게임 유사도"
        verbose_name_plural = "게임 유사도"
        unique_together = ['game_a', 'game_b']
        indexes = [
            models.Index(fields=['game_a', 'similarity_score']),
            models.Index(fields=['game_b', 'similarity_score']),
        ]
    
    def __str__(self):
        return f"{self.game_a.title} <-> {self.game_b.title}: {self.similarity_score:.2f}"
