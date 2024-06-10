from datetime import datetime
import json
import time
from glinet import GlInetClient
from rpc import RPCUnauthorized

with open("config.json", "r") as d:
    config_json = json.loads(d.read())

password = config_json["password"]
log_path = config_json.get("log_file", "log.txt")

client = GlInetClient()
client.login(password)

while True:
    system_status = client.get_system_status()
    # print(system_status)
    # print(get_tethering_status(system_status))
    # print(get_ethernet_status(system_status))

    # Log which one is true
    try:
        tethering = client.get_tethering_status(system_status)
        ethernet = client.get_ethernet_status(system_status)
    except RPCUnauthorized():
        client.login(password)
        continue

    log_entry = json.dumps({
        "timestamp": datetime.now().isoformat(),
        "tethering": {"available": tethering.up, "used": tethering.online},
        "ethernet": {"available": ethernet.up, "used": ethernet.online},
    })

    print(log_entry)

    f = open(log_path, mode="a")
    f.write(log_entry)
    f.write("\n")
    f.close()

    try:
        time.sleep(60)
    except KeyboardInterrupt:
        break
