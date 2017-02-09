#!/usr/bin/env python3

import dbus
import dbus.mainloop.glib
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
        self.device_path = "/org/bluez/" + adapter_name + "/dev_" + mac_address.replace(":", "_")
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

    def disconnect(self):
        self.object.Disconnect()

    def is_connected(self):
        return self.properties.Get("org.bluez.Device1", "Connected") == 1

    def properties_changed(self, sender, changed_properties, invalidated_properties):
        print("Properties changed", sender, changed_properties)
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
        print("'" + string + "'")


class NuimoController(GattDevice):
    NUIMO_SERVICE_UUID           = "f29b1525-cb19-40f3-be5c-7241ecb82fd2"
    BUTTON_CHARACTERISTIC_UUID   = "f29b1529-cb19-40f3-be5c-7241ecb82fd2"
    TOUCH_CHARACTERISTIC_UUID    = "f29b1527-cb19-40f3-be5c-7241ecb82fd2"
    ROTATION_CHARACTERISTIC_UUID = "f29b1528-cb19-40f3-be5c-7241ecb82fd2"
    FLY_CHARACTERISTIC_UUID      = "f29b1526-cb19-40f3-be5c-7241ecb82fd2"

    def __init__(self, adapter_name, mac_address):
        super().__init__(adapter_name, mac_address)
        self.listener = None

    def properties_changed(self, sender, changed_properties, invalidated_properties):
        super().properties_changed(sender, changed_properties, invalidated_properties)

        connected = changed_properties.get("Connected")
        if (connected == 0) and self.listener:
            self.listener.disconnected()

    def connect(self):
        if self.listener:
            self.listener.started_connecting()
        super().connect()

    def disconnect(self):
        if self.listener:
            self.listener.started_disconnecting()
        super().disconnect()

    def services_resolved(self):
        super().services_resolved()

        for service in self.services:
            print(service.path, service.uuid)
            for characteristic in service.characteristics:
                print("   ", characteristic.path, characteristic.uuid)

        nuimo_service = next(service for service in self.services if service.uuid == "f29b1525-cb19-40f3-be5c-7241ecb82fd2")

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


class NuimoControllerTestListener(NuimoControllerPrintListener):
    def __init__(self, controller):
        super().__init__(controller)

    def disconnected(self):
        super().disconnected()

        # Reconnect as soon as Nuimo was disconnected
        # TODO: Only reconnect if `disconnect` was not called – add an error parameter to this callback
        print("Disconnected, reconnecting...")
        self.controller.connect()


if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    controller = NuimoController(adapter_name="hci0", mac_address="FC:52:6E:8E:87:06")
    #controller = NuimoController(adapter_name="hci0", mac_address="C4:54:31:CD:DD:07")

    controller.listener = NuimoControllerTestListener(controller=controller)

    print("Connected:", controller.is_connected())

    controller.disconnect()
    controller.connect()

    print("Entering main loop. Exit with Ctrl+C")
    mainloop = GObject.MainLoop()
    mainloop.run()
