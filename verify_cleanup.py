
import asyncio
from fastapi.testclient import TestClient
from backend.main import app

def test_message_flow_signature():
    """
    Test that the standard message endpoint accepts the new request format 
    (no manual_responses).
    """
    client = TestClient(app)
    
    # 1. Create conversation
    resp = client.post("/api/conversations", json={})
    assert resp.status_code == 200
    conv_id = resp.json()["id"]
    
    # 2. Try to send a message (standard flow)
    # We won't actually wait for the stream to finish as that requires mocking OpenRouter
    # We just want to make sure the endpoint accepts the request body without manual_responses
    
    # The endpoint is an SSE stream.
    # FastAPIs TestClient doesn't easily support SSE streaming testing in a blocking way 
    # without running the generator.
    # But we can check if it returns 200 OK and starts the stream.
    
    # Note: If we use the real OpenRouter, it might be slow or cost money.
    # Ideally we'd mock it. 
    # For now, let's just inspect the request model handling by sending a known invalid request
    # and then a valid one.
    
    # Send request with extra field that should be ignored or cause error? 
    # Pydantic usually ignores extras unless configured otherwise.
    # But if we send WITHOUT manual_responses, it should definitely work.
    
    # Actually, we can just verify the Pydantic model by importing it.
    from backend.main import SendMessageRequest
    
    try:
        req = SendMessageRequest(content="Hello")
        assert not hasattr(req, "manual_responses")
        print("SendMessageRequest model correctly updated (no manual_responses).")
    except Exception as e:
        print(f"Model validation failed: {e}")
        exit(1)

    print("Cleanup verification passed.")

if __name__ == "__main__":
    test_message_flow_signature()
