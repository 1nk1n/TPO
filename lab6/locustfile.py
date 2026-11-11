"""Locust scenarios for laboratory work 6: OpenBMC and public APIs."""

import os

import urllib3
from locust import HttpUser, between, task

from lab6_validation import (
    validate_posts_payload,
    validate_system_payload,
    validate_weather_payload,
)


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OPENBMC_URL = os.getenv("OPENBMC_URL", "https://127.0.0.1:2443").rstrip("/")
OPENBMC_USERNAME = os.getenv("OPENBMC_USERNAME", "root")
OPENBMC_PASSWORD = os.getenv("OPENBMC_PASSWORD", "0penBmc")


def _check_json_response(response, validator) -> None:
    if response.status_code != 200:
        response.failure(f"expected HTTP 200, received {response.status_code}")
        return
    try:
        validator(response.json())
    except (ValueError, TypeError) as error:
        response.failure(str(error))


class OpenBMCUser(HttpUser):
    host = OPENBMC_URL
    wait_time = between(1, 3)

    @task(2)
    def get_system_information(self):
        with self.client.get(
            "/redfish/v1/Systems/system",
            auth=(OPENBMC_USERNAME, OPENBMC_PASSWORD),
            verify=False,
            name="OpenBMC system information",
            catch_response=True,
        ) as response:
            _check_json_response(response, validate_system_payload)

    @task(2)
    def get_power_state(self):
        with self.client.get(
            "/redfish/v1/Systems/system",
            auth=(OPENBMC_USERNAME, OPENBMC_PASSWORD),
            verify=False,
            name="OpenBMC PowerState",
            catch_response=True,
        ) as response:
            _check_json_response(response, validate_system_payload)


class PublicAPIUser(HttpUser):
    host = "https://jsonplaceholder.typicode.com"
    wait_time = between(1, 3)

    @task
    def get_posts(self):
        with self.client.get(
            "/posts",
            name="JSONPlaceholder posts",
            catch_response=True,
        ) as response:
            _check_json_response(response, validate_posts_payload)

    @task
    def get_weather(self):
        with self.client.get(
            "https://wttr.in/Novosibirsk?format=j1",
            name="wttr.in weather",
            catch_response=True,
        ) as response:
            _check_json_response(response, validate_weather_payload)
