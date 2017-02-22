# Nuimo Python SDK
[Nuimo](https://senic.com) is a universal smart device controller made by [Senic](https://senic.com).

The Nuimo Python SDK for Linux allows you to integrate your Nuimo(s) into any type of Linux application or script that can execute Python code.

## Prerequisites
The Nuimo SDK requires [Python 3.4+](https://www.python.org) and a recent installation of [BlueZ](http://www.bluez.org/). It is tested to work fine with BlueZ 5.43, slightly older versions should however work, too.

## Installation
These instructions assume a Debian-based Linux.

On Linux the [BlueZ](http://www.bluez.org/) library is necessary to access your built-in Bluetooth controller or Bluetooth USB dongle. Some Linux distributions provide a more up-to-date BlueZ package, some other distributions only install older versions that don't implement all Bluetooth features needed for this SDK. In those cases you want to either update BlueZ or build it from sources.

### Updating/installing BlueZ via apt-get

1. `bluetoothd --version` Obtains the version of the pre-installed BlueZ. `bluetoothd` daemon must run at startup expose the Bluetooth API via D-Bus.
2. `sudo apt-get install --no-install-recommends bluetooth` Installs BlueZ
3. If the installed version is too old, proceed with next step: [Installing BlueZ from sources](#installing-bluez-from-sources)

### Installing BlueZ from sources

The following commands download BlueZ 5.43 sources and built them into `/usr/local`. It's not suggested to remove any pre-installed BlueZ package as its deinstallation might remove necessary Bluetooth drivers as well.

1. `sudo systemctl stop bluetooth`
2. `sudo apt-get update`
3. `sudo apt-get install libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev libdbus-glib-1-dev unzip`
4. `cd`
5. `mkdir bluez`
6. `cd bluez`
7. `wget http://www.kernel.org/pub/linux/bluetooth/bluez-5.43.tar.xz`
8. `tar xf bluez-5.43.tar.xz`
9. `cd bluez-5.43`
10. `./configure`
11. `make`
12. `sudo make install`
13. `sudo systemctl daemon-reload`
14. `sudo systemctl start bluetooth`

### Enabling your Bluetooth adapter

1. `sudo hciconfig hci0 up` Enables your built-in Bluetooth adapter or external Bluetooth USB dongle

### Using BlueZ commandline tools
BlueZ also provides an interactive commandline tool to interact with Bluetooth devices. You know that your BlueZ installation is working fine if it discovers any Bluetooth devices nearby.

`sudo bluetoothctl` Starts an interactive mode to talk to BlueZ
  * `power on` Enables the Bluetooth adapter
  * `scan on` Start Bluetooth device scanning and lists all found devices with MAC addresses
  * `connect AA:BB:CC:DD:EE:FF` Connects to a Nuimo controller with specified MAC address
  * `exit` Quits the interactive mode

### Installing Nuimo Python SDK

To install Nuimo module and the Python3 D-Bus dependency globally, run:

`sudo pip3 install nuimo`
`sudo apt-get install python3-dbus`

#### Running the Nuimo control script

To test if your setup is working, run the following command. Note that it must be run as root because on Linux, Bluetooth discovery is a restricted operation.

`sudo python3 nuimoctl.py --discover`
`sudo python3 nuimoctl.py --connect AA:BB:CC:DD:EE:FF` (Replace the MAC address with your Nuimo's MAC address)

## SDK Usage

### Discovering nearby Nuimo controllers

The SDK entry point is the `ControllerManager` class. Check the following example to dicover any Nuimo controller nearby.

Please note that communication with your Bluetooth adapter happens over BlueZ's D-Bus API, hence an event loop needs to be run in order to receive all Bluetooth related events. You can start and stop the event loop via `run()` and `stop()` calls to your `ControllerManager` instance.


```
import nuimo

class ControllerManagerPrintListener(nuimo.ControllerManagerListener):
    def controller_discovered(self, controller):
        print("Discovered Nuimo controller", controller.mac_address)

manager = nuimo.ControllerManager(adapter_name='hci0')
manager.listener = nuimo.ControllerManagerPrintListener()
manager.start_discovery()
manager.run()

```

### Connecting to a Nuimo controller and receiving user input events

Once `ControllerManager` has discovered a Nuimo controller you can use the `controller` object that you retrieved from `ControllerManagerListener.controller_discovered()` to connect to it. Alternatively you can create a new instance of `Controller` using the name of your Bluetooth adapter (typically `hci0`) and Nuimo's MAC address.

Make sure to assign a `ControllerListener` object to the `listener` attribute of your controller instance. It will notify you about all Nuimo controller related events such connection, disconnection and user input events.

The following example connects to a Nuimo controller and uses the predefined `ControllerPrintListener` class to print all controller events:

```
import nuimo

controller = nuimo.Controller(adapter_name='hci0', mac_address="AA:BB:CC:DD:EE:FF")
controller.listener = nuimo.ControllerPrintListener(controller=controller)
controller.connect()

manager = ControllerManager(adapter_name="hci0")
manager.run()

```

As with Nuimo controller discovery, remember to start the Bluetooth event loop with `ControllerManager.run()`. Please make sure to use the same `ControllerManager` for starting and stopping the event loop.

### Write to Nuimo's LED matrix

Once a Nuimo controller is connected you can send an LED matrix to its display. Therefor create an `LedMatrix` object by initializing it with a string. That string should contain 81 characters: each character, starting from top left corner, tells whether the corresponding LED should be on or off. The following example shows a cross:

```
matrix = nuimo.LedMatrix(
    "*       *"
    " *     * "
    "  *   *  "
    "   * *   "
    "    *    "
    "   * *   "
    "  *   *  "
    " *     * "
    "*       *"
)
controller.display_matrix(matrix)

```

## Support

Please open an issue or drop us an email to [developers@senic.com](mailto:developers@senic.com).

## Contributing

Contributions are welcome via pull requests. Please open an issue first in case you want to discus your possible improvements to this SDK.

## License

The Nuimo Python SDK is available under the MIT License.
