"""Async helper functions for MQTT subscriber message persistence."""

from datetime import datetime as dt
import os
from typing import Any, Awaitable, Callable

import pytz


async def process_message(
    message: Any,
    topic_values: dict[str, float],
    all_topics: set[str],
    row_ready: dict[str, float],
    update_csv_fn: Callable[[str, dict[str, float], str, str, str], Awaitable[None]],
    csv_file: str,
    measure: str,
) -> None:
    """Decode one MQTT message and delegate CSV persistence."""
    topic = message.topic
    value = float(message.payload.decode())
    local_tz = pytz.timezone("America/Sao_Paulo")
    timestamp = dt.now(local_tz).strftime("%m-%d-%Y %H:%M:%S")

    topic_values[topic] = value
    all_topics.add(topic)
    row_ready[topic] = value

    await update_csv_fn(timestamp, row_ready, topic, csv_file, measure)


async def update_csv(
    timestamp: str,
    row_ready: dict[str, float],
    topic: str,
    csv_file: str,
    measure: str,
) -> None:
    """Append a single CSV row for the current message topic and value."""
    if not os.path.exists(csv_file):
        header = ["timestamp", "point", measure]
        with open(csv_file, "a", encoding="utf-8") as file:
            file.write(",".join(header) + "\n")

    row = [timestamp, str(topic.split("/")[-1]), str(row_ready.get(topic, ""))]
    with open(csv_file, "a", encoding="utf-8") as file:
        file.write(",".join(row) + "\n")

    row_ready.clear()
