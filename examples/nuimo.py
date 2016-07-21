
# Copyright (c) 2016 Senic. All rights reserved.
#
# This software may be modified and distributed under the terms
# of the MIT license.  See the LICENSE file for details.

"""nuimo.py - Sample code for Nuimo controller"""

import time
import sys
from nuimocore import NuimoDiscoveryManager


def main():
    # Uncomment the next 2 lines to enable detailed logging
    # import logging
    # logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Discover Nuimo Controllers
    # Note:
    #   1) Discovery is a synchronous operation i.e. other Python activity is paused
    #   2) Discovery must be run as the root user
    #   3) If the Nuimo MAC address is known, the NuimoController can be instantiated directly.
    #      For example:
    #          nuimo = NuimoController('D0:DF:D2:8F:49:B6')

    adapter = 'hci0'  # Typical bluetooth adapter name
    nuimo_manager = NuimoDiscoveryManager(bluetooth_adapter=adapter, delegate=DiscoveryLogger())
    nuimo_manager.start_discovery()

    # Were any Nuimos found?
    if len(nuimo_manager.nuimos) == 0:
        print('No Nuimos detected')
        sys.exit(0)

    # Take the first Nuimo found.
    nuimo = nuimo_manager.nuimos[0]

    # Set up handling of Nuimo events.
    # In this case just log each incoming event.
    # NuimoLogger is defined below.
    nuimo_event_delegate = NuimoLogger()
    nuimo.set_delegate(nuimo_event_delegate)

    # Attach to the Nuimo.
    nuimo.connect()

    # Display an icon for 2 seconds
    interval = 2.0
    print("Displaying LED Matrix...")
    nuimo.write_matrix(MATRIX_SHUFFLE, interval)

    # Nuimo events are dispatched in the background
    time.sleep(100000)

    nuimo.disconnect()

# Example matrix for the Nuimo display
# Must be 9x9 characters.
MATRIX_SHUFFLE = (
    "         " +
    "         " +
    " ..   .. " +
    "   . .   " +
    "    .    " +
    "   . .   " +
    " ..   .. " +
    "         " +
    "         ")


class DiscoveryLogger:
    """ Handle Nuimo Discovery callbacks. """
    def controller_added(self, nuimo):
        print("added Nuimo: {}".format(nuimo))


class NuimoLogger:
    """ Handle Nuimo Controller event callbacks by printing the events. """

    def received_gesture_event(self, event):
        print("received event: name={}, gesture_id={}, value={}".format(event.name, event.gesture, event.value))

if __name__ == '__main__':
    main()
