"""MQTT subscriber entrypoint for collecting and storing measure streams."""

import asyncio
from asyncio import AbstractEventLoop
from datetime import datetime as dt
import os

import paho.mqtt.client as mqtt
import pytz

from s_functions import process_message, update_csv


BROKER = "mqtt-broker"
PORT = 1883
TOPIC_PREFIX = "measures/#"
READINGS_DIR = "/app/subscriber/readings"
os.makedirs(READINGS_DIR, exist_ok=True)

LOCAL_TZ = pytz.timezone("America/Sao_Paulo")
START_TIME = dt.now(LOCAL_TZ).strftime("%m-%d-%Y_(%Hh%Mm)")

topic_values: dict[str, float] = {}
all_topics: set[str] = set()
row_ready: dict[str, float] = {}
loop: AbstractEventLoop | None = None


def on_message(client, userdata, message) -> None:
    """Route incoming messages to a measure-specific CSV file."""
    if loop is None:
        # Messages received before asyncio loop initialization are ignored.
        return

    if "current" in message.topic:
        measure = "current"
        csv_file = os.path.join(READINGS_DIR, f"current_{START_TIME}.csv")
    elif "voltage" in message.topic:
        measure = "voltage"
        csv_file = os.path.join(READINGS_DIR, f"voltage_{START_TIME}.csv")
    elif "consumption" in message.topic:
        measure = "consumption"
        csv_file = os.path.join(READINGS_DIR, f"consumption_{START_TIME}.csv")
    else:
        print(f"Unknown topic: {message.topic}")
        return

    asyncio.run_coroutine_threadsafe(
        process_message(
            message,
            topic_values,
            all_topics,
            row_ready,
            update_csv,
            csv_file,
            measure,
        ),
        loop,
    )


client = mqtt.Client()
client.on_message = on_message
client.connect(BROKER, PORT)
client.subscribe(TOPIC_PREFIX)


async def main() -> None:
    """Start asyncio loop used by MQTT callback coroutine dispatch."""
    global loop
    loop = asyncio.get_running_loop()
    await asyncio.Event().wait()


client.loop_start()
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Shutting down...")
finally:
    client.loop_stop()
    client.disconnect()



