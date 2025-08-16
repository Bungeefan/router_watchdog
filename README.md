# Router Watchdog

Router Watchdog script for Raspberry Pi using [rpi-rf](https://github.com/milaq/rpi-rf).

This script checks periodically a list of hosts and tries to connect to them, either via HTTP request or ICMP ping.

If there is repeatedly no working connection detected, the Raspberry Pi uses an 433Mhz sender to first disable and
then re-enable a wireless socket.

## Install

```sh
cd router_watchdog/
```

### Install dependencies (in venv)

```sh
sh install_dependencies.sh
```

## Run

### Manually (without service)

```sh
python3 router_watchdog.py
```

### Service

#### Enable and start service

```sh
sudo systemctl enable $(/bin/readlink -f router-watchdog.service)
sudo systemctl start router-watchdog.service
```

---

### Helpful resources:

* https://www.instructables.com/Super-Simple-Raspberry-Pi-433MHz-Home-Automation/
* https://github.com/sui77/rc-switch/issues/103

---

### Developer Notes:

#### Upgrade dependencies

```sh
python3 -m pip freeze > requirements.txt
```
