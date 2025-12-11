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
]