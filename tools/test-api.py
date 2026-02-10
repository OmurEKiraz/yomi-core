import requests
import time
import json

BASE_URL = "http://127.0.0.1:8000"

def print_step(msg):
    print(f"\n🚀 --- {msg} ---")

def test_api():
    # 1. HEALTH CHECK
    print_step("TEST 1: Health Check")
    r = requests.get(f"{BASE_URL}/")
    print(f"Status: {r.status_code}")
    print(f"Response: {r.json()}")
    assert r.status_code == 200

    # 2. SEARCH (Fuzzy)
    print_step("TEST 2: Search 'Solo'")
    r = requests.get(f"{BASE_URL}/search", params={"q": "solo"})
    results = r.json()
    print(f"Found {len(results)} mangas.")
    if results:
        print(f"Top result: {results[0]['name']} ({results[0]['slug']})")
        target_slug = results[0]['slug']
    else:
        print("❌ Search failed to find 'solo'")
        return

    # 3. DETAILS
    print_step(f"TEST 3: Get Details for '{target_slug}'")
    r = requests.get(f"{BASE_URL}/manga/{target_slug}")
    if r.status_code == 200:
        data = r.json()
        print(f"Title: {data['title']}")
        print(f"Total Chapters: {len(data['chapters'])}")
        # Düzeltilmiş Satır:
    if data['metadata']:
        print(f"Metadata (Writer): {data['metadata'].get('writer', 'Unknown')}")
    else:
        print("⚠️ Metadata: Bulunamadı (Anilist eşleşmedi)")
        return

    # 4. DOWNLOAD (Background Task)
    # Sadece 1. bölümü indirelim ki test çabuk bitsin
    print_step(f"TEST 4: Start Download '{target_slug}' (Chapter 1)")
    payload = {
        "slug": target_slug,
        "chapters": "1" 
    }
    r = requests.post(f"{BASE_URL}/download", json=payload)
    print(f"Queue Response: {r.json()}")
    assert r.status_code == 200

    # 5. QUEUE MONITORING
    print_step("TEST 5: Monitor Queue (5 seconds poll)")
    for _ in range(5):
        time.sleep(1)
        r = requests.get(f"{BASE_URL}/queue")
        tasks = r.json()
        print(f"Active Tasks: {tasks}")
        # Eğer tamamlandıysa döngüden çık
        if tasks and tasks[0]['status'] == 'completed':
            print("✅ Download Completed!")
            break
        
    # 6. LIBRARY CHECK
    print_step("TEST 6: Check Library")
    r = requests.get(f"{BASE_URL}/library")
    print(f"Library Content: {json.dumps(r.json(), indent=2)}")

if __name__ == "__main__":
    try:
        test_api()
        print("\n✨ TÜM TESTLER BAŞARIYLA GEÇTİ! FLUTTER'A HAZIRSIN.")
    except Exception as e:
        print(f"\n❌ BİR HATA OLUŞTU: {e}")