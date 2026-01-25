import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

@pytest.fixture(autouse=True)
def isolated_test_data():
    """
    Fixture that redirects all data persistence to a temporary directory.
    Runs automatically for all tests.
    """
    # Create a temporary directory
    tmp_dir = tempfile.mkdtemp()
    
    # Define subdirectories
    conv_dir = os.path.join(tmp_dir, "conversations")
    images_dir = os.path.join(tmp_dir, "images")
    os.makedirs(conv_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    
    scores_file = os.path.join(tmp_dir, "model_scores.json")

    # Patch the constants where they are USED
    with patch("backend.storage.DATA_DIR", conv_dir), \
         patch("backend.scores.DATA_DIR", conv_dir), \
         patch("backend.scores.SCORES_FILE", scores_file), \
         patch("backend.main.IMAGES_DIR", Path(images_dir)):
        
        yield
        
    # Clean up the temporary directory after the test
    shutil.rmtree(tmp_dir)
