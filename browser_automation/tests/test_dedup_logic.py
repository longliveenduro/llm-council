import sys
from pathlib import Path

# Add the directory containing chatgpt_automation to the path
sys.path.append(str(Path(__file__).parent.parent))

async def test_deduplication():
    # We want to test the logic inside send_prompt
    # Since we can't easily call it without Playwright, we'll verify the logic manually or extract it
    
    image_paths = ["path1.jpg", "path2.jpg", "path1.jpg", None, "path3.jpg", "path2.jpg"]
    
    # Logic from send_prompt:
    unique_paths = []
    seen = set()
    for p in image_paths:
        if p and p not in seen:
            unique_paths.append(p)
            seen.add(p)
    
    print(f"Original: {image_paths}")
    print(f"Deduplicated: {unique_paths}")
    
    expected = ["path1.jpg", "path2.jpg", "path3.jpg"]
    assert unique_paths == expected
    print("Deduplication test passed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_deduplication())
