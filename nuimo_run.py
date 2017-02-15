#!/usr/bin/env python3

from nuimo_dbus import *

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
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    #controller = NuimoController(adapter_name="hci0", mac_address="FC:52:6E:8E:87:06")
    #controller = NuimoController(adapter_name="hci0", mac_address="C4:54:31:CD:DD:07")

    #controller.listener = NuimoControllerTestListener(controller=controller)

    #print("Connected:", controller.is_connected())
    #controller.disconnect()
    #controller.connect()

    controller_manager = NuimoControllerManager(adapter_name="hci0")
    controller_manager.listener = NuimoControllerManagerPrintListener()
    controller_manager.start_discovery()

    print("Entering main loop. Exit with Ctrl+C")
    mainloop = GObject.MainLoop()
    mainloop.run()
