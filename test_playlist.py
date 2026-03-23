import sys
from scraper import OmniScraper

def test_playlist_logic():
    scraper = OmniScraper()
    playlist_url = "https://www.youtube.com/watch?v=AIs_E-9O_40&list=PLrY2hE_G3Z7Z02V7XhZf1d0Q31Xm_3N8z"
    
    print("--- Test 1: get_metadata on a playlist URL ---")
    try:
        metadata = scraper.get_metadata(playlist_url)
        print(f"✅ Extracted Video ID: {metadata['id']}")
        print(f"✅ Clean URL: {metadata.get('clean_url')}")
    except Exception as e:
        print(f"❌ Error in get_metadata: {e}")

    print("\n--- Test 2: get_playlist_videos ---")
    try:
        urls = scraper.get_playlist_videos("https://www.youtube.com/playlist?list=PLrY2hE_G3Z7Z02V7XhZf1d0Q31Xm_3N8z")
        print(f"✅ Extracted {len(urls)} videos from playlist.")
        for u in urls[:3]:
            print(f"  - {u}")
    except Exception as e:
        print(f"❌ Error in get_playlist_videos: {e}")

if __name__ == "__main__":
    test_playlist_logic()
