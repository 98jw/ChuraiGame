from django.contrib import admin
from .models import Game, Rating, GameScreenshot, GameTrailer

class GameScreenshotInline(admin.TabularInline):
    model = GameScreenshot
    extra = 0

class GameTrailerInline(admin.TabularInline):
    model = GameTrailer
    extra = 0

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['title', 'genre', 'steam_appid', 'rawg_id', 'metacritic_score']
    list_filter = ['genre']
    search_fields = ['title', 'steam_appid']
    inlines = [GameScreenshotInline, GameTrailerInline]
    readonly_fields = ['steam_appid']

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['user', 'game', 'score', 'created_at']
    list_filter = ['score', 'created_at']
    search_fields = ['user__username', 'game__title']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(GameScreenshot)
class GameScreenshotAdmin(admin.ModelAdmin):
    list_display = ['game', 'image_url']
    search_fields = ['game__title']

@admin.register(GameTrailer)
class GameTrailerAdmin(admin.ModelAdmin):
    list_display = ['game', 'name', 'preview_url']
    search_fields = ['game__title', 'name']
