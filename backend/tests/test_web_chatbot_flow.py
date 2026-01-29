from fastapi.testclient import TestClient
from backend.main import app

def test_web_chatbot_flow():
    client = TestClient(app)
    
    # 1. Test Stage 2 Prompt Generation
    query = "What is the capital of France?"
    stage1_results = [
        {"model": "Model A", "response": "Paris"},
        {"model": "Model B", "response": "The capital is Paris."}
    ]
    
    response = client.post(
        "/api/web-chatbot/stage2-prompt",
        json={"user_query": query, "stage1_results": stage1_results}
    )
    assert response.status_code == 200
    data = response.json()
    assert "Response A1" in data["prompt"]
    assert "Response B1" in data["prompt"]
    assert "Model A" == data["label_to_model"]["Response A1"]
    
    label_to_model = data["label_to_model"]

    # 2. Test Processing Rankings
    stage2_results = [
        {"model": "Model A", "ranking": "FINAL RANKING:\n1. Response B1\n2. Response A1"},
        {"model": "Model B", "ranking": "FINAL RANKING: 1. Response A1. 2. Response B1"}
    ]
    
    response = client.post(
        "/api/web-chatbot/process-rankings",
        json={"stage2_results": stage2_results, "label_to_model": label_to_model}
    )
    assert response.status_code == 200
    data = response.json()
    
    processed = data["stage2_results"]
    assert len(processed) == 2
    assert processed[0]["parsed_ranking"] == ["Response B1", "Response A1"]

    # 3. Test Stage 3 Prompt Generation
    response = client.post(
        "/api/web-chatbot/stage3-prompt",
        json={
            "user_query": query,
            "stage1_results": stage1_results,
            "stage2_results": processed
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "STAGE 1" in data["prompt"]
    assert "STAGE 2" in data["prompt"]

    # 4. Test Saving Web ChatBot Message with Title
    # First create a conversation
    resp = client.post("/api/conversations", json={})
    conv_id = resp.json()["id"]
    
    manual_title = "Manual Override Title"
    manual_message_data = {
        "user_query": query,
        "stage1": stage1_results,
        "stage2": processed,
        "stage3": {"model": "Chairman", "response": "Final Answer is Paris."},
        "metadata": {"label_to_model": label_to_model},
        "title": manual_title
    }
    
    response = client.post(
        f"/api/conversations/{conv_id}/message/web-chatbot",
        json=manual_message_data
    )
    assert response.status_code == 200
    
    # Verify it's in the conversation AND title is set
    resp = client.get(f"/api/conversations/{conv_id}")
    conv_data = resp.json()
    messages = conv_data["messages"]
    
    assert len(messages) == 2 # User + Assistant
    assert messages[1]["role"] == "assistant"
    assert messages[1]["stage3"]["response"] == "Final Answer is Paris."
    assert conv_data["title"] == manual_title
