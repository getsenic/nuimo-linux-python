#!/usr/bin/env python

"""
nuimocore.py - Python API for Senic Nuimo Controller
"""
# Copyright (c) 2016 Senic. All rights reserved.
#
# This software may be modified and distributed under the terms
# of the MIT license.  See the LICENSE file for details.

import functools
import logging

from threading import Event
from gattlib import GATTRequester, DiscoveryService
import gattlib

_LOGGER = logging.getLogger(__name__)
_LOGGER.addHandler(logging.NullHandler())
_LOGGER.setLevel(logging.INFO)


class NuimoEvent(object):
    pass


class NuimoGestureEvent(NuimoEvent):
    """Describe a Nuimo Controller Gesture Event
    The event has properties gesture, name and value.
    For example,

    >>> event = NuimoGestureEvent(NuimoGestureEvent.ROTATE, 20)  # Rotated by 20 clicks
    >>> print([event.gesture, event.value, event.name])
    [3, 20, 'ROTATE']
    """

    # Event codes
    BUTTON_PRESS = 1
    BUTTON_RELEASE = 2
    ROTATE = 3
    SWIPE_LEFT = 4
    SWIPE_RIGHT = 5
    SWIPE_UP = 6
    SWIPE_DOWN = 7
    TOUCH_LEFT = 8
    TOUCH_RIGHT = 9
    TOUCH_TOP = 10
    TOUCH_BOTTOM = 11
    FLY_LEFT = 12
    FLY_RIGHT = 13
    FLY_BACKWARDS = 14
    FLY_TOWARD = 15
    FLY_UP_DOWN = 16

    event_names = {
        1: 'BUTTON_PRESS',
        2: 'BUTTON_RELEASE',
        3: 'ROTATE',
        4: 'SWIPE_LEFT',
        5: 'SWIPE_RIGHT',
        6: 'SWIPE_UP',
        7: 'SWIPE_DOWN',
        8: 'TOUCH_LEFT',
        9: 'TOUCH_RIGHT',
        10: 'TOUCH_TOP',
        11: 'TOUCH_BOTTOM',
        12: 'FLY_LEFT',
        13: 'FLY_RIGHT',
        14: 'FLY_BACKWARDS',
        15: 'FLY_TOWARD',
        16: 'FLY_UP_DOWN'
    }

    def __init__(self, gesture, value):
        self._gesture = gesture
        self._value = value

    def __str__(self):
        s = "NuimoGestureEvent({}, {})".format(self.name, self._value)
        return s

    @property
    def value(self):
        """Event value"""
        return self._value

    @property
    def gesture(self):
        """Event gesture code as an integer"""
        return self._gesture

    @property
    def name(self):
        """Event gesture code as a string"""
        return self.event_names.get(self.gesture, 'UNKNOWN')


class NuimoControllerDelegate(object):
    """
    Handle Nuimo Controller event callbacks.
    Inherit from this class if you are only interested in a few events.
    By default all events are ignored.
    If you want to trace the events use NuimoControllerLoggingDelegate.
    """
    def __init__(self, controller):
        self.controller = controller

    def connection_state_changed(self, state, error=None):
        pass

    def received_gesture_event(self, event):
        pass

    def displayed_led_matrix(self):
        pass


class NuimoControllerLoggingDelegate:
    """
    Handle Nuimo Controller event callbacks by logging them.
    """
    def __init__(self, controller, logger=logging):
        self.controller = controller
        self.logger = logger

    def connection_state_changed(self, state):
        self.logger.debug("{}.connection_state_changed, {}".format(self.controller.addr, state))

    def received_gesture_event(self, event):
        self.logger.debug("{}.received_gesture_event, {}".format(self.controller.addr, event))

    def displayed_led_matrix(self):
        self.logger.debug("{}.displayed_led_matrix".format(self.controller.addr))


class NuimoController(gattlib.GATTRequester):
    """
    Represent a Nuimo Controller
    """

    def __init__(self, addr):
        """addr is a Nuimo controller mac address"""
        super(NuimoController, self).__init__(addr, False)
        self.thread_event = Event()
        self.characteristics_by_name = {}
        self.characteristics_by_uuid = {}
        self.characteristics_by_handle = {}
        self.device_characteristics = {}
        self.addr = addr
        self.delegate = None
        self.default_matrix_display_interval = 2.0  # display_interval = 2 seconds
        self.display_brightness = 1.0  # max brightness

    def _setup_mappings(self):
        # Bluetooth characteristics by name and UUID
        characteristics_table = [
            ('BUTTON',     'f29b1529-cb19-40f3-be5c-7241ecb82fd2', self.button_event),
            ('ROTATION',   'f29b1528-cb19-40f3-be5c-7241ecb82fd2', self.rotation_event),
            ('SWIPE',      'f29b1527-cb19-40f3-be5c-7241ecb82fd2', self.swipe_event),
            ('FLY',        'f29b1526-cb19-40f3-be5c-7241ecb82fd2', self.fly_event),
            ('LED_MATRIX', 'f29b1524-cb19-40f3-be5c-7241ecb82fd1', None)
        ]

        for (name, uuid, constructor) in characteristics_table:
            char = {'name': name, 'uuid': uuid, 'constructor': constructor, 'value_handle': None}
            self.characteristics_by_name[name] = char
            self.characteristics_by_uuid[uuid] = char

        # add mappings for the device characteristic handles
        for device_char in self.device_characteristics:
            uuid = device_char['uuid']
            char = self.characteristics_by_uuid.get(uuid)
            # Ignore uuids we don't support
            if char:
                char['value_handle'] = device_char['value_handle']
                self.characteristics_by_handle[char['value_handle']] = char

    def __str__(self):
        return "NuimoController({})".format(self.addr)

    def set_delegate(self, delegate):
        """Set up handling of Nuimo events."""
        self.delegate = delegate

    # Controller connection states
    CONNECTING = 1
    CONNECTED = 2
    DISCONNECTING = 3
    DISCONNECTED = 4

    def connect(self, **kwargs):
        """Attach to a Nuimo controller"""
        self.log('connecting')
        GATTRequester.connect(self, wait=True, channel_type="random")
        self.log('connected')
        self._get_characteristics()
        self._setup_mappings()
        self.enable_notifications()

    def _get_characteristics(self):
        self.log('discovering characteristics')
        self.device_characteristics = self.discover_characteristics()
        self.log('discovered {} characteristics'.format(len(self.device_characteristics)))
        self.debug("\n".join(map(str, self.device_characteristics)))

    def _dispatch_event(self, event):
        """ Call the delegate's appropriate event callback """
        if not self.delegate:
            return
        self.delegate.received_gesture_event(event)

    @staticmethod
    def rotation_event(received_data):
        rotation_value = ord(received_data[3]) + (ord(received_data[4]) << 8)
        if rotation_value >= 1 << 15:
            rotation_value -= 1 << 16

        event = NuimoGestureEvent(NuimoGestureEvent.ROTATE, rotation_value)
        return event

    @staticmethod
    def fly_event(received_data):
        directions = [NuimoGestureEvent.FLY_LEFT, NuimoGestureEvent.FLY_RIGHT,
                      NuimoGestureEvent.FLY_TOWARD, NuimoGestureEvent.FLY_BACKWARDS,
                      NuimoGestureEvent.FLY_UP_DOWN]
        fly_direction = ord(received_data[3])
        event_kind = directions[fly_direction]
        event = NuimoGestureEvent(event_kind, fly_direction)
        return event

    @staticmethod
    def swipe_event(received_data):
        directions = [NuimoGestureEvent.SWIPE_LEFT, NuimoGestureEvent.SWIPE_RIGHT,
                      NuimoGestureEvent.SWIPE_UP, NuimoGestureEvent.SWIPE_DOWN, 
                      NuimoGestureEvent.TOUCH_LEFT, NuimoGestureEvent.TOUCH_RIGHT,
                      NuimoGestureEvent.TOUCH_TOP, NuimoGestureEvent.TOUCH_BOTTOM ]
        swipe_direction = ord(received_data[3])
        event_kind = directions[swipe_direction]
        event = NuimoGestureEvent(event_kind, swipe_direction)
        return event

    @staticmethod
    def button_event(received_data):
        button_direction = ord(received_data[3])
        event_kind = NuimoGestureEvent.BUTTON_PRESS if button_direction != 0 else NuimoGestureEvent.BUTTON_RELEASE
        event = NuimoGestureEvent(event_kind, button_direction)
        return event

    # Override GATTRequester superclass
    def on_notification(self, handle, data):
        self.debug('on_notification(handle={}, {})'.format(handle, list(data)))

        uuid = self.value_handle_to_uuid(handle)

        self.debug('on_notification(handle={}, uuid={})'.format(handle, uuid))

        event = self.event_factory(data, uuid)

        if event is None:
            raise RuntimeError('Nuimo Controller could not construct event for uuid={}'
                               .format(uuid))
        self._dispatch_event(event)

    def event_factory(self, received_data, uuid):
        item = self.characteristics_by_uuid.get(uuid)
        event = item['constructor'](received_data)
        return event

    def value_handle_to_uuid(self, handle):
        return self.characteristics_by_handle.get(handle)['uuid']

    def enable_notifications(self):
        for uuid, item in self.characteristics_by_uuid.items():
            if item['constructor']:  # has events
                self.enable_notification(uuid)

    def enable_notification(self, uuid):
        name = self.characteristics_by_uuid.get(uuid)['name']
        self.log('enable_notification {}'.format(name))

        notification_handle = self.value_handle(uuid) + 1
        notification_on_bytearray = bytes(bytearray([1, 0]))

        self.write_by_handle(notification_handle, notification_on_bytearray)
        self.debug('done.... for {}, handle {}'.format(name, notification_handle))

    def value_handle(self, uuid):
        handle = self.characteristics_by_uuid.get(uuid)['value_handle']
        if not handle:
            raise RuntimeError('Nuimo Controller characteristic not found for uuid {}'
                               .format(uuid))
        return handle

    def write_matrix(self, matrix, timeout, brightness=1.0):
        """Display LEDs on Nuimo"""

        matrix = '{:<81}'.format(matrix[:81])
        matrix_bytes_list = list(map(lambda leds: functools.reduce(
            lambda acc, led: acc + (1 << led if leds[led] not in [' ', '0'] else 0),
            range(0, len(leds)), 0), [matrix[i:i + 8] for i in range(0, len(matrix), 8)]))

        timeout = max(0, min(255, int(timeout * 10.0)))
        brightness = max(0, min(255, int(255.0 * brightness)))
        matrix_bytes_list.append(brightness)
        matrix_bytes_list.append(timeout)

        led_data = bytearray(matrix_bytes_list)
        led_uuid = self.characteristics_by_name['LED_MATRIX']['uuid']
        led_handle = self.value_handle(led_uuid)
        self.write_by_handle(led_handle, bytes(led_data))

    def log(self, msg):
        _LOGGER.info("%s: %s", self.addr, msg)

    def debug(self, msg):
        _LOGGER.debug("%s: %s", self.addr, msg)


class NuimoDiscoveryManager(object):
    def __init__(self, bluetooth_adapter='hci0', timeout=5, delegate=None):
        self.timeout = timeout
        self.adapter = bluetooth_adapter
        self.delegate = delegate
        self.nuimos = []
        self.discovery_service = gattlib.DiscoveryService(bluetooth_adapter)

    def start_discovery(self):
        self.log("started Nuimo discovery")
        if self.delegate:
            self.delegate.discovery_started()
        all_discovered_devices = self.discovery_service.discover(int(self.timeout))
        self.log_devices(all_discovered_devices)
        self.nuimos = self.create_nuimos(all_discovered_devices)
        self.log_nuimos(self.nuimos)
        self.fire_callbacks()
        if self.delegate:
            self.delegate.discovery_finished()

    def stop_discovery(self):
        self.log("stopped Nuimo discovery")

    @staticmethod
    def filter_nuimos(devices):
        return [addr for addr, attrs in devices.items() if attrs.get('name') == 'Nuimo']

    def create_nuimos(self, devices):
        return [NuimoController(device) for device in self.filter_nuimos(devices)]

    def fire_callbacks(self):
        if not self.delegate:
            return

        [self.delegate.controller_added(nuimo) for nuimo in self.nuimos]

    def log_devices(self, devices):
        for device, attrs in devices.items():
            self.log("discovered Bluetooth device {}, {}".format(device, attrs))

    def log_nuimos(self, nuimos):
        for nuimo in nuimos:
            self.log(nuimo)

    def log(self, msg):
        _LOGGER.info("%s, %s", self.adapter, msg)
