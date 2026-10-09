"""Environment-backed runtime configuration."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    region: str = os.getenv("AWS_REGION", "ap-southeast-1")
    identity_store_id: str = os.getenv("IDENTITY_STORE_ID", "")
    access_sessions_table: str = os.getenv("ACCESS_SESSIONS_TABLE", "")
    approval_tokens_table: str = os.getenv("APPROVAL_TOKENS_TABLE", "")
    access_group_mapping_secret: str = os.getenv("ACCESS_GROUP_MAPPING_SECRET", "")
    jira_credentials_secret: str = os.getenv("JIRA_CREDENTIALS_SECRET", "")
    webhook_auth_secret: str = os.getenv("WEBHOOK_AUTH_SECRET", "")
    token_secret_name: str = os.getenv("TOKEN_SECRET_NAME", "")
    ses_sender_email: str = os.getenv("SES_SENDER_EMAIL", "")
    portal_url: str = os.getenv("IDENTITY_CENTER_PORTAL_URL", "")
    approval_base_url: str = os.getenv("APPROVAL_BASE_URL", "")
    require_hmac: bool = os.getenv("REQUIRE_HMAC", "true").lower() == "true"
    access_group_prefix: str = os.getenv("ACCESS_GROUP_PREFIX", "pa-")
    token_ttl_hours: int = int(os.getenv("TOKEN_TTL_HOURS", "24"))


settings = Settings()
