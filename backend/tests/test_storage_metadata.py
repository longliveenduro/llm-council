import uuid
from backend import storage

def test_storage_metadata_persistence():
    conv_id = f"test-{uuid.uuid4()}"
    storage.create_conversation(conv_id)
    
    stage1 = [{"model": "model_a", "response": "resp_a"}]
    stage2 = [{"model": "model_b", "ranking": "rank_b"}]
    stage3 = {"model": "model_c", "response": "resp_c"}
    metadata = {"label_to_model": {"Response A": "model_a"}, "test": "passed"}
    
    storage.add_assistant_message(conv_id, stage1, stage2, stage3, metadata)
    
    conv = storage.get_conversation(conv_id)
    last_msg = conv["messages"][-1]
    saved_metadata = last_msg.get("metadata")
    
    assert saved_metadata == metadata
    
    # Clean up
    storage.delete_conversation(conv_id)
