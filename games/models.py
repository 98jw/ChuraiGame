from django.db import models
from django.conf import settings

# Create your models here.
class Game(models.Model):
    steam_appid = models.IntegerField(unique=True, null=True) # 스팀 연동용
    title = models.CharField(max_length=200)
    genre = models.CharField(max_length=100)
    image_url = models.URLField()
    rawg_id = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    background_image = models.URLField(max_length=500, blank=True)
    metacritic_score = models.IntegerField(null=True, blank=True)
    # IGDB 등에서 가져온 메타데이터 저장

class GameScreenshot(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='screenshots')
    image_url = models.URLField(max_length=500)

class GameTrailer(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='trailers')
    name = models.CharField(max_length=200)
    preview_url = models.URLField(max_length=500)
    data_480 = models.URLField(max_length=500)
    data_max = models.URLField(max_length=500)

class CachedGameList(models.Model):
    """
    RAWG API 응답을 캐싱하여 로딩 속도 향상
    카테고리별로 게임 목록을 JSON으로 저장
    """
    CATEGORY_CHOICES = [
        ('popular', '요즘 뜨는'),
        ('top_rated', '평점 높은'),
        ('new_releases', '신작 게임'),
        ('trending', '트렌딩'),
        ('upcoming', '출시 예정'),
    ]
    
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, unique=True)
    games_data = models.JSONField(default=list)  # 게임 목록 JSON
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Cached Game List'
        verbose_name_plural = 'Cached Game Lists'
    
    def __str__(self):
        return f"{self.get_category_display()} ({len(self.games_data)} games)"
    
    @classmethod
    def get_cached_games(cls, category, max_age_hours=6):
        """
        캐시된 게임 목록 가져오기
        max_age_hours 이내의 캐시만 유효
        """
        from django.utils import timezone
        from datetime import timedelta
        
        try:
            cache = cls.objects.get(category=category)
            age = timezone.now() - cache.updated_at
            if age < timedelta(hours=max_age_hours):
                return cache.games_data
        except cls.DoesNotExist:
            pass
        return None
    
    @classmethod
    def set_cached_games(cls, category, games_data):
        """캐시 저장/업데이트"""
        cache, created = cls.objects.update_or_create(
            category=category,
            defaults={'games_data': games_data}
        )
        return cache


class Rating(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    score = models.FloatField() # 1.0 ~ 5.0
    content = models.TextField(blank=True) # 리뷰 내용
    playtime_forever = models.IntegerField(default=0) # 스팀에서 가져온 플레이 타임 (분)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'game') # 한 유저는 한 게임에 하나의 평가만
