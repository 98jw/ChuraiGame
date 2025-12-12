from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('delete/', views.delete_account_view, name='delete'),
    path('', views.main_view, name='main'), # 메인 페이지 뷰 필요
    
    # Steam OAuth
    path('steam/login/', views.steam_login, name='steam_login'),
    path('steam/callback/', views.steam_callback, name='steam_callback'),
    path('steam/unlink/', views.steam_unlink, name='steam_unlink'),
    
    # Steam API
    path('api/steam/library/', views.steam_library_api, name='steam_library'),
    path('api/steam/recently-played/', views.steam_recently_played_api, name='steam_recently_played'),
    
    # Recommendation API
    path('api/recommendations/', views.personalized_recommendations_api, name='recommendations'),
    
    # AI Chatbot API
    path('api/ai-chat/', views.ai_chat_api, name='ai_chat'),
    
    # Translation API
    path('api/translate/', views.translate_text_api, name='translate'),
    
    # Onboarding API (왓챠 스타일 게임 평가)
    path('api/onboarding/status/', views.onboarding_status_api, name='onboarding_status'),
    path('api/onboarding/games/', views.onboarding_games_api, name='onboarding_games'),
    path('api/onboarding/rate/', views.onboarding_rate_api, name='onboarding_rate'),
    path('api/onboarding/next-step/', views.onboarding_next_step_api, name='onboarding_next_step'),
    path('api/onboarding/complete/', views.onboarding_complete_api, name='onboarding_complete'),
    path('api/onboarding/recommendations/', views.onboarding_recommendations_api, name='onboarding_recommendations'),
    
    # Game Rating API (상세 페이지에서 사용)
    path('api/game-rating/<int:rawg_id>/', views.get_game_rating_api, name='get_game_rating'),
]
