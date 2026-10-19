import os
import sys
import json
import sqlite3
from datetime import datetime
import paho.mqtt.client as mqtt

MQTT_BROKER = os.getenv("SMARTECO_MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("SMARTECO_MQTT_PORT", "1883"))
TEMP_TOPIC = os.getenv("SMARTECO_MQTT_TEMP_TOPIC", "sensors/temp")
CMD_TOPIC = os.getenv("SMARTECO_MQTT_CMD_TOPIC", "devices/commands")
DB_FILE = os.getenv("SMARTECO_DATABASE_LOCATION", "database.db")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def save_temperature(temp, hum=None):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO temperature (timestamp, temperature, humidity) VALUES (?, ?, ?)", (timestamp, temp, hum))
        conn.commit()
    except sqlite3.Error as e:
        print(f"SQLite error while saving: {e}")
    finally:
        if conn:
            conn.close()

def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Msg received: {payload}")
    
    try:
        data = json.loads(payload)
        temp = data.get("temperature")
        hum = data.get("humidity")
        
        if temp is not None:
            save_temperature(float(temp), float(hum) if hum is not None else None)
            print("JSON data saved on DB.")
            
    except json.JSONDecodeError:
        try:
            temp = float(payload)
            save_temperature(temp)
            print("Temp saved to DB.")
        except ValueError:
            print(f"Ignored: Payload was neither number or json: {payload}")

def run_daemon():
    print(f"Starting Daemon mode. Listening broker {MQTT_BROKER} -> '{TEMP_TOPIC}'...")
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.subscribe(TEMP_TOPIC)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nDaemon stopped by user.")
    except Exception as e:
        print(f"Error while connecting to broker: {e}")

def broadcast_command(comando):
    print(f"Sending command: '{comando}' to '{CMD_TOPIC}' in {MQTT_BROKER}")
    
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.publish(CMD_TOPIC, comando)
        client.disconnect()
        print("Ok.")
    except Exception as e:
        print(f"Error while sending MQTT command: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mqtt_bridge.py [daemon | <command>]")
        sys.exit(1)

    argument = sys.argv[1].lower()

    if argument == "daemon":
        run_daemon()
    else:
        full_command = " ".join(sys.argv[1:])
        broadcast_command(full_command)