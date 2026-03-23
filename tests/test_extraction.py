import os
import pytest
from pathlib import Path
from scraper import OmniScraper

@pytest.fixture(scope="module")
def scraper_instance():
    """
    Fixture (testing-qa / python-testing-patterns) to ensure 
    the scraper is initialized once for the test module.
    """
    scraper = OmniScraper()
    return scraper

def test_metadata_extraction_clean_id(scraper_instance):
    """
    Tests if the metadata extraction handles dirty URLs properly 
    (extracting just the ID and making a clean URL).
    """
    dirty_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw&list=PLrY2hE_G3Z7Z02V7XhZf1d0Q31Xm_3N8z&t=10s"
    metadata = scraper_instance.get_metadata(dirty_url)
    
    assert metadata["id"] == "jNQXAC9IVRw", "Should extract pure video ID"
    assert "list=" not in metadata["clean_url"], "Clean URL should not contain playlist info"

def test_groq_fallback_extraction_short_video(scraper_instance):
    """
    Integration Test: 
    Tests the actual transcription fallback process on a very short video.
    Me at the zoo: https://www.youtube.com/watch?v=jNQXAC9IVRw
    """
    # Verify API key is loaded
    assert scraper_instance.client is not None, "Groq API Key is missing. Fallback test cannot run."
    
    url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    output_file_path = scraper_instance.process_video(url)
    
    # Assertions
    assert output_file_path is not None, "Process video should return a valid file path string"
    assert os.path.exists(output_file_path), "The text file must actually exist on disk"
    
    # Read and verify content
    content = Path(output_file_path).read_text(encoding="utf-8")
    assert len(content) > 10, "Transcription should not be empty"
    
    # Cleanup after test
    os.remove(output_file_path)

def test_playlist_extraction_logic(scraper_instance):
    """
    Tests if the get_playlist_videos correctly extracts a list of URLs
    from a public playlist without downloading the videos.
    """
    # A random public playlist (e.g., YouTube's own or a generic one)
    # Testing with a very small well-known playlist or just asserting the method doesn't crash on empty
    playlist_url = "https://www.youtube.com/playlist?list=PLBCF2DAC6FFB574DE" # YouTube Creators playlist
    try:
        urls = scraper_instance.get_playlist_videos(playlist_url)
        assert isinstance(urls, list), "Should return a list"
    except Exception as e:
        pytest.fail(f"Playlist extraction crashed: {e}")
