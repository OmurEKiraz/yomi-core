import requests
import json
import re
import time
import os

# HEDEF: 5000 Manga
TARGET_COUNT = 5000
PER_PAGE = 50
OUTPUT_PATH = "yomi/utils/raw-names.json"

def slugify(text):
    """ 'One Piece' -> 'one-piece', 'Bleach!' -> 'bleach' """
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text) 
    text = re.sub(r'[\s]+', '-', text)
    return text.strip('-')

def fetch_top_manga_anilist():
    print(f"📡 AniList API'ye Bağlanılıyor (Hedef: {TARGET_COUNT} Popüler Manga)...")
    
    url = 'https://graphql.anilist.co'
    slugs = []
    seen = set()
    page = 1

    # GraphQL Sorgusu (Popülerliğe göre sırala)
    query = '''
    query ($page: Int, $perPage: Int) {
      Page (page: $page, perPage: $perPage) {
        pageInfo {
          hasNextPage
        }
        media (type: MANGA, sort: POPULARITY_DESC, isAdult: false) {
          title {
            romaji
            english
          }
        }
      }
    }
    '''

    while len(slugs) < TARGET_COUNT:
        variables = {
            'page': page,
            'perPage': PER_PAGE
        }

        try:
            response = requests.post(url, json={'query': query, 'variables': variables})
            
            if response.status_code != 200:
                print(f"❌ API Hatası (Sayfa {page}): {response.status_code}")
                time.sleep(5) # Biraz bekle tekrar dene
                continue

            data = response.json()
            media_list = data['data']['Page']['media']
            
            count_on_page = 0
            for item in media_list:
                # Hem Romaji (Shingeki no Kyojin) hem İngilizce (Attack on Titan) alalım
                titles = []
                if item['title']['english']: titles.append(item['title']['english'])
                if item['title']['romaji']: titles.append(item['title']['romaji'])
                
                for t in titles:
                    slug = slugify(t)
                    if slug and slug not in seen and len(slug) > 2: # 'k' gibi tek harflileri ele
                        slugs.append(slug)
                        seen.add(slug)
                        count_on_page += 1

            print(f"📄 Sayfa {page} alındı... (Toplam: {len(slugs)})")
            
            if not data['data']['Page']['pageInfo']['hasNextPage']:
                print("⚠️ Başka sayfa kalmadı.")
                break
                
            page += 1
            time.sleep(1) # API'yi boğmamak için nezaket

        except Exception as e:
            print(f"⚠️ Hata: {e}")
            break

    # Listeyi Kes (Tam 1000 olsun veya ne kadar bulduysa)
    final_list = slugs[:TARGET_COUNT]

    # Klasör kontrolü
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=2)
    
    print(f"✅ İŞLEM TAMAM! {len(final_list)} adet popüler manga ismi '{OUTPUT_PATH}' dosyasına kaydedildi.")

if __name__ == "__main__":
    fetch_top_manga_anilist()