"""
Index mapping for different book titles to their corresponding OpenSearch indices.

This file maps book titles to their specific OpenSearch index names.
When the API receives a request with a title, it will use this mapping
to query the correct index for that book's content.
"""

index_map = {
    "An Invitation to Health": "chunk_357973585",
    "Steps to writing well": "chunk_1337899796"
}

def get_index_for_title(title: str) -> str:
    """
    Get the OpenSearch index name for a given book title.
    
    Args:
        title (str): The book title
        
    Returns:
        str: The corresponding OpenSearch index name
        
    Raises:
        ValueError: If the title is not found in the mapping
    """
    if title in index_map:
        return index_map[title]
    else:
        # Return available titles for error message
        available_titles = list(index_map.keys())
        raise ValueError(f"Title '{title}' not found. Available titles: {available_titles}")

def get_available_titles():
    """
    Get all available book titles.
    
    Returns:
        list: List of available book titles
    """
    return list(index_map.keys())
