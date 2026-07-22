"""Production entry point for the offline Vikzar compute application."""

from __future__ import annotations


def main() -> None:
    """Load validated environment settings and run the local API node."""

    import uvicorn

    from app.api.configuration import APISettings

    settings = APISettings.from_environment()
    uvicorn.run(
        "app.api.server:create_app_from_environment",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
