from __future__ import annotations

import logging

from config import load_config


def main() -> None:
    """Application entrypoint.

    VK transport/startup is intentionally kept for the VK API stage.
    Configuration is validated here before the transport is started.
    """
    config = load_config()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    logging.info(
        "VK-Moderator entrypoint initialized for group %s (API %s).",
        config.group_id,
        config.api_version,
    )
    logging.info(
        "VK transport is configured in the next integration stage."
    )


if __name__ == "__main__":
    main()
