"""Validation helpers shared by the laboratory 6 Locust scenarios."""


def validate_system_payload(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("OpenBMC system response must be a JSON object")
    if not isinstance(payload.get("PowerState"), str) or not payload["PowerState"]:
        raise ValueError("OpenBMC system response has no PowerState")


def validate_posts_payload(payload: object) -> None:
    if not isinstance(payload, list):
        raise ValueError("JSONPlaceholder response must be a list of posts")


def validate_weather_payload(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("wttr.in response must be a JSON object")
    conditions = payload.get("current_condition")
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("wttr.in response has no current_condition data")
