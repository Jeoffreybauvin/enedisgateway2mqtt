import os
import time
from dateutil.relativedelta import *
from distutils.util import strtobool
import sqlite3

from importlib import import_module
f = import_module("function")
addr = import_module("addresses")
cont = import_module("contract")
c = import_module("daily_consumption")
p = import_module("daily_production")
ha = import_module("home_assistant")

url = "https://enedisgateway.tech/api"

########################################################################################################################
# CHECK MANDATORY PARAMETERS
if not "ACCESS_TOKEN" in os.environ:
    f.log("Environement variable 'ACCESS_TOKEN' is mandatory")
    quit()
if not "PDL" in os.environ:
    f.log("Environement variable 'PDL' is mandatory")
    quit()
if not "MQTT_HOST" in os.environ:
    f.log("Environement variable 'MQTT_HOST' is mandatory")
    quit()

########################################################################################################################
# AUTHENTIFICATION
accessToken = os.environ['ACCESS_TOKEN']
pdl = os.environ['PDL']
headers = {
    'Content-Type': 'application/json',
    'Authorization': accessToken
}

########################################################################################################################
# MQTT
broker = os.environ['MQTT_HOST']

if broker == "":
    f.log("Environement variable 'MQTT_HOST' can't be empty")
    quit()

if "MQTT_PORT" in os.environ:
    port = int(os.environ['MQTT_PORT'])
else:
    port = 1883
if "MQTT_PREFIX" in os.environ:
    prefix = os.environ['MQTT_PREFIX']
else:
    prefix = "enedis_gateway"
if "MQTT_CLIENT_ID" in os.environ:
    client_id = os.environ['MQTT_CLIENT_ID']
else:
    client_id = "enedis_gateway"
if "MQTT_USERNAME" in os.environ:
    username = os.environ['MQTT_USERNAME']
else:
    username = ""
if "MQTT_PASSWORD" in os.environ:
    password = os.environ['MQTT_PASSWORD']
else:
    password: ""
if "RETAIN" in os.environ:
    retain = bool(strtobool(os.environ['RETAIN']))
else:
    retain = False
if "QOS" in os.environ:
    qos = int(os.environ['QOS'])
else:
    qos = 0
########################################################################################################################
# HOME ASSISTANT
if "HA_AUTODISCOVERY" in os.environ:
    ha_autodiscovery = bool(strtobool(os.environ['HA_AUTODISCOVERY']))
else:
    ha_autodiscovery = False
if "HA_AUTODISCOVERY_PREFIX" in os.environ:
    ha_autodiscovery_prefix = str(os.environ['HA_AUTODISCOVERY_PREFIX'])
else:
    ha_autodiscovery_prefix = "homeassistant"

########################################################################################################################
# CONSUMPTION
if "GET_CONSUMPTION" in os.environ:
    get_consumption = bool(strtobool(os.environ['GET_CONSUMPTION']))
else:
    get_consumption = True
if "CONSUMPTION_PRICE_BASE" in os.environ:
    consumption_base_price = float(os.environ['CONSUMPTION_PRICE_BASE'])
else:
    consumption_base_price = 0
if "CONSUMPTION_PRICE_HC" in os.environ:
    consumption_base_price = float(os.environ['CONSUMPTION_PRICE_HC'])
else:
    consumption_base_price = 0
if "CONSUMPTION_PRICE_HP" in os.environ:
    consumption_base_price = float(os.environ['CONSUMPTION_PRICE_HP'])
else:
    consumption_base_price = 0

########################################################################################################################
# PRODUCTION
if "GET_PRODUCTION" in os.environ:
    get_production = bool(strtobool(os.environ['GET_PRODUCTION']))
else:
    get_production = False
if "PRODUCTION_PRICE" in os.environ:
    production_base = float(os.environ['PRODUCTION_PRICE'])
else:
    production_base = 0

########################################################################################################################
# YEARS
# ! GENERATE 1 API CALL !
if "YEARS" in os.environ:
    years = int(os.environ['YEARS'])
    if years >= 3:
        years = 3
else:
    years = 1

########################################################################################################################
# ADDRESSES
# ! GENERATE 1 API CALL !
if "ADDRESSES" in os.environ:
    addresses = bool(strtobool(os.environ['ADDRESSES']))
else:
    addresses = True

########################################################################################################################
# CYCLE
if "CYCLE" in os.environ:
    cycle = int(os.environ['CYCLE'])
    if cycle < 3600:
        cycle = 3600
else:
    cycle = 86400

api_no_result = []

def run():
    client = f.connect_mqtt()
    client.loop_start()
    while True:

        # SQLlite
        if not os.path.exists('/data'):
            os.mkdir('/data')

        if not os.path.exists('/data/enedisgateway.db'):
            f.log("Init SQLite Database")
            con = sqlite3.connect('/data/enedisgateway.db', timeout=10)
            cur = con.cursor()
            # CONSUMPTION
            cur.execute('''CREATE TABLE consumption_daily
                           (pdl TEXT, date TEXT, value REAL)''')
            cur.execute('''CREATE UNIQUE INDEX idx_date_consumption
                            ON consumption_daily (date)''')
            # PRODUCTION
            cur.execute('''CREATE TABLE production_daily
                           (pdl TEXT, date TEXT, value REAL)''')
            cur.execute('''CREATE UNIQUE INDEX idx_date_production 
                            ON production_daily (date)''')
        else:
            con = sqlite3.connect('/data/enedisgateway.db', timeout=10)
            cur = con.cursor()

        f.log("####################################################################################")
        f.log("Get contract :")
        contract = cont.getContract(client)
        if "error" in contract:
            f.publish(client, f"error", str(1))
            for key, data in contract["errorMsg"].items():
                f.publish(client, f"errorMsg/{key}", str(data))
        else:
            f.publish(client, f"error", str(0))

            if "last_activation_date" in contract:
                last_activation_date = contract['last_activation_date']

            if addresses == True:
                f.log("####################################################################################")
                f.log("Get Addresses :")
                addr.getAddresses(client)

            if get_consumption == True:
                f.log("####################################################################################")
                f.log("Get Consumption :")
                ha_discovery_consumption = c.dailyConsumption(cur, client, last_activation_date)
                if ha_autodiscovery == True:
                    f.log("####################################################################################")
                    f.log("Home Assistant auto-discovery (Consumption) :")
                    for pdl, data in ha_discovery_consumption.items():
                        for name, sensor_data in data.items():
                            if "attributes" in sensor_data:
                                attributes = sensor_data['attributes']
                            else:
                                attributes = None
                            if "unit_of_meas" in sensor_data:
                                unit_of_meas = sensor_data['unit_of_meas']
                            else:
                                unit_of_meas = None
                            if "device_class" in sensor_data:
                                device_class = sensor_data['device_class']
                            else:
                                device_class = None
                            if "state_class" in sensor_data:
                                state_class = sensor_data['state_class']
                            else:
                                state_class = None
                            ha.haAutodiscovery(client=client, type="sensor", pdl=pdl, name=name, value=sensor_data['value'],
                                               attributes=attributes, unit_of_meas=unit_of_meas,
                                               device_class=device_class, state_class=state_class)

            if get_production == True:
                f.log("####################################################################################")
                f.log("Get production :")
                ha_discovery_production = p.dailyProduction(cur, client, last_activation_date)
                if ha_autodiscovery == True:
                    f.log("####################################################################################")
                    f.log("Home Assistant auto-discovery (Production) :")
                    for pdl, data in ha_discovery_production.items():
                        for name, sensor_data in data.items():
                            if "attributes" in sensor_data:
                                attributes = sensor_data['attributes']
                            else:
                                attributes = None
                            if "unit_of_meas" in sensor_data:
                                unit_of_meas = sensor_data['unit_of_meas']
                            else:
                                unit_of_meas = None
                            if "device_class" in sensor_data:
                                device_class = sensor_data['device_class']
                            else:
                                device_class = None
                            if "state_class" in sensor_data:
                                state_class = sensor_data['state_class']
                            else:
                                state_class = None
                            ha.haAutodiscovery(client=client, type="sensor", pdl=pdl, name=name, value=sensor_data['value'],
                                            attributes=attributes, unit_of_meas=unit_of_meas,
                                            device_class=device_class, state_class=state_class)

        # query = f"SELECT * FROM consumption_daily ORDER BY date"
        # rows = con.execute(query)
        # for row in rows:
        #     print(row)

        con.commit()
        con.close()
        time.sleep(cycle)


if __name__ == '__main__':
    run()
