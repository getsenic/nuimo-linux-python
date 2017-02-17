import dbus
import dbus.mainloop.glib
import re

from gi.repository import GObject


class DeviceManager:
    def __init__(self, adapter_name):
        self.listener = None
        self.adapter_name = adapter_name

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.mainloop = GObject.MainLoop()
        self.bus = dbus.SystemBus()
        adapter_object = self.bus.get_object('org.bluez', '/org/bluez/' + adapter_name)
        self.adapter = dbus.Interface(adapter_object, 'org.bluez.Adapter1')
        self.device_path_regex = re.compile('^/org/bluez/' + adapter_name + '/dev((_[A-Z0-9]{2}){6})$')

        self._devices = {}
        self._discovered_devices = {}
        self._interface_added_signal = None
        self._properties_changed_signal = None

    def run(self):
        """Starts the main loop that is necessary to receive Bluetooth events from the Bluetooth adapter.
           This call blocks until you call `stop()` to stop the main loop."""

        object_manager = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        mac_addresses = list(filter(None.__ne__, [
            self._mac_address(path)
            for path, _ in object_manager.GetManagedObjects().items()
        ]))
        for mac_address in mac_addresses:
            if self._devices.get(mac_address, None) is not None:
                continue
            self._devices[mac_address] = Device(adapter_name=self.adapter_name, mac_address=mac_address)

        self._interface_added_signal = self.bus.add_signal_receiver(
            self._interfaces_added,
            dbus_interface='org.freedesktop.DBus.ObjectManager',
            signal_name='InterfacesAdded')

        # TODO: Also listen to 'interfaces removed' events?

        self._properties_changed_signal = self.bus.add_signal_receiver(
            self._properties_changed,
            dbus_interface=dbus.PROPERTIES_IFACE,
            signal_name='PropertiesChanged',
            arg0='org.bluez.Device1',
            path_keyword='path')

        self.mainloop.run()

    def stop(self):
        """Stops the main loop started with `start()`"""

        if self._interface_added_signal is not None:
            self._interface_added_signal.remove()
        if self._properties_changed_signal is not None:
            self._properties_changed_signal.remove()

        self.mainloop.quit()

    def devices(self):
        return self._devices()[:]

    def start_discovery(self, service_uuids=[]):
        filter = {'Transport': 'le'}
        if len(service_uuids) > 0:  # D-Bus doesn't like empty lists, needs to guess type
            filter['UUIDs'] = service_uuids
        self._discovered_devices = {}
        self.adapter.SetDiscoveryFilter(filter)
        self.adapter.StartDiscovery()

    def stop_discovery(self):
        pass

    def _interfaces_added(self, path, interfaces):
        self._device_discovered(path, interfaces)

    def _properties_changed(self, interface, changed, invalidated, path):
        # TODO: Handle `changed` and `invalidated` properties and update device
        self._device_discovered(path, [interface])

    def _device_discovered(self, path, interfaces):
        if 'org.bluez.Device1' not in interfaces:
            return
        mac_address = self._mac_address(path)
        if not mac_address:
            return
        device = self._devices.get(mac_address, None)
        if device is None:
            # Should not happen as we listen to "interfaces added" events, but be robust
            device = Device(adapter_name=self.adapter_name, mac_address=mac_address)
            self._devices[mac_address] = device

        if self._discovered_devices.get(mac_address, None) is None:
            self._discovered_devices[mac_address] = device
            if self.listener:
                self.listener.device_discovered(device)
        else:
            device.advertised()

    def _mac_address(self, device_path):
        match = self.device_path_regex.match(device_path)
        if not match:
            return None
        return match.group(1)[1:].replace('_', ':').lower()

    def create_device(self, mac_address):
        pass

    def remove_device(self, mac_address):
        pass


class DeviceManagerListener:
    def device_discovered(self, device):
        pass

    def device_disappeared(self, device):
        pass


class Device:
    def __init__(self, adapter_name, mac_address):
        self.mac_address = mac_address
        self.bus = dbus.SystemBus()
        self.object_manager = dbus.Interface(
            self.bus.get_object('org.bluez', '/'),
            'org.freedesktop.DBus.ObjectManager')

        # TODO: Get adapter from managed objects? See bluezutils.py
        adapter_object = self.bus.get_object('org.bluez', '/org/bluez/' + adapter_name)
        self.adapter = dbus.Interface(adapter_object, 'org.bluez.Adapter1')

        # TODO: Device needs to be created if it's not yet known to bluetoothd, see "test-device" in bluez-5.43/test/
        self.device_path = '/org/bluez/' + adapter_name + '/dev_' + mac_address.replace(':', '_').upper()
        device_object = self.bus.get_object('org.bluez', self.device_path)
        self.object = dbus.Interface(device_object, 'org.bluez.Device1')
        self.services = []

        self.properties = dbus.Interface(self.object, 'org.freedesktop.DBus.Properties')
        self.properties_signal_match = self.properties.connect_to_signal('PropertiesChanged', self.properties_changed)

    def advertised(self):
        """Called when an advertisement package has been received from the device. Requires device discovery to run."""

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
        self._connect_retry_attempt = 0
        self._connect()

    def connect_failed(self, e):
        pass

    def _connect(self):
        self._connect_retry_attempt += 1
        try:
            self.object.Connect()
            if self.is_services_resolved():
                self.services_resolved()
        except dbus.exceptions.DBusException as e:
            if (e.get_dbus_name() == 'org.freedesktop.DBus.Error.UnknownObject'):
                self.connect_failed(Exception("Nuimo Controller does not exist, check adapter name and MAC address."))
            elif ((e.get_dbus_name() == 'org.bluez.Error.Failed') and
                  (e.get_dbus_message() == "Operation already in progress")):
                pass
            elif ((self._connect_retry_attempt < 5) and
                  (e.get_dbus_name() == 'org.bluez.Error.Failed') and
                  (e.get_dbus_message() == "Software caused connection abort")):
                self._connect()
            elif (e.get_dbus_name() == 'org.freedesktop.DBus.Error.NoReply'):
                # TODO: How to handle properly?
                # Reproducable when we repeatedly shut off Nuimo immediately after its flashing Bluetooth icon appears
                self.connect_failed(e)
            else:
                self.connect_failed(e)

    def disconnect(self):
        self.object.Disconnect()

    def connected(self):
        """Will be called when `connect()` has finished connecting to the device.
           Will not be called if the device was already connected."""
        pass

    def disconnected(self):
        """Will be called when the device has disconnected"""
        pass

    def is_connected(self):
        return self.properties.Get('org.bluez.Device1', 'Connected') == 1

    def is_services_resolved(self):
        return self.properties.Get('org.bluez.Device1', 'ServicesResolved') == 1

    def alias(self):
        return self.properties.Get('org.bluez.Device1', 'Alias')

    def properties_changed(self, sender, changed_properties, invalidated_properties):
        if 'Connected' in changed_properties:
            if changed_properties['Connected']:
                self.connected()
            else:
                self.disconnected()

        if 'ServicesResolved' in changed_properties and changed_properties['ServicesResolved'] == 1:
            self.services_resolved()

    def services_resolved(self):
        self.invalidate_services()

        services_regex = re.compile(self.device_path + '/service[0-9abcdef]{4}$')
        managed_services = [
            service for service in self.object_manager.GetManagedObjects().items()
            if services_regex.match(service[0])]
        self.services = [Service(
            device=self,
            path=service[0],
            uuid=service[1]['org.bluez.GattService1']['UUID']) for service in managed_services]

    def characteristic_value_updated(self, characteristic, value):
        # To be implemented by subclass
        pass


class Service:
    def __init__(self, device, path, uuid):
        self.device = device
        self.path = path
        self.uuid = uuid
        self.bus = device.bus
        self.object_manager = device.object_manager
        self.object = self.bus.get_object('org.bluez', path)
        self.characteristics = []
        self.characteristics_resolved()

    def invalidate(self):
        self.invalidate_characteristics()

    def invalidate_characteristics(self):
        for characteristic in self.characteristics:
            characteristic.invalidate()

    def characteristics_resolved(self):
        self.invalidate_characteristics()

        characteristics_regex = re.compile(self.path + '/char[0-9abcdef]{4}$')
        managed_characteristics = [
            char for char in self.object_manager.GetManagedObjects().items()
            if characteristics_regex.match(char[0])]
        self.characteristics = [Characteristic(
            service=self,
            path=c[0],
            uuid=c[1]['org.bluez.GattCharacteristic1']['UUID']) for c in managed_characteristics]


class Characteristic:
    def __init__(self, service, path, uuid):
        self.service = service
        self.path = path
        self.uuid = uuid
        self.bus = service.bus
        self.object_manager = service.object_manager
        self.object = self.bus.get_object('org.bluez', path)
        self.properties = dbus.Interface(self.object, "org.freedesktop.DBus.Properties")
        self.properties_signal = self.properties.connect_to_signal('PropertiesChanged', self.properties_changed)

    def invalidate(self):
        self.properties_signal.remove()

    def properties_changed(self, properties, changed_properties, invalidated_properties):
        value = changed_properties.get('Value')
        if value is not None:
            self.service.device.characteristic_value_updated(characteristic=self, value=bytes(value))

    def write_value(self, bytes, offset=0):
        bytes = [dbus.Byte(b) for b in bytes]
        self.object.WriteValue(
            bytes,
            {'offset': dbus.Byte(offset, variant_level=1)},
            reply_handler=self.write_value_succeeded,
            error_handler=self.write_value_failed,
            dbus_interface='org.bluez.GattCharacteristic1')

    def write_value_succeeded(self):
        print('write_value_succeeded')

    def write_value_failed(self, error):
        print('write_value_failed', error)

    def enable_notifications(self):
        self.object.StartNotify(
            reply_handler=self.enable_notifications_succeeded,
            error_handler=self.enable_notifications_failed,
            dbus_interface='org.bluez.GattCharacteristic1')

    def enable_notifications_succeeded(self):
        print('notification_enabling_succeeded')

    def enable_notifications_failed(self, error):
        if ((error.get_dbus_name() == 'org.bluez.Error.Failed') and
            (error.get_dbus_message() == "Already notifying")):
            return
        print('notification_enabling_failed', error)
