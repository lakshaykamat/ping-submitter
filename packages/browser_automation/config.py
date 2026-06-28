from dataclasses import dataclass


@dataclass(frozen=True)
class SkyvernSettings:
    base_url: str
    api_key: str
    max_steps: int = 50
    poll_interval_seconds: float = 5.0
    task_timeout_seconds: float = 3600.0
    record_session: bool = False

    @classmethod
    def from_mapping(cls, config):
        return cls(
            base_url=config["SKYVERN_BASE_URL"],
            api_key=config["SKYVERN_API_KEY"],
            max_steps=int(config.get("SKYVERN_MAX_STEPS", 50)),
            poll_interval_seconds=float(config.get("SKYVERN_POLL_INTERVAL_SECONDS", 5.0)),
            task_timeout_seconds=float(config.get("SKYVERN_TASK_TIMEOUT_SECONDS", 3600.0)),
            record_session=str(config.get("SKYVERN_RECORD_SESSION", "false")).lower() == "true",
        )
