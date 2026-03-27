# BME680 Raspberry Pi Driver

A pure Python driver for the Bosch BME680 environmental sensor on Raspberry Pi 4/5, with a C bridge to the proprietary Bosch BSEC library for Indoor Air Quality (IAQ) computation.

## Features

- Direct I2C register access with no external driver dependencies beyond `smbus2`
- Temperature, pressure, humidity, and gas resistance readings
- Compensation algorithms implemented per the BME680 datasheet
- BSEC 2.x integration for IAQ index calculation via a lightweight C bridge
- Automatic BSEC state persistence and restore across restarts

## Hardware Requirements

- Raspberry Pi 4 or 5
- BME680 sensor connected via I2C (default address `0x77`, falls back to `0x76`)
- I2C enabled on the Pi (`sudo raspi-config` → Interface Options → I2C)

## Wiring

Tested with the Joy-IT BME680 breakout board. Connect four pins:

| Raspberry Pi 5 | BME680 |
|-----------------|--------|
| Pin 1 (3.3V)   | VCC    |
| Pin 3 (SDA)    | SDA    |
| Pin 5 (SCL)    | SCL    |
| Pin 6 (GND)    | GND    |

Leave SDO and CS unconnected — the Joy-IT board pulls SDO high, setting the I2C address to `0x77`. Other breakout boards may wire these differently; if the sensor isn't found, check whether SDO needs to be tied high or low for your board.

![Wiring diagram](docs/wiring.svg)

## Project Structure

```
.
├── docs/
│   └── wiring.svg              # Wiring diagram
├── src/
│   ├── example.py              # Usage example
│   ├── driver/                  # Python BME680 driver
│   │   ├── bme680.py
│   │   ├── bme680_compensation.py
│   │   ├── bme680_constants.py
│   │   ├── bme680_register.py
│   │   ├── i2c.py
│   │   ├── register.py
│   │   └── register_group.py
│   └── bsec_bridge/             # BSEC C bridge
│       ├── bsecIAQ.py
│       ├── bsec_wrapper.c
│       ├── bsec_wrapper.h
│       └── compile.sh
├── bsec/                        # Bosch BSEC library (not included, see below)
│   └── algo/
│       └── bsec_IAQ/
│           ├── inc/
│           └── bin/
└── README.md
```

## Setup

### 1. Install Python dependencies

```bash
pip install smbus2
```

### 2. Obtain the Bosch BSEC library

The BSEC library is proprietary and cannot be redistributed. Download it directly from Bosch:

1. Go to [https://www.bosch-sensortec.com/software-tools/software/bme680-software-bsec/](https://www.bosch-sensortec.com/software-tools/software/bme680-software-bsec/)
2. Download BSEC 2.x (tested against **BSEC 2.6.1.0**)
3. Extract and copy the contents so that the following paths exist:
   - `bsec/algo/bsec_IAQ/inc/` (header files)
   - `bsec/algo/bsec_IAQ/bin/RaspberryPi/PiFour_Armv8/libalgobsec.a` (static library)

The `PiFour_Armv8` binary works for both Raspberry Pi 4 and Pi 5.

### 3. Compile the BSEC bridge

```bash
cd src/bsec_bridge
chmod +x compile.sh
./compile.sh
```

This uses `gcc` (pre-installed on Raspberry Pi OS) to produce `libbsec_wrapper.so` in the `src/` directory, right next to `example.py`.

### 4. Run

```bash
cd src
python example.py
```

Expected output:

```
BSEC not ready, skipping
Temp: 24.96 °C  Press: 101568.32 Pa  Hum: 40.22 %  IAQ: 180.7  Accuracy: 1
Temp: 25.00 °C  Press: 101561.82 Pa  Hum: 40.19 %  IAQ: 200.0  Accuracy: 1
Temp: 25.02 °C  Press: 101559.92 Pa  Hum: 40.13 %  IAQ: 201.4  Accuracy: 1
...
```

Press `Ctrl+C` to stop. The BSEC state is saved automatically on exit and restored on the next run, preserving calibration progress.

## BSEC Calibration and Burn-In

The BSEC algorithm requires time to produce accurate IAQ readings. There are a few things to be aware of:

**Accuracy levels** — The `Accuracy` field in the output indicates calibration status:
- `0` — Stabilizing, output unreliable
- `1` — Low accuracy, background calibration in progress
- `2` — Medium accuracy
- `3` — Fully calibrated

**Initial burn-in** — Per the Bosch documentation, the BME680 gas sensor requires a burn-in period of approximately 48 hours of continuous operation before gas resistance readings fully stabilize. During this period, IAQ values will drift and should not be considered reliable.

**Ongoing calibration** — Even after burn-in, BSEC continuously adjusts its baseline. The algorithm expects to see both clean and polluted air over time to establish a meaningful reference. A sensor running in consistently clean air may take longer to reach accuracy 3.

**State persistence** — The example saves BSEC state every 5 minutes and on shutdown. This means you do not lose calibration progress across restarts. Without state persistence, the algorithm restarts from scratch each time.

**First reading** — The very first BSEC call after startup may return no output (`BSEC not ready, skipping`). This is normal — the algorithm needs at least one data point before it can produce IAQ values.

For full details, refer to the [BME680 datasheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme680-ds001.pdf) and the BSEC integration guide included in the BSEC download.

## Using the Driver Without BSEC

The Python driver works independently of BSEC. If you only need temperature, pressure, humidity, and raw gas resistance:

```python
from driver import BME680

with BME680() as bme680:
    bme680.set_forced_mode()
    bme680.wait_for_tph_measurement()
    tph = bme680.get_compensated_tph()

    print(f"Temperature: {tph['temperature']:.2f} °C")
    print(f"Pressure:    {tph['pressure']:.2f} Pa")
    print(f"Humidity:    {tph['humidity']:.2f} %")
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

The Bosch BSEC library has its own proprietary license. Refer to the license terms included in the BSEC download.
