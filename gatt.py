import dbus
import re


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
        pass

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
