
import os
import sys
import uuid
from backend import storage

def verify():
    conv_id = f"test-{uuid.uuid4()}"
    print(f"Creating test conversation {conv_id}...")
    storage.create_conversation(conv_id)
    
    stage1 = [{"model": "model_a", "response": "resp_a"}]
    stage2 = [{"model": "model_b", "ranking": "rank_b"}]
    stage3 = {"model": "model_c", "response": "resp_c"}
    metadata = {"label_to_model": {"Response A": "model_a"}, "test": "passed"}
    
    print("Adding assistant message with metadata...")
    storage.add_assistant_message(conv_id, stage1, stage2, stage3, metadata)
    
    print("Loading conversation back...")
    conv = storage.get_conversation(conv_id)
    
    last_msg = conv["messages"][-1]
    saved_metadata = last_msg.get("metadata")
    
    print(f"Saved Metadata: {saved_metadata}")
    
    if saved_metadata == metadata:
        print("\n✅ Metadata persistence verified successfully!")
    else:
        print("\n❌ Metadata persistence verification failed!")
        sys.exit(1)
    
    # Clean up
    storage.delete_conversation(conv_id)
    print(f"Cleaned up test conversation {conv_id}")

if __name__ == "__main__":
    verify()
