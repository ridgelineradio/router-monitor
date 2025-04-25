from datetime import datetime
import json
import time
import sys
import os
import servicemanager
import win32event
import win32service
import win32serviceutil
from glinet import GlInetClient
from rpc import RPCUnauthorized


def get_data_path(filename: str) -> str:
    exe_dir = os.path.dirname(sys.executable)
    return os.path.join(exe_dir, filename)


class RouterMonitorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "RouterMonitor"
    _svc_display_name_ = "Router Monitor Service"
    _svc_description_ = "Monitors GL-iNet router status and logs the information"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = False

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.running = False

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.running = True
        self.main()

    def main(self):
        # Load config from the same directory as the executable
        config_path = get_data_path("config.json")
        with open(config_path, "r") as d:
            config_json = json.loads(d.read())

        password = config_json["password"]
        log_path = config_json.get("log_file", get_data_path("log.txt"))

        client = GlInetClient()
        client.login(password)
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            0,
            ("Logged in to router", '')
        )

        while self.running:
            try:
                system_status = client.get_system_status()
                
                try:
                    tethering = client.get_tethering_status(system_status)
                    ethernet = client.get_ethernet_status(system_status)
                except RPCUnauthorized:
                    client.login(password)
                    continue

                log_entry = json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "tethering": {"available": tethering.up, "used": tethering.online},
                    "ethernet": {"available": ethernet.up, "used": ethernet.online},
                })

                with open(log_path, mode="a") as f:
                    f.write(log_entry)
                    f.write("\n")

                # Wait for service stop event or timeout
                timeout_ms = 60 * 1000  # 60 seconds in milliseconds
                if win32event.WaitForSingleObject(self.stop_event, timeout_ms) == win32event.WAIT_OBJECT_0:
                    break
            except Exception as e:
                servicemanager.LogErrorMsg(f"Error in router monitoring: {str(e)}")
                # Wait a bit before retrying
                win32event.WaitForSingleObject(self.stop_event, 5000)  # 5 seconds


if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(RouterMonitorService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(RouterMonitorService)
