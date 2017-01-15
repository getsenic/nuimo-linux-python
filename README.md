# Nuimo Python SDK

The **Nuimo** SDK is a single Python source file.  It has been tested with Python 2.7 and Python 3.4.

## Installation
These instructions assume a Debian-based Linux.

1. `git clone https://github.com/getsenic/nuimo-linux-python`
2. `cd nuimo-linux-python`

The remainder of these instructions assume `nuimo-linux-python` is the current directory.

For convenience, the following groups of commands are included in a shell script **examples/install.sh**


### 1. Install bluez (Linux)

On Linux the [Bluez](http://www.bluez.org/) library is necessary to access your inbuilt Bluetooth controller or Bluetooth USB dongle.
If you are using a Raspberry Pi, the Bluez library is pre-installed in Raspian Jessie. The Raspberry Pi 3 comes with Bluetooth Controller hardware. 

1. `bluetoothd --version` (Shows the version of the pre-installed bluez. **bluetoothd** daemon must run at startup to use Bluez)
2. `sudo apt-get install --no-install-recommends bluetooth` (Installs Bluez)

**or**
```
sh examples/install.sh install
```
#### Using bluez commandline tools 
Bluez also provides commandline tools such as **hciconfig, hcitool, bluetoothctl** to interact with Bluetooth devices.
**bluetoothctl** was introduced in Bluez version 5.0 but many Linux distributions are still using Bluez 4.x.

1. `sudo hciconfig hci0 up` (Enables your Bluetooth dongle)
2. `sudo hcitool lescan` (Should discover your Nuimo, press Ctrl+C to stop discovery)
3. `bluetoothctl devices` (Lists the previously paired peripherals)

**or**
```
sh examples/install.sh scan
```
#### Manually connect to Nuimo with bluez (optional, skip this step if you are not interested)

1. `sudo hcitool lescan | grep Nuimo` (Copy your Nuimo's MAC address and press Ctrl+C to stop discovery)
2. `gatttool -b FA:48:12:00:CA:AC -t random -I` (Replace the MAC address with the address from step 1)
3. `connect` (Should successfully connect to Nuimo)
4. `characteristics` (Displays [Nuimo's GATT characteristics](https://senic.com/files/nuimo-gatt-profile.pdf))
5. Look for uuid `F29B1529-...` (button press characteristic) and note its `char value handle` (2nd column). Here: `001d`.
6. Add `1` to the handle. Here: `001d + 1 = 001e` (Hexadecimal value representation; [use a calculator if necessary](http://www.miniwebtool.com/hex-calculator/?number1=001d&operate=1&number2=1))
7. `char-write-req 001e 0100` (Registers for button click events; replace `001e` with the handle from step 6)
8. Hold Nuimo's click button pressed and release it. `gatttool` should now notify all button press events.
8. `exit` to leave `gatttool`

**or**
```
sh examples/install.sh connect
```

### 2. Install Nuimo Python SDK

#### Install the system dependencies

    sudo apt-get install build-essential pkg-config libboost-python-dev libboost-thread-dev libbluetooth-dev libglib2.0-dev python-dev python-setuptools`

#### Install Nuimo SDK & it's Python dependencies

If you're using Python 2.X run:

    sudo python setup.py install

If you're using Python 3.X run:

    sudo python3 setup.py install

This will install Nuimo SDK package and it's dependency Gattlib (see
note about Gattlib below) to Python package directory.

#### Running the example script

To test if your setup is working, run the following command (note that it must be run as root because on Linux, Bluetooth discovery is a restricted operation).

```
sudo python examples/test.py
```

You can find the example script here: [examples/test.py](/examples/test.py)
 
#### Tested on
1. Raspberry Pi Model 3 - Raspbian Jessie Full (raspberrypi 4.1.18)
2. Linux Mint 17.3 Rosa

### Note about Pygattlib
[Pygattlib](https://bitbucket.org/OscarAcena/pygattlib) is a Python library to use the GATT Protocol for Bluetooth LE devices. It is a wrapper around the implementation used by gatttool in the bluez package. Unlike some other Python Bluetooth libraries, Pygattlib does not need invoke any external programs.

**Known Issues**
Pygattlib may not be reliable on your platform.  We are investigating these issues at Senic.
1. The library sometimes appears to get 'stuck', especially when executing `discover_characteristics`.
