import dbus
import dbus.mainloop.glib
import functools
import gatt
import re
from enum import Enum
from gi.repository import GObject


class Gesture(Enum):
    BUTTON_PRESS = 1
    BUTTON_RELEASE = 2
    SWIPE_LEFT = 3
    SWIPE_RIGHT = 4
    SWIPE_UP = 5
    SWIPE_DOWN = 6
    TOUCH_LEFT = 8,
    TOUCH_RIGHT = 9,
    TOUCH_TOP = 10,
    TOUCH_BOTTOM = 11,
    LONGTOUCH_LEFT = 12
    LONGTOUCH_RIGHT = 13
    LONGTOUCH_TOP = 14,
    LONGTOUCH_BOTTOM = 15,
    ROTATION = 16,
    FLY_LEFT = 17,
    FLY_RIGHT = 18,
    FLY_UPDOWN = 19


class GestureEvent:
    def __init__(self, gesture, value=None):
        self.gesture = gesture
        self.value = value

    def __repr__(self):
        return str(self.gesture) + (("," + str(self.value)) if self.value is not None else "")


class LedMatrix:
    def __init__(self, string):
        string = '{:<81}'.format(string[:81])
        self.leds = [c not in [' ', '0'] for c in string]


class Controller(gatt.Device):
    NUIMO_SERVICE_UUID                    = 'f29b1525-cb19-40f3-be5c-7241ecb82fd2'
    BUTTON_CHARACTERISTIC_UUID            = 'f29b1529-cb19-40f3-be5c-7241ecb82fd2'
    TOUCH_CHARACTERISTIC_UUID             = 'f29b1527-cb19-40f3-be5c-7241ecb82fd2'
    ROTATION_CHARACTERISTIC_UUID          = 'f29b1528-cb19-40f3-be5c-7241ecb82fd2'
    FLY_CHARACTERISTIC_UUID               = 'f29b1526-cb19-40f3-be5c-7241ecb82fd2'
    LED_MATRIX_CHARACTERISTIC_UUID        = 'f29b152d-cb19-40f3-be5c-7241ecb82fd2'

    LEGACY_LED_MATRIX_SERVICE             = 'f29b1523-cb19-40f3-be5c-7241ecb82fd1'
    LEGACY_LED_MATRIX_CHARACTERISTIC_UUID = 'f29b1524-cb19-40f3-be5c-7241ecb82fd1'

    # TODO: Give services their actual names
    UNNAMED1_SERVICE_UUID                 = '00001801-0000-1000-8000-00805f9b34fb'
    UNNAMED2_SERVICE_UUID                 = '0000180a-0000-1000-8000-00805f9b34fb'
    UNNAMED3_SERVICE_UUID                 = '0000180f-0000-1000-8000-00805f9b34fb'

    SERVICE_UUIDS = [
        NUIMO_SERVICE_UUID,
        LEGACY_LED_MATRIX_SERVICE,
        UNNAMED1_SERVICE_UUID,
        UNNAMED2_SERVICE_UUID,
        UNNAMED3_SERVICE_UUID]

    def __init__(self, adapter_name, mac_address):
        super().__init__(adapter_name, mac_address)
        self.listener = None

    def connect(self):
        if self.listener:
            self.listener.started_connecting()
        super().connect()

    def connect_failed(self, error):
        if self.listener:
            self.listener.connect_failed(error)

    def disconnect(self):
        if self.listener:
            self.listener.started_disconnecting()
        super().disconnect()

    def connected(self):
        super().connected()

    def disconnected(self):
        super().disconnected()
        self.listener.disconnected()

    def services_resolved(self):
        super().services_resolved()

        for service in self.services:
            print(service.path, service.uuid)
            for characteristic in service.characteristics:
                print("   ", characteristic.path, characteristic.uuid)

        nuimo_service = next(service for service in self.services if service.uuid == self.NUIMO_SERVICE_UUID)

        notification_characteristic_uuids = [
            self.BUTTON_CHARACTERISTIC_UUID,
            self.TOUCH_CHARACTERISTIC_UUID,
            self.ROTATION_CHARACTERISTIC_UUID,
            self.FLY_CHARACTERISTIC_UUID
        ]

        for characteristic_uuid in notification_characteristic_uuids:
            characteristic = next((
                characteristic for characteristic in nuimo_service.characteristics
                if characteristic.uuid == characteristic_uuid), None)
            characteristic.enable_notifications()

        # TODO: Only fire `connected` when we read the firmware version or battery value as in other SDKs
        if self.listener:
            self.listener.connected()

    def display_matrix(self, matrix, interval=2.0, brightness=1.0, options=0):
        matrix_bytes = list(
            map(lambda leds: functools.reduce(
                lambda acc, led: acc + (1 << led if leds[led] else 0), range(0, len(leds)), 0),
                [matrix.leds[i:i + 8] for i in range(0, 81, 8)]))

        # TODO: Support `fading` parameter
        # if fading:
        #     matrix_bytes_list[10] ^= 1 << 4

        # TODO: Support write requests without response
        # TODO: Support ignore duplicate matrix writes

        matrix_bytes += [max(0, min(255, int(brightness * 255.0))), max(0, min(255, int(interval * 10.0)))]

        nuimo_service = next((service for service in self.services if service.uuid == self.NUIMO_SERVICE_UUID), None)
        matrix_characteristic = next((
            characteristic for characteristic in nuimo_service.characteristics
            if characteristic.uuid == self.LED_MATRIX_CHARACTERISTIC_UUID), None)
        # TODO: Fallback to legacy led matrix service
        # this is needed for older Nuimo firmware were the LED characteristic was a separate service)

        matrix_characteristic.write_value(matrix_bytes)

    def characteristic_value_updated(self, characteristic, value):
        {
            self.BUTTON_CHARACTERISTIC_UUID:   self.notify_button_event,
            self.TOUCH_CHARACTERISTIC_UUID:    self.notify_touch_event,
            self.ROTATION_CHARACTERISTIC_UUID: self.notify_rotation_event,
            self.FLY_CHARACTERISTIC_UUID:      self.notify_fly_event
        }[characteristic.uuid](value)

    def notify_button_event(self, value):
        self.notify_gesture_event(gesture=Gesture.BUTTON_RELEASE if value[0] == 0 else Gesture.BUTTON_PRESS)

    def notify_touch_event(self, value):
        gesture = {
            0:  Gesture.SWIPE_LEFT,
            1:  Gesture.SWIPE_RIGHT,
            2:  Gesture.SWIPE_UP,
            3:  Gesture.SWIPE_DOWN,
            4:  Gesture.TOUCH_LEFT,
            5:  Gesture.TOUCH_RIGHT,
            6:  Gesture.TOUCH_TOP,
            7:  Gesture.TOUCH_BOTTOM,
            8:  Gesture.LONGTOUCH_LEFT,
            9:  Gesture.LONGTOUCH_RIGHT,
            10: Gesture.LONGTOUCH_TOP,
            11: Gesture.LONGTOUCH_BOTTOM
        }[value[0]]
        if gesture is not None:
            self.notify_gesture_event(gesture=gesture)

    def notify_rotation_event(self, value):
        rotation_value = value[0] + (value[1] << 8)
        if (value[1] >> 7) > 0:
            rotation_value -= 1 << 16
        self.notify_gesture_event(gesture=Gesture.ROTATION, value=rotation_value)

    def notify_fly_event(self, value):
        if value[0] == 0:
            self.notify_gesture_event(gesture=Gesture.FLY_LEFT)
        elif value[0] == 1:
            self.notify_gesture_event(gesture=Gesture.FLY_RIGHT)
        elif value[0] == 4:
            self.notify_gesture_event(gesture=Gesture.FLY_UPDOWN, value=value[1])

    def notify_gesture_event(self, gesture, value=None):
        if self.listener:
            self.listener.received_gesture_event(GestureEvent(gesture=gesture, value=value))


class ControllerListener:
    def received_gesture_event(self, event):
        pass

    def started_connecting(self):
        pass

    def connected(self):
        pass

    def connect_failed(self, error):
        pass

    def started_disconnecting(self):
        pass

    def disconnected(self):
        pass


class ControllerManagerListener:
    def controller_discovered(self, controller):
        pass


# TODO: Extract reusable `DeviceDiscovery` class
class ControllerManager:
    def __init__(self, adapter_name='hci0'):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.mainloop = GObject.MainLoop()
        self.listener = None
        self.bus = dbus.SystemBus()
        self.object_manager = dbus.Interface(
            self.bus.get_object('org.bluez', '/'),
            'org.freedesktop.DBus.ObjectManager')

        # TODO: Get adapter from managed objects? See bluezutils.py
        adapter_object = self.bus.get_object('org.bluez', '/org/bluez/' + adapter_name)
        self.adapter = dbus.Interface(adapter_object, 'org.bluez.Adapter1')

        self.adapter_name = adapter_name
        self.device_path_regex = re.compile('^/org/bluez/' + adapter_name + '/dev((_[A-Z0-9]{2}){6})$')

        self._interface_added_signal = None
        self._properties_changed_signal = None

    def run(self):
        """Starts the main loop that is necessary to receive Bluetooth events from the Bluetooth driver.
           This call blocks until you call `stop()` to stop the main loop."""
        self.mainloop.run()

    def stop(self):
        """Stops the main loop started with `start()`"""
        self.mainloop.quit()

    def known_controllers(self):
        # TODO: Return known devices
        # see https://github.com/bbirand/python-dbus-gatt/blob/master/discovery.py
        return []

    def start_discovery(self):
        # TODO: Support service UUID filter
        # see http://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc/adapter-api.txt#n57
        self._discovered_controllers = {}

        self._interface_added_signal = self.bus.add_signal_receiver(
            self._interfaces_added,
            dbus_interface='org.freedesktop.DBus.ObjectManager',
            signal_name='InterfacesAdded')

        self._properties_changed_signal = self.bus.add_signal_receiver(
            self._properties_changed,
            dbus_interface=dbus.PROPERTIES_IFACE,
            signal_name='PropertiesChanged',
            arg0='org.bluez.Device1',
            path_keyword='path')

        self.adapter.SetDiscoveryFilter({
            'UUIDs': Controller.SERVICE_UUIDS,
            'Transport': 'le'})
        self.adapter.StartDiscovery()

    def stop_discovery(self):
        if self._interface_added_signal is not None:
            self._interface_added_signal.remove()
        if self._properties_changed_signal is not None:
            self._properties_changed_signal.remove()
        self.adapter.StopDiscovery()

    def _interfaces_added(self, path, interfaces):
        self._device_discovered(path, interfaces)

    def _properties_changed(self, interface, changed, invalidated, path):
        # TODO: Handle `changed` and `invalidated` properties and update device
        self._device_discovered(path, [interface])

    def _device_discovered(self, path, interfaces):
        if 'org.bluez.Device1' not in interfaces:
            return
        match = self.device_path_regex.match(path)
        if not match:
            return
        mac_address = match.group(1)[1:].replace('_', ':').lower()
        alias = gatt.Device(adapter_name=self.adapter_name, mac_address=mac_address).alias()
        if alias != 'Nuimo':
            return
        controller = Controller(adapter_name=self.adapter_name, mac_address=mac_address)
        discovered_controller = self._discovered_controllers.get(controller.mac_address, None)
        if discovered_controller is None:
            self._discovered_controllers[mac_address] = controller
            if self.listener is not None:
                self.listener.controller_discovered(controller)
        else:
            discovered_controller.advertised()


class ControllerPrintListener(ControllerListener):
    def __init__(self, controller):
        self.controller = controller

    def started_connecting(self):
        self.print("connecting...")

    def connected(self):
        self.print("connected")

    def connect_failed(self, error):
        self.print("connect failed: " + str(error))

    def started_disconnecting(self):
        self.print("disconnecting...")

    def disconnected(self):
        self.print("disconnected")

    def received_gesture_event(self, event):
        self.print("did send gesture event " + str(event))

    def print(self, string):
        print("Nuimo controller " + self.controller.mac_address + " " + string)
