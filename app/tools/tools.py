from collections.abc import Callable

from app.tools.calculator import calculator
from app.tools.websearch import get_system_time, web_search
from app.tools.wikipedia_search import wikipedia_search


def get_tool_descriptions() -> list[dict[str, str | Callable[..., str]]]:
    return [
        {
            'name': 'wikipedia_search',
            'description': 'A wrapper around Wikipedia. Useful for when you need to answer general questions about people, places, companies, facts, historical events, or other subjects. Input should be a search query.',
            'func': wikipedia_search,
        },
        {
            'name': 'web_search',
            'description': (
                'Search the web for real-time information using Brave Search API. '
                'Use this for weather forecasts, ticket prices, hotel prices, travel blogs, '
                'restaurant recommendations, and any current data. '
                'Input: a search query string. Output: top 3 result snippets.'
            ),
            'func': web_search,
        },
        {
            'name': 'calculator',
            'description': (
                'Evaluate a mathematical expression to get an exact numeric result. '
                'Use this for budget calculations, total cost estimates, unit conversions. '
                "Input: a math expression (e.g., '150000 * 2 + 50000'). Output: the result."
            ),
            'func': calculator,
        },
        {
            'name': 'get_system_time',
            'description': (
                "Get today's date and day of the week. "
                'Use this to determine the current date for planning trips, '
                "calculating 'next weekend', or checking seasonal weather. "
                'Input: none. Output: current date string.'
            ),
            'func': get_system_time,
        },
    ]
