#!/usr/bin/env python3

from argparse import ArgumentParser
from nuimo_dbus import *
from gi.repository import GObject

class NuimoControllerTestListener(NuimoControllerPrintListener):
    def __init__(self, controller):
        super().__init__(controller)

    def disconnected(self):
        super().disconnected()

        # Reconnect as soon as Nuimo was disconnected
        # TODO: Only reconnect if `disconnect` was not called – add an error parameter to this callback
        print("Disconnected, reconnecting...")
        self.controller.connect()

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
    args = arg_parser.parse_args()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    if args.discover:
        controller_manager = NuimoControllerManager(adapter_name="hci0")
        controller_manager.listener = NuimoControllerManagerPrintListener()
        controller_manager.start_discovery()
    elif args.connect:
        controller = NuimoController(adapter_name="hci0", mac_address=args.connect)
        controller.listener = NuimoControllerTestListener(controller=controller)
        print("Connected:", controller.is_connected())
        controller.disconnect()
        controller.connect()

    print("Entering main loop. Exit with Ctrl+C")
    mainloop = GObject.MainLoop()
    mainloop.run()
