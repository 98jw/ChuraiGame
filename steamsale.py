import requests
import json
import time

# ==========================================
# 설정
# ==========================================
TARGET_COUNT = 2000  # 목표 수집 개수
BATCH_SIZE = 100     # 한 번에 가져올 개수 (최대 100 추천)
API_URL = "https://steamsale.windbell.co.kr/api/v1/sales"

def crawl_steam_sales_fast():
    collected_data = []
    page = 1
    
    print(f"🚀 크롤링 시작: 목표 {TARGET_COUNT}개 (현재 할인 정보만 수집)")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://steamsale.windbell.co.kr/'
    }

    while len(collected_data) < TARGET_COUNT:
        try:
            # 파라미터 설정 (size=100으로 한 번에 많이 요청)
            params = {
                'keyword': '',
                'page': page,
                'size': BATCH_SIZE 
            }
            
            response = requests.get(API_URL, params=params, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ {page}페이지 요청 실패: {response.status_code}")
                break
            
            data = response.json()
            items = data.get('list', [])
            
            if not items:
                print("🏁 더 이상 데이터가 없습니다.")
                break
                
            # 데이터 가공 및 저장
            for item in items:
                game_info = {
                    'game_id': item.get('game_id'),
                    'title': item.get('title_nm'),
                    'current_price': item.get('sale_price_va'),     # 현재 판매가
                    'original_price': item.get('full_price_va'),    # 정가
                    'discount_rate': item.get('discount_rt'),       # 현재 할인율 (0.5 = 50%)
                    'thumbnail': item.get('img_lk'),
                    'store_link': item.get('store_lk')
                }
                collected_data.append(game_info)
            
            print(f"   ✅ {page}페이지 완료 (누적 {len(collected_data)}개)")
            
            page += 1
            time.sleep(0.2) # 너무 빨라서 0.2초 매너 대기
            
        except Exception as e:
            print(f"⚠️ 에러 발생: {e}")
            break

    # 목표 개수에 맞춰 자르기
    final_result = collected_data[:TARGET_COUNT]

    # 파일 저장
    file_name = 'users/steam_sale_dataset_fast.json'
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(final_result, f, ensure_ascii=False, indent=4)
        
    print(f"\n🎉 완료! 총 {len(final_result)}개 저장됨: {file_name}")

# 실행
if __name__ == "__main__":
    while True:
        crawl_steam_sales_fast()
        print("⏳ 24시간 대기 중...")
        time.sleep(86400)