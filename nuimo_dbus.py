import dbus
import dbus.mainloop.glib
import functools
import re
from enum import Enum
from gi.repository import GObject


class GattCharacteristic:
    def __init__(self, service, path, uuid):
        self.service = service
        self.path = path
        self.uuid = uuid
        self.bus = service.bus
        self.object_manager = service.object_manager
        self.object = self.bus.get_object("org.bluez", path)
        self.properties = dbus.Interface(self.object, "org.freedesktop.DBus.Properties")
        self.properties_signal = self.properties.connect_to_signal("PropertiesChanged", self.properties_changed)

    def invalidate(self):
        self.properties_signal.remove()

    def properties_changed(self, properties, changed_properties, invalidated_properties):
        value = changed_properties.get("Value")
        if value is not None:
            self.service.device.characteristic_value_updated(characteristic=self, value=bytes(value))

    def write_value(self, bytes, offset=0):
        bytes = [dbus.Byte(b) for b in bytes]
        self.object.WriteValue(
            bytes,
            {"offset": dbus.Byte(offset, variant_level=1)},
            reply_handler=self.write_value_succeeded,
            error_handler=self.write_value_failed,
            dbus_interface="org.bluez.GattCharacteristic1")

    def write_value_succeeded(self):
        print("write_value_succeeded")

    def write_value_failed(self, error):
        print("write_value_failed", error)

    def enable_notifications(self):
        self.object.StartNotify(
            reply_handler=self.enable_notifications_succeeded,
            error_handler=self.enable_notifications_failed,
            dbus_interface="org.bluez.GattCharacteristic1"
        )

    def enable_notifications_succeeded(self):
        print("notification_enabling_succeeded")

    def enable_notifications_failed(self, error):
        print("notification_enabling_failed", error)


class GattService:
    def __init__(self, device, path, uuid):
        self.device = device
        self.path = path
        self.uuid = uuid
        self.bus = device.bus
        self.object_manager = device.object_manager
        self.object = self.bus.get_object("org.bluez", path)
        self.characteristics = []
        self.characteristics_resolved()

    def invalidate(self):
        self.invalidate_characteristics()

    def invalidate_characteristics(self):
        for characteristic in self.characteristics:
            characteristic.invalidate()

    def characteristics_resolved(self):
        self.invalidate_characteristics()

        characteristics_regex = re.compile(self.path + "/char[0-9abcdef]{4}$")
        managed_characteristics = [char for char in self.object_manager.GetManagedObjects().items() if characteristics_regex.match(char[0])]
        self.characteristics = [GattCharacteristic(
            service=self,
            path=c[0],
            uuid=c[1]["org.bluez.GattCharacteristic1"]["UUID"]) for c in managed_characteristics]


class GattDevice:
    def __init__(self, adapter_name, mac_address):
        self.mac_address = mac_address
        self.bus = dbus.SystemBus()
        self.object_manager = dbus.Interface(self.bus.get_object("org.bluez", '/'), "org.freedesktop.DBus.ObjectManager")

        # TODO: Get adapter from managed objects? See bluezutils.py
        adapter_object = self.bus.get_object("org.bluez", "/org/bluez/" + adapter_name)
        self.adapter = dbus.Interface(adapter_object, "org.bluez.Adapter1")

        # TODO: Device needs to be created if it's not yet known to bluetoothd, see "test-device" in bluez-5.43/test/
        self.device_path = "/org/bluez/" + adapter_name + "/dev_" + mac_address.replace(":", "_").upper()
        device_object = self.bus.get_object("org.bluez", self.device_path)
        self.object = dbus.Interface(device_object, "org.bluez.Device1")
        self.services = []

        self.properties = dbus.Interface(self.object, "org.freedesktop.DBus.Properties")
        self.properties_signal_match = self.properties.connect_to_signal("PropertiesChanged", self.properties_changed)

    def invalidate(self):
        self.properties_signal_match.remove()
        self.invalidate_services()

    def invalidate_services(self):
        for service in self.services:
            service.invalidate()

    def is_registered(self):
        # TODO: Implement, see __init__
        return False

    def register(self):
        # TODO: Implement, see __init__
        return

    def connect(self):
        self.__connect()

    def __connect(self):
        print("__connect...")
        try:
            self.object.Connect()
        except dbus.exceptions.DBusException as e:
            # TODO: Only retry on "software" exceptions and only retry for a given number of retries
            print("Failed to connect:", e)
            print("Trying to connect again...")
            self.__connect()

        if self.is_services_resolved():
            self.services_resolved()

    def disconnect(self):
        self.object.Disconnect()

    def connected(self):
        """Will be called when `connect()` has finished connecting to the device. Will not be called if the device was already connected."""
        pass

    def disconnected(self):
        """Will be called when the device has disconnected"""
        pass

    def is_connected(self):
        return self.properties.Get("org.bluez.Device1", "Connected") == 1

    def is_services_resolved(self):
        return self.properties.Get("org.bluez.Device1", "ServicesResolved") == 1

    def alias(self):
        return self.properties.Get("org.bluez.Device1", "Alias")

    def properties_changed(self, sender, changed_properties, invalidated_properties):
        if "Connected" in changed_properties:
            if changed_properties["Connected"]:
                self.connected()
            else:
                self.disconnected()

        if "ServicesResolved" in changed_properties and changed_properties["ServicesResolved"] == 1:
            self.services_resolved()

    def services_resolved(self):
        self.invalidate_services()

        services_regex = re.compile(self.device_path + "/service[0-9abcdef]{4}$")
        managed_services = [service for service in self.object_manager.GetManagedObjects().items() if services_regex.match(service[0])]
        self.services = [GattService(
            device=self,
            path=service[0],
            uuid=service[1]["org.bluez.GattService1"]["UUID"]) for service in managed_services]

    def characteristic_value_updated(self, characteristic, value):
        # To be implemented by subclass
        pass


class NuimoGesture(Enum):
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


class NuimoGestureEvent:
    def __init__(self, gesture, value=None):
        self.gesture = gesture
        self.value = value

    def __repr__(self):
        return str(self.gesture) + (("," + str(self.value)) if self.value is not None else "")


class NuimoLedMatrix:
    def __init__(self, string):
        string = "{:<81}".format(string[:81])
        self.leds = [c not in [' ', '0'] for c in string]


class NuimoController(GattDevice):
    NUIMO_SERVICE_UUID                    = "f29b1525-cb19-40f3-be5c-7241ecb82fd2"
    BUTTON_CHARACTERISTIC_UUID            = "f29b1529-cb19-40f3-be5c-7241ecb82fd2"
    TOUCH_CHARACTERISTIC_UUID             = "f29b1527-cb19-40f3-be5c-7241ecb82fd2"
    ROTATION_CHARACTERISTIC_UUID          = "f29b1528-cb19-40f3-be5c-7241ecb82fd2"
    FLY_CHARACTERISTIC_UUID               = "f29b1526-cb19-40f3-be5c-7241ecb82fd2"
    LED_MATRIX_CHARACTERISTIC_UUID        = "f29b152d-cb19-40f3-be5c-7241ecb82fd2"

    LEGACY_LED_MATRIX_SERVICE             = "f29b1523-cb19-40f3-be5c-7241ecb82fd1"
    LEGACY_LED_MATRIX_CHARACTERISTIC_UUID = "f29b1524-cb19-40f3-be5c-7241ecb82fd1"

    # TODO: Give services their actual names
    UNNAMED1_SERVICE_UUID                 = "00001801-0000-1000-8000-00805f9b34fb"
    UNNAMED2_SERVICE_UUID                 = "0000180a-0000-1000-8000-00805f9b34fb"
    UNNAMED3_SERVICE_UUID                 = "0000180f-0000-1000-8000-00805f9b34fb"

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
            characteristic = next((characteristic for characteristic in nuimo_service.characteristics if characteristic.uuid == characteristic_uuid), None)
            characteristic.enable_notifications()

        # TODO: Only fire `connected` when we read the firmware version or battery value as in other SDKs
        if self.listener:
            self.listener.connected()

    def display_matrix(self, matrix, interval=2.0, brightness=1.0, options=0):
        matrix_bytes = list(map(
            lambda leds: functools.reduce(lambda acc, led: acc + (1 << led if leds[led] else 0), range(0, len(leds)), 0),
            [matrix.leds[i:i + 8] for i in range(0, 81, 8)]))

        # TODO: Support `fading` parameter
        # if fading:
        #     matrix_bytes_list[10] ^= 1 << 4

        # TODO: Support write requests without response
        # TODO: Support ignore duplicate matrix writes

        matrix_bytes += [max(0, min(255, int(brightness * 255.0))), max(0, min(255, int(interval * 10.0)))]

        nuimo_service = next((service for service in self.services if service.uuid == self.NUIMO_SERVICE_UUID), None)
        matrix_characteristic = next((characteristic for characteristic in nuimo_service.characteristics if characteristic.uuid == self.LED_MATRIX_CHARACTERISTIC_UUID), None)
        # TODO: Fallback to legacy led matrix service (this is needed for older Nuimo firmware were the LED characteristic was a separate service)

        matrix_characteristic.write_value(matrix_bytes)

    def characteristic_value_updated(self, characteristic, value):
        {
            self.BUTTON_CHARACTERISTIC_UUID:   self.notify_button_event,
            self.TOUCH_CHARACTERISTIC_UUID:    self.notify_touch_event,
            self.ROTATION_CHARACTERISTIC_UUID: self.notify_rotation_event,
            self.FLY_CHARACTERISTIC_UUID:      self.notify_fly_event
        }[characteristic.uuid](value)

    def notify_button_event(self, value):
        self.notify_gesture_event(gesture=NuimoGesture.BUTTON_RELEASE if value[0] == 0 else NuimoGesture.BUTTON_PRESS)

    def notify_touch_event(self, value):
        gesture = {
            0:  NuimoGesture.SWIPE_LEFT,
            1:  NuimoGesture.SWIPE_RIGHT,
            2:  NuimoGesture.SWIPE_UP,
            3:  NuimoGesture.SWIPE_DOWN,
            4:  NuimoGesture.TOUCH_LEFT,
            5:  NuimoGesture.TOUCH_RIGHT,
            6:  NuimoGesture.TOUCH_TOP,
            7:  NuimoGesture.TOUCH_BOTTOM,
            8:  NuimoGesture.LONGTOUCH_LEFT,
            9:  NuimoGesture.LONGTOUCH_RIGHT,
            10: NuimoGesture.LONGTOUCH_TOP,
            11: NuimoGesture.LONGTOUCH_BOTTOM
        }[value[0]]
        if gesture is not None:
            self.notify_gesture_event(gesture=gesture)

    def notify_rotation_event(self, value):
        rotation_value = value[0] + (value[1] << 8)
        if (value[1] >> 7) > 0:
            rotation_value -= 1 << 16
        self.notify_gesture_event(gesture=NuimoGesture.ROTATION, value=rotation_value)

    def notify_fly_event(self, value):
        if value[0] == 0:
            self.notify_gesture_event(gesture=NuimoGesture.FLY_LEFT)
        elif value[0] == 1:
            self.notify_gesture_event(gesture=NuimoGesture.FLY_RIGHT)
        elif value[0] == 4:
            self.notify_gesture_event(gesture=NuimoGesture.FLY_UPDOWN, value=value[1])

    def notify_gesture_event(self, gesture, value=None):
        if self.listener:
            self.listener.received_gesture_event(NuimoGestureEvent(gesture=gesture, value=value))


class NuimoControllerListener:
    def received_gesture_event(self, event):
        pass

    def started_connecting(self):
        pass

    def connected(self):
        pass

    def started_disconnecting(self):
        pass

    def disconnected(self):
        pass


class NuimoControllerManagerListener:
    def controller_discovered(self, controller):
        pass


# TODO: Extract reusable `GattDeviceDiscovery` class
class NuimoControllerManager:
    def __init__(self, adapter_name="hci0"):
        self.listener = None
        self.bus = dbus.SystemBus()
        self.object_manager = dbus.Interface(self.bus.get_object("org.bluez", '/'), "org.freedesktop.DBus.ObjectManager")

        # TODO: Get adapter from managed objects? See bluezutils.py
        adapter_object = self.bus.get_object("org.bluez", "/org/bluez/" + adapter_name)
        self.adapter = dbus.Interface(adapter_object, "org.bluez.Adapter1")

        self.adapter_name = adapter_name
        self.device_path_regex = re.compile("^/org/bluez/" + adapter_name + "/dev((_[A-Z0-9]{2}){6})$")

        self.bus.add_signal_receiver(
            self.interfaces_added,
            dbus_interface='org.freedesktop.DBus.ObjectManager',
            signal_name='InterfacesAdded')

        self.bus.add_signal_receiver(
            self.properties_changed,
            dbus_interface=dbus.PROPERTIES_IFACE,
            signal_name='PropertiesChanged',
            arg0='org.bluez.Device1',
            path_keyword='path')

    def known_controllers(self):
        #TODO: Return known devices, see https://github.com/bbirand/python-dbus-gatt/blob/master/discovery.py
        return []

    def start_discovery(self):
        # TODO: Support service UUID filter, see http://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc/adapter-api.txt#n57
        scan_filter = {}
        self.adapter.SetDiscoveryFilter({
            "UUIDs": NuimoController.SERVICE_UUIDS,
            "Transport": "le"})
        self.adapter.StartDiscovery()

    def stop_discovery(self):
        self.adapter.StopDiscovery()

    def interfaces_added(self, path, interfaces):
        if (not self.listener) or ('org.bluez.Device1' not in interfaces):
            return
        match = self.device_path_regex.match(path)
        if not match:
            return
        mac_address = match.group(1)[1:].replace("_", ":").lower()
        alias = GattDevice(adapter_name=self.adapter_name, mac_address=mac_address).alias()
        if alias == "Nuimo":
            self.listener.controller_discovered(NuimoController(adapter_name=self.adapter_name, mac_address=mac_address))

    def properties_changed(self, interface, changed, invalidated, path):
        # TODO: Update device's reachability as we get updated RSSI values here every now and then
        # print('properties_changed', interface)
        # if "org.bluez.Device1" in interface:
        #     for prop in changed:
        #         print(interface, path, prop, changed[prop])
        pass


class NuimoControllerPrintListener(NuimoControllerListener):
    def __init__(self, controller):
        self.controller = controller

    def started_connecting(self):
        self.print("connecting...")

    def connected(self):
        self.print("connected")

    def started_disconnecting(self):
        self.print("disconnecting...")

    def disconnected(self):
        self.print("disconnected")

    def received_gesture_event(self, event):
        self.print("did send gesture event " + str(event))

    def print(self, string):
        print("Nuimo controller " + self.controller.mac_address + " " + string)
