import asyncio
import sys
import os

# Add parent directory to path if needed, or assume running from project root
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chatgpt_automation import get_browser_context, ensure_memory_off

async def verify_memory_check():
    print("Starting verification of ChatGPT Memory Check...")
    context = None
    try:
        context, page = await get_browser_context()
        print("Browser launched.")
        
        print("Please ensure you are logged in. Waiting 5 seconds before checking...")
        await page.goto("https://chatgpt.com/")
        await asyncio.sleep(5)
        
        # Check if we are really logged in
        if "login" in page.url or await page.query_selector('button:has-text("Log in")'):
            print("Please log in manually in the opened browser.")
            input("Press Enter after you have logged in...")
        
        print("Running ensure_memory_off()...")
        success = await ensure_memory_off(page)
        
        if success:
            print("\nVERIFICATION PASSED: ensure_memory_off returned True.")
        else:
            print("\nVERIFICATION FAILED: ensure_memory_off returned False.")
            
    except Exception as e:
        print(f"\nVERIFICATION FAILED with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if context:
            print("Closing browser...")
            await context.close()

if __name__ == "__main__":
    asyncio.run(verify_memory_check())
