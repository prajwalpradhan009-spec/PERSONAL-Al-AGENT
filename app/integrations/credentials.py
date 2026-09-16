"""
Credentials Manager
Centralized loading / validation of third-party API credentials stored in
`config.json` under the `credentials` block. Keeping secrets in one place lets
the integration modules degrade gracefully to non-API fallbacks when a credential
is not yet configured.

NEVER log or return token values. Only expose boolean availability flags.
"""

from typing import Dict, Any, Tuple, Optional

from app.core.config import load_config


def get_credentials() -> Dict[str, Any]:
    """Returns the full credentials block from the saved configuration."""
    config = load_config()
    creds = config.get("credentials") or {}
    return dict(creds)


def get_setting(key: str) -> Optional[str]:
    """Returns a single credential value or None."""
    creds = get_credentials()
    value = creds.get(key)
    return value if value else None


def is_configured(*keys: str) -> bool:
    """Returns True when ALL of the given credential keys are populated."""
    creds = get_credentials()
    return all(bool(creds.get(k)) for k in keys)


def describe_status() -> Dict[str, bool]:
    """Reports which integrations have the credentials needed for full API mode."""
    return {
        "spotify_api": is_configured("spotify_client_id", "spotify_client_secret"),
        "github_api": is_configured("github_token"),
        "google_api": is_configured("google_client_secrets_path"),
        "discord_api": is_configured("discord_bot_token"),
        "youtube_api": is_configured("youtube_api_key"),
    }


def missing_for(key: str) -> Tuple[bool, str]:
    """
    Helper returning (configured, explanation).
    When not configured, returns a developer-friendly hint about where to add the key.
    """
    configured = is_configured(key)
    if configured:
        return True, ""
    return False, (
        f"'{key}' is not configured. Add it under the 'credentials' block of "
        f"config.json (see README Integrations section) and restart the agent."
    )