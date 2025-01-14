import logging
from datetime import datetime, timedelta

from opennem import settings
from opennem.clients.slack import slack_message
from opennem.core.networks import network_from_network_code
from opennem.utils.dates import chop_delta_microseconds, parse_date
from opennem.utils.http import http

logger = logging.getLogger("opennem.monitors.opennem")


def check_opennem_interval_delays(network_code: str) -> bool:
    """Runs periodically and alerts if there is a current delay in output of power intervals"""
    network = network_from_network_code(network_code)

    if not network or not network.code:
        raise Exception(f"Could not run check interval for network code: {network_code}")

    env = ""

    if settings.debug:
        env = ".dev"

    url = f"https://data{env}.opennem.org.au/v3/stats/au/{network.code}/power/7d.json"

    resp = http.get(url)

    if resp.status_code != 200 or not resp.ok:
        logger.error(f"Error retrieving: {url}")
        return False

    resp_json = resp.json()

    if "data" not in resp_json:
        logger.error("Error retrieving wem power: malformed response")
        return False

    data = resp_json["data"]

    fueltech_data = data.pop()

    history_end_date = fueltech_data["history"]["last"]

    history_date = parse_date(history_end_date, dayfirst=False)

    if not history_date:
        logger.error("Could not read history date for opennem interval monitor")
        return False

    now_date = datetime.now().astimezone(network.get_timezone())  # type: ignore

    time_delta = chop_delta_microseconds(now_date - history_date) - timedelta(minutes=network.interval_size)

    logger.debug(f"Live time: {history_date},  delay: {time_delta}")

    alert_threshold = network.monitor_interval_alert_threshold or settings.monitor_interval_alert_threshold or 60

    if time_delta > timedelta(minutes=alert_threshold):
        slack_message(
            f"[{settings.env}] *WARNING*: OpenNEM {network.code} " f"interval delay on {settings.env} currently: {time_delta}.\n",
            tag_users=settings.monitoring_alert_slack_user,
        )

    return True


if __name__ == "__main__":
    for network_code in ["NEM", "WEM"]:
        check_opennem_interval_delays(network_code)
