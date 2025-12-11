"""
URL configuration for ChuraiGame project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users import views as user_views  # 메인 페이지 연결을 위해 import

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 1. users 앱의 URL들을 포함시킵니다. (예: /users/login/)
    path('users/', include('users.urls')),
    
    # 2. games 앱의 URL들을 포함시킵니다. (예: /games/list/)
    path('games/', include('games.urls')),
    
    # 3. 루트 URL('')로 접속 시 users 앱의 main_view로 연결합니다.
    path('', user_views.main_view, name='home'),

    path('community/', include('community.urls')),
]

# 개발 환경에서 미디어 파일 서빙
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)