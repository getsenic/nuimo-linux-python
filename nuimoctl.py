#!/usr/bin/env python3

import sys
from argparse import ArgumentParser
import nuimo

controller_manager = None


class ControllerPrintListener(nuimo.ControllerListener):
    """
    An implementation of ``ControllerListener`` that prints each event.
    """
    def __init__(self, controller):
        self.controller = controller

    def started_connecting(self):
        self.print("connecting...")

    def connect_succeeded(self):
        self.print("connected")

    def connect_failed(self, error):
        self.print("connect failed: " + str(error))

    def started_disconnecting(self):
        self.print("disconnecting...")

    def disconnect_succeeded(self):
        self.print("disconnected")

    def received_gesture_event(self, event):
        self.print("did send gesture event " + str(event))

    def print(self, string):
        print("Nuimo controller " + self.controller.mac_address + " " + string)


class ControllerTestListener(ControllerPrintListener):
    def __init__(self, controller, auto_reconnect=False):
        super().__init__(controller)
        self.auto_reconnect = auto_reconnect

    def connect_failed(self, error):
        super().connect_failed(error)
        controller_manager.stop()
        sys.exit(0)

    def disconnect_succeeded(self):
        super().disconnect_succeeded()

        if self.auto_reconnect:
            # Reconnect as soon as Nuimo was disconnected
            print("Disconnected, reconnecting...")
            self.controller.connect()
        else:
            controller_manager.stop()
            sys.exit(0)

    def received_gesture_event(self, event):
        super().received_gesture_event(event)
        self.controller.display_matrix(nuimo.LedMatrix(
            "*        "
            " *       "
            "  *      "
            "   *     "
            "    *    "
            "     *   "
            "      *  "
            "       * "
            "        *"))


class ControllerManagerPrintListener(nuimo.ControllerManagerListener):
    def controller_discovered(self, controller):
        print("Discovered Nuimo controller", controller.mac_address)


def main():
    arg_parser = ArgumentParser(description="Nuimo Controller Demo")
    arg_parser.add_argument(
        '--adapter',
        default='hci0',
        help="Name of Bluetooth adapter, defaults to 'hci0'")
    arg_commands_group = arg_parser.add_mutually_exclusive_group(required=True)
    arg_commands_group.add_argument(
        '--discover',
        action='store_true',
        help="Lists all nearby Nuimo controllers")
    arg_commands_group.add_argument(
        '--connect',
        metavar='address',
        type=str,
        help="Connect to a Nuimo controller with a given MAC address")
    arg_commands_group.add_argument(
        '--auto',
        metavar='address',
        type=str,
        help="Connect and automatically reconnect to a Nuimo controller with a given MAC address")
    arg_commands_group.add_argument(
        '--disconnect',
        metavar='address',
        type=str,
        help="Disconnect a Nuimo controller with a given MAC address")
    args = arg_parser.parse_args()

    global controller_manager
    controller_manager = nuimo.ControllerManager(adapter_name=args.adapter)

    if args.discover:
        controller_manager.listener = ControllerManagerPrintListener()
        controller_manager.start_discovery()
    elif args.connect:
        controller = nuimo.Controller(adapter_name=args.adapter, mac_address=args.connect)
        controller.listener = ControllerTestListener(controller=controller)
        controller.connect()
    elif args.auto:
        controller = nuimo.Controller(adapter_name=args.adapter, mac_address=args.auto)
        controller.listener = ControllerTestListener(controller=controller, auto_reconnect=True)
        controller.connect()
    elif args.disconnect:
        controller = nuimo.Controller(adapter_name=args.adapter, mac_address=args.disconnect)
        if not controller.is_connected():
            print("Already disconnected")
            return
        controller.listener = ControllerTestListener(controller=controller)
        controller.disconnect()

    print("Terminate with Ctrl+C")
    try:
        controller_manager.run()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
