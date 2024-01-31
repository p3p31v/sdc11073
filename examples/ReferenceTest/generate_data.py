import time
from datetime import datetime
from influxdb import InfluxDBClient

# InfluxDB configuration
influx_host = 'localhost'
influx_port = 8086
influx_database = 'example_db'
influx_measurement = 'example_measurement'

# Connect to InfluxDB
influx_client = InfluxDBClient(host=influx_host, port=influx_port)
influx_client.create_database(influx_database)
influx_client.switch_database(influx_database)

# Generate and send data
try:
    while True:
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        value = round(time.time())

        data_point = {
            "measurement": influx_measurement,
            "tags": {},
            "time": timestamp,
            "fields": {"value": value}
        }

        # Write data to InfluxDB
        influx_client.write_points([data_point])

        print(f'Sent data to InfluxDB: {data_point}')
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    print("Script terminated.")