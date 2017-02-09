#!/usr/bin/env python3

import dbus
import dbus.mainloop.glib
import gi.repository.GLib

def interfaces_added(path, interfaces):
    print('interfaces_added')
    if 'org.bluez.Device1' in interfaces:
        print('Device added at {}'.format(path))

def properties_changed(interface, changed, invalidated, path):
    print('properties_changed')
    if constants.DEVICE_INTERFACE in interface:
        for prop in changed:
            print(interface, path, prop, changed[prop])

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SystemBus()
    adapter_object = bus.get_object('org.bluez', '/org/bluez/hci0')
    adapter = dbus.Interface(adapter_object, 'org.bluez.Adapter1')

    print(adapter)

    bus.add_signal_receiver(
        interfaces_added,
        dbus_interface='org.freedesktop.DBus.ObjectManager',
        signal_name='InterfacesAdded')

    bus.add_signal_receiver(
        properties_changed,
        dbus_interface=dbus.PROPERTIES_IFACE,
        signal_name='PropertiesChanged',
        arg0='org.bluez.Device1',
        path_keyword='path')

    #TODO: Get known devices, see https://github.com/bbirand/python-dbus-gatt/blob/master/discovery.py
    adapter.StartDiscovery()

    mainloop = gi.repository.GLib.MainLoop()
    mainloop.run()

