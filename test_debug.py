from yomi.core import YomiCore

# Initialize Core in Debug Mode with 4 workers
core = YomiCore(output_dir="yomi_downloads", workers=4, debug=True)

# Test with a dummy URL (Logic test only, since we don't have a real matching URL for Generic yet)
# This will trigger the "Generic fallback" warning, which is what we want to test.
print("--- STARTING TEST ---")
core.download_manga("https://example.com/manga/test-series")
print("--- TEST FINISHED ---")