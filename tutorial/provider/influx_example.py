import influxdb_client
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import time

token = os.environ.get("INFLUXDB_TOKEN")
org = "joselito"
url = "http://localhost:8086"

write_client = InfluxDBClient(url=url, token=token, org=org)  # Corrected the client instantiation

bucket = "joselito"

write_api = write_client.write_api(write_options=SYNCHRONOUS)  # Corrected the client usage

for value in range(5):
    point = (
        Point("measurement1")
        .tag("tagname1", "tagvalue1")
        .field("field1", value)
    )
    write_api.write(bucket=bucket, org="joselito", record=point)
    time.sleep(1)  # Separate points by 1 second