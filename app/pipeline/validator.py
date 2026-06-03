def clean_json_response(response: str) -> str:
    """Strip markdown code fences if the model wraps the JSON despite instructions."""
    response = response.strip()
    if response.startswith("```"):
        # Remove opening fence (handles ```json, ```JSON, ``` etc.)
        response = response.split("\n", 1)[-1]
    if response.endswith("```"):
        # Remove closing fence
        response = response.rsplit("```", 1)[0]
    return response.strip()
