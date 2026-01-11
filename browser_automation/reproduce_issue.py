import asyncio
import sys
import os
# Add the compiled directory's parent to sys.path so we can import code if needed
# But here we are in the same dir.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from browser_automation.claude_automation import get_browser_context, send_prompt

async def reproduce():
    print("Starting reproduction...")
    context, page = await get_browser_context()
    
    # 1. Simulate getting stuck on a "Conversation not found" page
    # by navigating to a bogus chat ID
    print("Navigating to invalid chat URL...")
    await page.goto("https://claude.ai/chat/00000000-0000-0000-0000-000000000000")
    
    # Wait a bit for the UI to load the error state
    await asyncio.sleep(2)
    
    # 2. Try to send a prompt using the automation function
    # This should fail if the automation doesn't auto-recover from this state
    try:
        print("Attempting to send prompt...")
        response = await send_prompt(page, "Hello, are you there?", model="auto")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Caught expected exception: {e}")
        # If we see "Conversation not found" or selector timeout, that's what we expect locally
        # But actually, send_prompt might succeed in typing but fail to get response, or fail to type.
        
    # Check if we are still on the bad URL
    if "chat/00000000-0000" in page.url:
        print("FAILURE: Still on invalid URL. Automation did not redirect to new chat.")
    else:
        print("SUCCESS: Automation seemingly recovered (or never got stuck).")

    await context.close()

if __name__ == "__main__":
    asyncio.run(reproduce())
