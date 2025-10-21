"""
Helper functions to parse player data from ESPN API
"""
import re
from typing import Optional, Dict, Any
from datetime import datetime, date


def parse_height_to_inches(height_str: Optional[str]) -> Optional[int]:
    """
    Convert ESPN height string to total inches.
    Examples: "6-2" -> 74, "5-11" -> 71
    Can also handle numeric values (assumes centimeters, converts to inches)
    """
    if not height_str:
        return None

    try:
        # If it's a number (float or int), assume it's centimeters and convert
        if isinstance(height_str, (int, float)):
            # Convert cm to inches (1 cm = 0.393701 inches)
            return int(height_str * 0.393701)

        # Convert to string for parsing
        height_str = str(height_str).strip()

        # Handle format like "6-2" or "6'2"
        if '-' in height_str:
            feet, inches = height_str.split('-')
        elif "'" in height_str:
            feet, inches = height_str.replace('"', '').split("'")
        else:
            # Try to parse as just inches or cm
            num = float(height_str)
            # If greater than 100, assume it's cm
            if num > 100:
                return int(num * 0.393701)
            else:
                return int(num)

        feet = int(feet.strip())
        inches = int(inches.strip())
        return (feet * 12) + inches

    except (ValueError, AttributeError, TypeError):
        return None


def parse_weight_to_pounds(weight_str: Optional[str]) -> Optional[int]:
    """
    Convert ESPN weight to integer pounds.
    Examples: "200" -> 200, "185 lbs" -> 185
    Can also handle numeric values (assumes kilograms if < 200, converts to pounds)
    """
    if not weight_str:
        return None

    try:
        # If it's already a number
        if isinstance(weight_str, (int, float)):
            # If less than 200, assume it's kg and convert to lbs (1 kg = 2.20462 lbs)
            if weight_str < 200:
                return int(weight_str * 2.20462)
            else:
                return int(weight_str)

        # Remove "lbs", "lb", "kg" and any non-digit characters
        weight_clean = re.sub(r'[^\d.]', '', str(weight_str))
        if not weight_clean:
            return None

        weight = float(weight_clean)
        # If less than 200, assume it's kg
        if weight < 200:
            return int(weight * 2.20462)
        else:
            return int(weight)

    except (ValueError, AttributeError, TypeError):
        return None


def parse_birth_date(date_str: Optional[str]) -> Optional[date]:
    """
    Parse birth date from ESPN format to Python date object.
    ESPN typically returns dates in ISO format.
    Returns a date object for PostgreSQL DATE column compatibility.
    """
    if not date_str:
        return None

    try:
        # Try parsing ISO format
        if 'T' in date_str:
            date_str = date_str.split('T')[0]

        # Parse and return as date object
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.date()
    except (ValueError, AttributeError, TypeError):
        return None


def parse_player_data(athlete: Dict[str, Any], team_id: int) -> Dict[str, Any]:
    """
    Parse ESPN athlete data into our database format.

    Args:
        athlete: Raw athlete data from ESPN API
        team_id: The database team_id this player belongs to

    Returns:
        Dictionary with properly formatted player data
    """
    # Parse height and weight
    height_inches = parse_height_to_inches(athlete.get("height"))
    weight_pounds = parse_weight_to_pounds(athlete.get("weight"))
    birth_date = parse_birth_date(athlete.get("dateOfBirth"))

    # Get experience years
    experience = athlete.get("experience", {})
    experience_years = None
    if isinstance(experience, dict):
        experience_years = experience.get("years")
    elif isinstance(experience, int):
        experience_years = experience

    # Build the player record
    player_record = {
        "displayName": athlete.get("displayName") or athlete.get("name") or f"Player {athlete.get('id', 'Unknown')}",
        "position": athlete.get("position", {}).get("abbreviation") if isinstance(athlete.get("position"), dict) else athlete.get("position"),
        "jersey": athlete.get("jersey"),
        "team_id": team_id,
        "height_inches": height_inches,
        "weight_pounds": weight_pounds,
        "birth_date": birth_date,
        "metadata": {
            "headshot": athlete.get("headshot", {}).get("href") if isinstance(athlete.get("headshot"), dict) else athlete.get("headshot"),
            "slug": athlete.get("slug"),
            "age": athlete.get("age"),
            "experience_years": experience_years,
            "college": athlete.get("college", {}).get("name") if isinstance(athlete.get("college"), dict) else None,
            "birthplace": athlete.get("birthPlace"),
        }
    }

    return player_record
