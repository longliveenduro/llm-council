import re

def clean_model_name(name: str) -> str:
    """
    Normalizes model names for the leaderboard and UI.
    - Removes 'Thinking' suffixes (including variants like '(Ext) Thinking', '[Ext. Thinking]')
    - Normalizes 'Chat GPT' to 'ChatGPT'
    - Strips whitespace
    """
    if not name:
        return name
        
    # Normalize 'Chat GPT' (case-insensitive) to 'ChatGPT'
    name = re.sub(r"Chat\s*GPT", "ChatGPT", name, flags=re.IGNORECASE)
    
    # Remove standard thinking suffixes
    # Patterns: 
    # - " Thinking"
    # - " (Ext) Thinking"
    # - " [Ext. Thinking]"
    # - " [Thinking]"
    # - " (Thinking)"
    suffixes = [
        r"\s*\(Ext\)\s*Thinking",
        r"\s*\[Ext\.\s*Thinking\]",
        r"\s*\[Thinking\]",
        r"\s*\(Thinking\)",
        r"\s+Thinking$"
    ]
    
    clean_name = name
    for pattern in suffixes:
        clean_name = re.sub(pattern, "", clean_name, flags=re.IGNORECASE)
        
    return clean_name.strip()
