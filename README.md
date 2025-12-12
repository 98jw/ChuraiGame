# 🎮 GameMatch (ChuraiGame)

> **"당신의 취향, AI가 찾아드립니다."**
> 
> **Steam 연동 기반 하이브리드 게임 추천 & AI 큐레이팅 플랫폼**  
> *SSAFY 1학기 관통 프로젝트 - 최우수 기술 스택*

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)
![Vue.js](https://img.shields.io/badge/Vue.js-3.0-4FC08D?style=for-the-badge&logo=vuedotjs&logoColor=white)
![Steam](https://img.shields.io/badge/Steam_API-Intergration-000000?style=for-the-badge&logo=steam&logoColor=white)
![OpenAI](https://img.shields.io/badge/GPT--5_Nano-AI_Curator-412991?style=for-the-badge&logo=openai&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Gemini_2.0-Translator-8E75B2?style=for-the-badge&logo=google-gemini&logoColor=white)

</div>

<br>

## 📖 프로젝트 개요

**GameMatch**는 "할 게임이 없다"고 느끼는 게이머들을 위해 개발되었습니다.  
단순한 인기 순위가 아닌, **사용자의 Steam 라이브러리 플레이 기록**과 **직관적인 온보딩 평가**를 분석하여 개인화된 게임을 추천합니다.

### 💡 핵심 가치
- **Connectivity**: Steam 계정 연동 한 번으로 나의 게임 인생을 분석
- **Personalization**: 플레이 타임과 평가 데이터를 결합한 정교한 추천 알고리즘
- **Optimization**: 외부 API 의존도를 낮추고 자체 캐싱 시스템으로 **98% 속도 향상**
- **Intelligence**: GPT-5 기반 AI 큐레이터와의 대화를 통한 감성 추천

---

## 🏗 시스템 아키텍처

```mermaid
graph TD
    User[User / Browser] -->|Vue.js Interaction| Frontend[Frontend Views]
    Frontend -->|REST API| Backend[Django REST Framework]
    
    subgraph "Backend Service"
        Backend -->|Auth| SteamAuth[Steam OpenID Login]
        Backend -->|Feature| Recommender[Recommendation Engine]
        Backend -->|Feature| AIChat[AI Chatbot (GPT/Gemini)]
        Backend -->|Data| DB[(SQLite DB)]
        
        Recommender -->|Read| CachedGame[DB Cache Layer]
        Recommender -->|Calc| Similarity[SciPy Hybrid Filtering]
    end
    
    subgraph "External APIs"
        SteamAuth --> SteamAPI[Steam Web API]
        Backend --> RAWG[RAWG Game API]
        Backend --> CheapShark[CheapShark Sale API]
        AIChat --> OpenAI[GPT-5 Nano]
    end
    
    CachedGame -.->|Cache Miss| RAWG
```

---

## ⚡ 기술적 도전과 해결 (Troubleshooting)

### 1. RAWG API 속도 문제 해결 (Performance Optimization)
**문제:** 메인 페이지 로딩 시 `Popular`, `Trending`, `New Release` 등의 섹션을 위해 매번 RAWG API를 호출하여 로딩 시간이 **9초 이상** 소요됨.  
**해결:**
- **DB Caching Layer** 구현: API 응답 결과를 `CachedGameList` 모델에 JSON 형태로 저장.
- **TTL (Time-To-Live)** 설정: 6시간 주기로 자동 갱신.
- **결과:** 로딩 속도 **9초 → 0.15초 (약 98% 단축)** 달성.

### 2. Cold Start 문제 해결 (Onboarding System)
**문제:** 신규 가입자는 데이터가 없어 추천이 불가능함.  
**해결:** 
- **왓챠(Watcha) 스타일 온보딩** 도입.
- 가입 직후 인기 게임 1,500개를 스와이프하며 평가 (-1: 싫어요, 0: 관심없음, 3.5: 좋아요, 5: 인생게임).
- 최소 3개 이상 평가 시 즉시 **Item-Based Collaborative Filtering** 작동.

### 3. 추천 정교화 (Hybrid Recommendation)
**전략:** 단순히 장르만 매칭하지 않고 복합적인 점수 산정 로직 구현.
```python
# games/recommendation.py
def calculate_score(game, user_pref):
    score = 0
    score += genre_match_score(game) * 0.4  # 장르 적합도 (40%)
    score += metacritic_score(game) * 0.25  # 전문가 평점 (25%)
    score += user_rating_score(game) * 0.2  # 유저 평점 (20%)
    score += sale_benefit_score(game) * 0.15 # 할인율 (15%)
    return score
```

---

## ✨ 주요 기능 상세

### 1. 🔐 Steam 완벽 연동
- **OpenID 2.0**: 보안 걱정 없는 공식 로그인 지원
- **라이브러리 분석**: 보유 게임, 플레이 타임 자동 동기화
- **실시간 반영**: "내가 어제 3시간 플레이한 Elden Ring"이 즉시 추천 알고리즘에 반영됨

### 2. 🤖 AI 게임 큐레이터 (Chatbot)
- **Context-Aware**: 단순 챗봇이 아닙니다. 유저의 Steam 라이브러리와 평가 데이터를 Prompt Context로 주입.
- **GPT-5 Nano**: "너 엘든링 100시간 했네? 그럼 P의 거짓은 어때?" 같은 개인화된 대화 가능.
- **Gemini Translation**: 영어로 된 게임 설명을 Gemini 2.0 Flash Lite를 이용해 1초 만에 자연스러운 한국어로 번역.

### 3. 💰 스마트 세일 정보
- **CheapShark API Integration**: Steam 외에도 다양한 스토어의 최저가 비교.
- **Scam Filter**: 할인율은 높지만 평점이 낮은 '스컴 게임'을 자동 필터링 (리뷰 500개 이상, 긍정 80% 이상).

### 4. 👥 커뮤니티 & 리뷰
- 게임별 별점 평가 및 코멘트 작성
- 유저 간 게시글 작성, 좋아요, 댓글 소통 기능
- 이미지 업로드 지원

---

## 🛠 설치 및 실행 방법

### Prerequisites
- Python 3.9+
- Django 5.x
- API Keys (RAWG, OpenAI/GMS)

### 1. 환경 설정
```bash
# Repository Clone
git clone https://github.com/username/ChuraiGame.git
cd ChuraiGame

# 가상환경 생성 및 실행
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. 데이터베이스 초기화 (필수)
이 프로젝트는 대량의 게임 데이터를 다루므로 초기 적재 과정이 필요합니다.

```bash
# DB 마이그레이션
python manage.py migrate

# 1. 게임 기본 데이터 적재 (JSON -> DB)
python manage.py load_games

# 2. 장르 정보 업데이트 (RAWG API 연동, 약 10~20분 소요)
python manage.py update_genres --limit=100  # 테스트용 100개만 우선 실행 권장

# 3. 메인 페이지용 캐시 생성 (속도 향상 핵심)
python manage.py refresh_game_cache
```

### 3. 서버 실행
```bash
python manage.py runserver
```
접속: [http://localhost:8000](http://localhost:8000)

---

## 📂 폴더 구조 (Project Structure)

```
ChuraiGame/
├── games/                  # 게임 데이터, 추천 로직, API 관리
│   ├── management/commands # 데이터 적재/싱크 스크립트
│   ├── utils.py            # RAWG API 래퍼 & 추천 알고리즘
│   └── views.py            # 게임 상세, API 뷰
├── users/                  # 유저 관리, Steam 연동, 온보딩
│   ├── steam_auth.py       # Steam OpenID & API 핸들러
│   ├── onboarding.py       # 왓챠 스타일 평가 로직
│   └── views.py            # AI 챗봇, 프로필
├── community/              # 게시판 기능
├── templates/              # Vue.js가 포함된 Django 템플릿
└── steamsale.py            # 세일 데이터 크롤링 모듈
```

---

<div align="center">

**Created by SSAFY 13기 1학기 관통 프로젝트 팀**
<br>
사용된 모든 게임 이미지의 저작권은 각 개발사/배급사에 있습니다.

</div>
