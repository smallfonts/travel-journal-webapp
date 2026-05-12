"""App configuration — loaded from environment variables."""
import os

class Settings:
    # Paths
    VAULT_PATH: str = os.getenv(
        "TRAVEL_JOURNAL_VAULT_PATH",
        "/home/cube/Dropbox/Apps/remotely-save/WeeksObsidianVault"
    )
    CACHE_IMAGES: str = os.getenv(
        "TRAVEL_JOURNAL_CACHE_IMAGES",
        "/home/cube/.hermes/profiles/journal/cache/images"
    )
    CACHE_VIDEOS: str = os.getenv(
        "TRAVEL_JOURNAL_CACHE_VIDEOS",
        "/home/cube/.hermes/profiles/journal/cache/videos"
    )

    # Vault sub-paths
    TEMPLATE_NAME: str = "Travel Journal Entry Daily Template (YYYY-MM-DD).md"

    @property
    def template_path(self) -> str:
        return os.path.join(self.VAULT_PATH, "Travel", self.TEMPLATE_NAME)

    @property
    def travel_folder(self) -> str:
        return os.path.join(self.VAULT_PATH, "Travel")

settings = Settings()