#!/usr/bin/env python3

import dbus
import sys
from argparse import ArgumentParser
from nuimo_dbus import *
from gi.repository import GObject

mainloop = GObject.MainLoop()

class NuimoControllerTestListener(NuimoControllerPrintListener):
    def __init__(self, controller, auto_reconnect=False):
        super().__init__(controller)
        self.auto_reconnect = auto_reconnect

    def connect_failed(self, error):
        super().connect_failed(error)
        mainloop.quit()
        sys.exit(0)

    def disconnected(self):
        super().disconnected()

        if self.auto_reconnect:
            # Reconnect as soon as Nuimo was disconnected
            print("Disconnected, reconnecting...")
            self.controller.connect()
        else:
            mainloop.quit()
            sys.exit(0)

    def received_gesture_event(self, event):
        super().received_gesture_event(event)
        self.controller.display_matrix(NuimoLedMatrix(
            "*        "
            " *       "
            "  *      "
            "   *     "
            "    *    "
            "     *   "
            "      *  "
            "       * "
            "        *"))


class NuimoControllerManagerPrintListener(NuimoControllerManagerListener):
    def controller_discovered(self, controller):
        print("Discovered Nuimo controller", controller.mac_address)


class NuimoControllerManagerPrintListener(NuimoControllerManagerListener):
    def controller_discovered(self, controller):
        print("Discovered Nuimo controller", controller.mac_address)


if __name__ == '__main__':
    arg_parser = ArgumentParser(description='Nuimo Controller Demo')
    arg_commands_group = arg_parser.add_mutually_exclusive_group(required=True)
    arg_commands_group.add_argument('--discover', action='store_true')
    arg_commands_group.add_argument('--connect', metavar='address', type=str, help='Connect to a Nuimo controller with a given MAC address')
    arg_commands_group.add_argument('--auto', metavar='address', type=str, help='Connect and automatically reconnect to a Nuimo controller with a given MAC address')
    arg_commands_group.add_argument('--disconnect', metavar='address', type=str, help='Disconnect a Nuimo controller with a given MAC address')
    args = arg_parser.parse_args()

    print("Terminate with Ctrl+C")
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    if args.discover:
        controller_manager = NuimoControllerManager(adapter_name="hci0")
        controller_manager.listener = NuimoControllerManagerPrintListener()
        controller_manager.start_discovery()
    elif args.connect:
        controller = NuimoController(adapter_name="hci0", mac_address=args.connect)
        controller.listener = NuimoControllerTestListener(controller=controller)
        controller.connect()
    elif args.auto:
        controller = NuimoController(adapter_name="hci0", mac_address=args.auto)
        controller.listener = NuimoControllerTestListener(controller=controller, auto_reconnect=True)
        controller.connect()
    elif args.disconnect:
        controller = NuimoController(adapter_name="hci0", mac_address=args.disconnect)
        controller.listener = NuimoControllerTestListener(controller=controller)
        controller.disconnect()

    mainloop.run()
