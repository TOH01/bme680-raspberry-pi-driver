#!/usr/bin/python3

from driver import BME680
import time

if __name__ == "__main__":
    bme680 = BME680()
    bme680.set_forced_mode()
    time.sleep(1)
    print(bme680.get_compensated_tph())
