#!/usr/bin/env python

import logging
import os.path
import platform
import subprocess
import sys
import time
from datetime import timedelta
import requests
from IPy import IP

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)-8s %(name)s: %(message)s",
    # format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    # datefmt="%Y-%m-%d %H:%M:%S,%s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        # logging.FileHandler("watchdog.log", mode="a"),
    ],
)

try:
    from rpi_rf import RFDevice
except Exception as importExc:
    error = "Can't import RFDevice, restart will not work:"
    logging.fatal(error, exc_info=importExc)

rf_on_code = 3323996
rf_off_code = 4099212
rf_protocol = 4
rf_pin = 17

last_restart_file = "last_restart.txt"

hosts = [
    "1.1.1.1",
    "8.8.8.8",
    "https://www.google.com",
    "https://www.amazon.com",
]
"""List of hosts to check"""

interval = 300
"""Interval in seconds between checks"""

threshold = 3
"""Threshold for number of failed attempts before triggering the event"""

timeout = 15
"""Timeout for HTTP requests in seconds"""

retries = 0
"""Number of hosts retries per check (0 = disabled)"""

retry_interval = 10
"""Interval in seconds between retries (ignored if retries = 0)"""

restart_duration = 300
"""Approximately the time the router needs to boot"""

min_restart_interval = 1800
"""Minimum duration between restarts"""


def read_last_restart():
    """Reads the timestamp of the last reboot from the file."""
    if os.path.exists(last_restart_file):
        try:
            with open(last_restart_file, "r") as f:
                line = f.readline()
                if len(line) > 0:
                    return float(line)
        except OSError as e:
            logging.exception("Failed to read last restart time", exc_info=e)
    return None


def save_last_restart():
    """Saves the timestamp of the last reboot into the file."""
    try:
        with open(last_restart_file, "w") as f:
            f.write(str(time.time()))
    except OSError as e:
        logging.exception("Failed to save last restart time", exc_info=e)


def restart():
    """Restarts the device by sending an OFF signal, waiting 10 seconds and sending an ON signal."""
    rf_device = None
    try:
        # Configure the RF transmitter
        rf_device = RFDevice(rf_pin)
        rf_device.enable_tx()

        # Send the OFF code
        rf_device.tx_code(rf_off_code, rf_protocol)

        # Wait time delay
        time.sleep(10)

        # Send the ON code
        rf_device.tx_code(rf_on_code, rf_protocol)
    except NameError as e:
        logging.warning("'RFDevice' not accessible", exc_info=e)
    finally:
        if rf_device is not None:
            rf_device.cleanup()


def send_single_signal(rf_code):
    """Send a single code over RF."""
    rf_device = None
    try:
        rf_device = RFDevice(rf_pin)
        rf_device.enable_tx()

        rf_device.tx_code(rf_code, rf_protocol)
    except NameError as e:
        logging.warning("'RFDevice' not accessible", exc_info=e)
    finally:
        if rf_device is not None:
            rf_device.cleanup()


def check_hosts():
    """Returns true if all hosts are considered down"""
    # If the threshold is reached, stop the loop
    for i in range(0, retries + 1):

        # Check the status of each host
        for host in hosts:
            if is_ip(host):
                if icmp_ping(host):
                    return False
            else:
                if http_ping(host):
                    return False

        if i < retries:
            logging.debug("No host was reachable, {}. retry in {} seconds".format(i + 1, retry_interval))
            # Sleep for the specified interval before checking again
            time.sleep(retry_interval)

    return True


def is_ip(host):
    try:
        IP(host)
    except ValueError:
        return False
    return True


def http_ping(host):
    try:
        # noinspection PyUnusedLocal
        r = requests.get(host, timeout=timeout)
        # Check the status code and content type of the response
        # if r.status_code == 200 and r.headers["Content-Type"].startswith("text/html"):
        #     return False
        logging.info("{} is reachable".format(host))
        return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        logging.warning("{} couldn't be reached:\n{}".format(host, str(e)))
    return False


def icmp_ping(host):
    """
    Returns True if host responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
    """

    # Option for the number of packets as a function of
    param_packets = "-n" if platform.system().lower() == "windows" else "-c"
    param_timeout = "-w" if platform.system().lower() == "windows" else "-W"

    # Building the command. Ex: "ping -c 1 google.com"
    command = ["ping", param_packets, "1", param_timeout, str(timeout), host]

    logging.info("Executing command: '{}'".format(" ".join(command)))
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    logging.info("--------------------SUBPROCESS STARTED---------------------")
    if result.returncode == 0:
        for line in result.stdout.decode().splitlines():
            logging.info(line)
    else:
        for line in result.stderr.decode().splitlines():
            logging.error(line)
    logging.info("--------------------SUBPROCESS STOPPED---------------------")

    return result.returncode == 0


def check_periodically():
    failed_attempts = 0
    while True:
        # Check the status of each host
        all_down = check_hosts()

        # If all hosts are down, trigger event
        if all_down:
            failed_attempts += 1

            logging.error(
                "All hosts are unreachable at {}, failed attempts: {}".format(time.ctime(), failed_attempts))

            if failed_attempts >= threshold:
                last_restart = read_last_restart()
                delta_since_last_restart = None if last_restart is None else timedelta(
                    seconds=time.time() - last_restart)
                if last_restart is None or (delta_since_last_restart.total_seconds() >= min_restart_interval):
                    logging.info("Restarting...")
                    restart()
                    save_last_restart()
                    logging.info("Restarted, waiting {} seconds for completion of reboot...".format(restart_duration))
                    failed_attempts = 0
                    time.sleep(restart_duration)
                else:
                    logging.warning("Restart skipped, last reboot is less than {} seconds ago.".format(
                        min_restart_interval))
        else:
            failed_attempts = 0

        logging.info("Next check in {} seconds...".format(interval))
        # Sleep for the specified interval before checking again
        time.sleep(interval)


def main() -> int:
    try:
        # Send initial ON code to (re-)enable the socket, if it was turned off
        # or perhaps didn't turn on after a power loss.
        logging.info("Sending initial on")
        send_single_signal(rf_on_code)

        logging.info("Starting host checks...")
        check_periodically()
    except KeyboardInterrupt:
        logging.info("Exiting...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
