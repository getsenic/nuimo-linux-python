# Nuimo Python SDK
[Nuimo](https://senic.com) is a universal smart device controller made by [Senic](https://senic.com).

The Nuimo Python SDK for Linux allows you to integrate your Nuimo(s) into any type of Linux application or script that can execute Python code.

## Prerequisites
The Nuimo SDK requires [Python 3.4+](https://www.python.org) and a recent installation of [BlueZ](http://www.bluez.org/). It is tested to work fine with BlueZ 5.44, slightly older versions should however work, too.

## Installation
These instructions assume a Debian-based Linux.

On Linux the [BlueZ](http://www.bluez.org/) library is necessary to access your built-in Bluetooth controller or Bluetooth USB dongle. Some Linux distributions provide a more up-to-date BlueZ package, some other distributions only install older versions that don't implement all Bluetooth features needed for this SDK. In those cases you want to either update BlueZ or build it from sources.

### Updating/installing BlueZ via apt-get

1. `bluetoothd --version` Obtains the version of the pre-installed BlueZ. `bluetoothd` daemon must run at startup to expose the Bluetooth API via D-Bus.
2. `sudo apt-get install --no-install-recommends bluetooth` Installs BlueZ
3. If the installed version is too old, proceed with next step: [Installing BlueZ from sources](#installing-bluez-from-sources)

### Installing BlueZ from sources

The `bluetoothd` daemon provides BlueZ's D-Bus interfaces that is accessed by the Nuimo SDK to communicate with Nuimo Bluetooth controllers. The following commands download BlueZ 5.44 sources, built them and replace any pre-installed `bluetoothd` daemon. It's not suggested to remove any pre-installed BlueZ package as its deinstallation might remove necessary Bluetooth drivers as well.

1. `sudo systemctl stop bluetooth`
2. `sudo apt-get update`
3. `sudo apt-get install libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev libdbus-glib-1-dev unzip`
4. `cd`
5. `mkdir bluez`
6. `cd bluez`
7. `wget http://www.kernel.org/pub/linux/bluetooth/bluez-5.44.tar.xz`
8. `tar xf bluez-5.44.tar.xz`
9. `cd bluez-5.44`
10. `./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var --enable-library`
11. `make`
12. `sudo make install`
13. `sudo ln -svf /usr/libexec/bluetooth/bluetoothd /usr/sbin/`
14. `sudo install -v -dm755 /etc/bluetooth`
15. `sudo install -v -m644 src/main.conf /etc/bluetooth/main.conf`
16. `sudo systemctl daemon-reload`
17. `sudo systemctl start bluetooth`
18. `bluetoothd --version` # should now print 5.44

Please note that some distributions might use a different directory for system deamons, apply step 13 only as needed.

### Enabling your Bluetooth adapter

1. `echo "power on" | sudo bluetoothctl` Enables your built-in Bluetooth adapter or external Bluetooth USB dongle

### Using BlueZ commandline tools
BlueZ also provides an interactive commandline tool to interact with Bluetooth devices. You know that your BlueZ installation is working fine if it discovers any Bluetooth devices nearby.

`sudo bluetoothctl` Starts an interactive mode to talk to BlueZ
  * `power on` Enables the Bluetooth adapter
  * `scan on` Start Bluetooth device scanning and lists all found devices with MAC addresses
  * `connect AA:BB:CC:DD:EE:FF` Connects to a Nuimo controller with specified MAC address
  * `exit` Quits the interactive mode

### Installing Nuimo Python SDK

To install Nuimo module and the Python3 D-Bus dependency globally, run:

```
sudo pip3 install nuimo
sudo apt-get install python3-dbus
```

#### Running the Nuimo control script

To test if your setup is working, run the following command. Note that it must be run as root because on Linux, Bluetooth discovery is a restricted operation.

```
sudo nuimoctl --discover
sudo nuimoctl --connect AA:BB:CC:DD:EE:FF # Replace the MAC address with your Nuimo's MAC address
sudo nuimoctl --help # To list all available commands
```

## SDK Usage

### Discovering nearby Nuimo controllers

The SDK entry point is the `ControllerManager` class. Check the following example to dicover any Nuimo controller nearby.

Please note that communication with your Bluetooth adapter happens over BlueZ's D-Bus API, hence an event loop needs to be run in order to receive all Bluetooth related events. You can start and stop the event loop via `run()` and `stop()` calls to your `ControllerManager` instance.


```python
import nuimo

class ControllerManagerPrintListener(nuimo.ControllerManagerListener):
    def controller_discovered(self, controller):
        print("Discovered Nuimo controller", controller.mac_address)

manager = nuimo.ControllerManager(adapter_name='hci0')
manager.listener = ControllerManagerPrintListener()
manager.start_discovery()
manager.run()
```

### Connecting to a Nuimo controller and receiving user input events

Once `ControllerManager` has discovered a Nuimo controller you can use the `controller` object that you retrieved from `ControllerManagerListener.controller_discovered()` to connect to it. Alternatively you can create a new instance of `Controller` using the name of your Bluetooth adapter (typically `hci0`) and Nuimo's MAC address.

Make sure to assign a `ControllerListener` object to the `listener` attribute of your controller instance. It will notify you about all Nuimo controller related events such connection, disconnection and user input events.

The following example connects to a Nuimo controller and uses the predefined `ControllerPrintListener` class to print all controller events:

```python
import nuimo

manager = nuimo.ControllerManager(adapter_name='hci0')

controller = nuimo.Controller(mac_address='AA:BB:CC:DD:EE:FF', manager=manager)
controller.listener = nuimo.ControllerListener() # Use an instance of your own nuimo.ControllerListener subclass
controller.connect()

manager.run()
```

As with Nuimo controller discovery, remember to start the Bluetooth event loop with `ControllerManager.run()`.

### Write to Nuimo's LED matrix

Once a Nuimo controller is connected you can send an LED matrix to its display. Therefor create an `LedMatrix` object by initializing it with a string. That string should contain 81 characters: each character, starting from top left corner, tells whether the corresponding LED should be on or off. `' '` and `'0'` signal LED off all other characters power the corresponding LED. The following example shows a cross:

```python
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

You can pass additional parameters to `display_matrix()` to control the following options:
* `interval: float` # Display interval in seconds, default: `2.0` seconds
* `brightness: float` # LED matrix brightness, default: `1.0` (100%)
* `fading: bool` # Whether to fade the previous matrix into the next one, aka "onion skinning effect", default: `False`
* `ignore_duplicates: bool` # Whether or not send an LED matrix to a Nuimo controller if it's already being displayed, default: `False`

## Support

Please open an issue or drop us an email to [developers@senic.com](mailto:developers@senic.com).

## Contributing

Contributions are welcome via pull requests. Please open an issue first in case you want to discus your possible improvements to this SDK.

## License

The Nuimo Python SDK is available under the MIT License.
