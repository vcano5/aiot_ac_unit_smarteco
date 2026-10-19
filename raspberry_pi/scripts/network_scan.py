import subprocess
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime
import os

command = ["sudo", "nmap", "-sn", os.environ.get("SMARTECO_SUBNET"), "-oX", "-"]
result = subprocess.run(command, capture_output=True, text=True)


root = ET.fromstring(result.stdout)
devices = []

for host in root.findall("host"):
    if host.find("status").get("state") != "up":
        continue
    mac_elem = host.find("address[@addrtype='mac']")
    mac = mac_elem.get("addr") if mac_elem is not None else "Desconocida (Local)"
    vendor = mac_elem.get("vendor") if mac_elem is not None else "Desconocido"

    hostnames_elem = host.find("hostnames/hostname")
    hostname = hostnames_elem.get("name") if hostnames_elem is not None else ""
    
    devices.append((mac, hostname, vendor, datetime.now().isoformat()))

conn = sqlite3.connect(os.environ.get("SMARTECO_DATABASE_LOCATION") + ".db")
cursor = conn.cursor()


cursor.executemany('''
INSERT INTO devices (mac, hostname, vendor, lastseen) VALUES (?, ?, ?, ?) ON CONFLICT(mac) DO UPDATE SET lastseen=excluded.lastseen
''', devices)

conn.commit()
conn.close()

print(f"Scan done. {len(devices)} devices detected.")