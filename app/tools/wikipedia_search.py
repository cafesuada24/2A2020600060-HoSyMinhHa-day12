import os
import requests
from dotenv import load_dotenv

load_dotenv()

def wikipedia_search(query: str) -> str:
    """
    Searches Wikipedia and returns a short summary of the top result.
    """
    url = os.getenv('WIKIPEDIA_URL')

    # ADDED: Custom User-Agent header required by Wikimedia API policies
    # Replace the email with your own contact info
    headers = {
        "User-Agent": f"MyReActAgent/1.0 ({os.getenv('WIKIPEDIA_USER_EMAIL')}) python-requests"
    }

    search_params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "utf8": 1,
        "srlimit": 1,
    }

    try:
        # ADDED: Pass the headers to the GET request
        response = requests.get(url, headers=headers, params=search_params, timeout=5)
        response.raise_for_status()
        search_data = response.json()

        results = search_data.get("query", {}).get("search", [])
        if not results:
            return f"Observation: No Wikipedia results found for '{query}'."

        best_title = results[0]["title"]

        extract_params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "exchars": 400,
            "exintro": True,
            "explaintext": True,
            "titles": best_title,
        }

        # ADDED: Pass the headers to the second GET request as well
        extract_response = requests.get(
            url, headers=headers, params=extract_params, timeout=5
        )
        extract_response.raise_for_status()
        extract_data = extract_response.json()

        pages = extract_data.get("query", {}).get("pages", {})
        for page_id, page_info in pages.items():
            if page_id == "-1":
                return f"Observation: Could not retrieve summary for '{best_title}'."

            extract = page_info.get("extract", "").strip()
            extract_clean = extract.replace("\n", " ")
            return f"Observation: [Page: {best_title}] {extract_clean}"

    except requests.exceptions.RequestException as e:
        return f"Observation: Error connecting to Wikipedia API: {str(e)}"

    return "Observation: Unknown error occurred during Wikipedia search."

