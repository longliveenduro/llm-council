
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import os
import sys

# Ensure backend modules are importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend import council

# Mock process object
def get_mock_process():
    proc = AsyncMock()
    proc.communicate.return_value = (b"", b"")
    proc.returncode = 0
    return proc

@pytest.mark.asyncio
async def test_council_passes_image_argument_chatgpt():
    # We patch create_subprocess_exec with an AsyncMock that returns our mock process
    with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = get_mock_process()
        
        with patch('backend.council._save_temp_image', return_value='/tmp/mock_image.png'):
            await council.run_chatgpt_automation("test prompt", image_base64="fake_base64")
            
            # Verify the command called
            # call_args[0] contains the positional arguments (program, args...)
            call_args = mock_exec.call_args[0]
            # args[0] is 'python3', args[1] is script path, args[2...] are script args
            
            # Flatten arguments if they are passed as separate args
            flat_args = []
            for arg in call_args:
                 flat_args.append(str(arg))
            
            print(f"ChatGPT Call Args: {flat_args}")
            assert "--image" in flat_args
            assert "/tmp/mock_image.png" in flat_args

@pytest.mark.asyncio
async def test_council_passes_image_argument_claude():
    with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = get_mock_process()
        
        with patch('backend.council._save_temp_image', return_value='/tmp/mock_image.png'):
            await council.run_claude_automation("test prompt", image_base64="fake_base64")
            
            flat_args = [str(arg) for arg in mock_exec.call_args[0]]
            print(f"Claude Call Args: {flat_args}")
            assert "--image" in flat_args
            assert "/tmp/mock_image.png" in flat_args

@pytest.mark.asyncio
async def test_council_passes_image_argument_ai_studio():
    with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = get_mock_process()
        
        with patch('backend.council._save_temp_image', return_value='/tmp/mock_image.png'):
            await council.run_ai_studio_automation("test prompt", image_base64="fake_base64")
            
            flat_args = [str(arg) for arg in mock_exec.call_args[0]]
            print(f"AI Studio Call Args: {flat_args}")
            assert "--image" in flat_args
            assert "/tmp/mock_image.png" in flat_args
