import os
from datetime import datetime

import requests
from ddgs import DDGS

ddgs = DDGS()
def web_search(query: str) -> str:
    """Search the web using Brave Search API. Returns top 3 snippets."""
    res = ddgs.text(query, max_results=5)
    return "\n".join(t['body'] for t in res)

def calculator(expression: str) -> str:
    """Evaluate a math expression safely. E.g., calculator[150000 * 2 + 50000]."""
    try:
        # Only allow safe math operations
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return f"Error: Invalid characters in expression: {expression}"
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Calculation error: {str(e)}"


def get_system_time(ignore: object) -> str:
    """Returns the current date and day of week."""
    now = datetime.now()
    return now.strftime("%A, %B %d, %Y")
