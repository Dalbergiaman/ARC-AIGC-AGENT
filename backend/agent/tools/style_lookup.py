from langchain_core.tools import tool

from agent.tools.prompt_templates import StyleKeywords, get_style, list_styles


@tool
def lookup_style_keywords(style: str) -> dict:
    """Query the local style keyword library for a given architectural style.

    Returns positive/negative keywords and mood description.
    If the style is not found, returns an empty result with available styles listed.
    """
    result = get_style(style)
    if result is None:
        return {
            "found": False,
            "style": style,
            "positive": [],
            "negative": [],
            "mood": "",
            "available_styles": list_styles(),
        }
    return {
        "found": True,
        **result,
    }
