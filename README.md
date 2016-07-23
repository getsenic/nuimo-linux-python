# Nuimo Python SDK

## Installation

### 1. Install bluez (Linux)

On Linux the [Bluez](http://www.bluez.org/) library is necessary to access your inbuilt Bluetooth controller or Bluetooth USB dongle.
If you are using a Raspberry Pi, the Bluez library is pre-installed in Raspian Jessie. The Raspberry Pi 3 comes with Bluetooth Controller hardware. 

1. `bluetoothd --version` (Shows the version of the pre-installed bluez. **bluetoothd** daemon must run at startup to use Bluez)
2. `sudo apt-get install --no-install-recommends bluetooth` (Installs Bluez)

##### Using bluez commandline tools 
Bluez also provides commandline tools such as **hciconfig, hcitool, bluetoothctl** to interact with Bluetooth devices.

1. `sudo hciconfig hci0 up` (Enables your Bluetooth dongle)
2. `sudo hcitool lescan` (Should discover your Nuimo, press Ctrl+C to stop discovery)
3. `bluetoothctl devices` (Lists the previously paired peripherals)

##### Manually connect to Nuimo with bluez (optional, skip this step if you are not interested)

1. `sudo hcitool lescan | grep Nuimo` (Copy your Nuimo's MAC address and press Ctrl+C to stop discovery)
2. `gatttool -b FA:48:12:00:CA:AC -t random -I` (Replace the MAC address with the address from step 1)
3. `connect` (Should successfully connect to Nuimo)
4. `characteristics` (Displays [Nuimo's GATT characteristics](https://senic.com/files/nuimo-gatt-profile.pdf))
5. Look for uuid `F29B1529-...` (button press characteristic) and note its `char value handle` (2nd column). Here: `001d`.
6. Add `1` to the handle. Here: `001d + 1 = 001e` (Hexadecimal value representation; [use a calculator if necessary](http://www.miniwebtool.com/hex-calculator/?number1=001d&operate=1&number2=1))
7. `char-write-req 001e 0100` (Registers for button click events; replace `001e` with the handle from step 6)
8. Hold Nuimo's click button pressed and release it. `gatttool` should now notify all button press events.
8. `exit` to leave `gatttool`

### 2. Install Pygattlib
[Pygattlib](https://github.com/matthewelse/pygattlib) is a Python library to use the GATT Protocol for Bluetooth LE devices. It is a wrapper around the implementation used by gatttool in bluez package. It does not call other binaries to do its job.

##### Install the dependencies
1. `sudo apt-get install pkg-config libboost-python-dev libboost-thread-dev libbluetooth-dev libglib2.0-dev python-dev`

##### Installing Pygattlib
1. `git clone https://github.com/matthewelse/pygattlib`
2. `cd pygattlib`
3. `sudo python setup.py install` (It installs **gattlib.so** to the folder **/usr/local/lib/python2.7/dist-packages** on Raspberry Pi )

### 3. Install Nuimo Python SDK
1. `git clone https://github.com/getsenic/nuimo-linux-osx-python`
2. `cd nuimo-linux-osx-python`
3. `sudo python setup.py install`

## Usage
### 1. Linux 
**nuimo** SDK is installed as python module at **/usr/local/lib/python2.7/dist-packages** on Linux and it can be imported simply by adding `from nuimo import Nuimo`

#### Example
```python
from threading import Event
from nuimo import Nuimo

if __name__ == '__main__':
    print '=== Nuimo Python SDK ==='
    nuimo = Nuimo()

    print 'Discovering Nuimos with default timeout 5 seconds, default adapter hci0...'
    discovered_nuimos = nuimo.discover_nuimos()
    print 'Discovered Nuimos', discovered_nuimos

    print 'Connecting to Nuimo', discovered_nuimos[0]
    rv = nuimo.connect(address=discovered_nuimos[0])
    print 'Nuimo connected: ', rv

    print 'Displaying LED Matrix...'
    timeout = 5.0
    rv = nuimo.display_led(
        "         " +
        " ***     " +
        " *  * *  " +
        " *  *    " +
        " ***  *  " +
        " *    *  " +
        " *    *  " +
        " *    *  " +
        "         ", timeout)
    print 'LED Matrix written: ', rv

    print 'Reading battery voltage...'
    battery_val = ord(nuimo.read_battery()[0])
    print 'Nuimo battery is {0} percent'.format(battery_val)


    def button_click_cb(data):
        print 'Button Click', data


    print 'Enabling button click...'
    rv = nuimo.enable_button_click_notification(button_click_cb)
    print 'Button click notification enabled:', rv


    def rotation_cb(data):
        print 'Rotated', data


    print 'Enabling Rotation...'
    rv = nuimo.enable_rotation_notification(rotation_cb)
    print 'Rotation notification enabled:', rv


    def swipe_cb(data):
        print 'Swiped', data


    print 'Enabling swiping...'
    rv = nuimo.enable_swipe_notification(swipe_cb)
    print 'Swipe notification enabled:', rv


    def fly_cb(data):
        print 'Gesture', data


    print 'Enabling fly gestures...'
    rv = nuimo.enable_fly_notification(fly_cb)
    print 'Fly gesture notification enabled:', rv

    Event().wait()

```
 
#### Tested on
1. Raspberry Pi Model 3 - Raspbian Jessie Full (raspberrypi 4.1.18)










