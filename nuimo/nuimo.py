import functools
import gatt
from datetime import datetime
from enum import Enum


class ControllerManager(gatt.DeviceManager):
    """
    Entry point for managing and discovering Nuimo ``Controller``s.
    """

    def __init__(self, adapter_name='hci0'):
        """
        Instantiates a ``ControllerManager``

        :param adapter_name: name of Bluetooth adapter used by this controller manager
        """
        super().__init__(adapter_name)
        self.listener = None
        self.discovered_controllers = {}

    def controllers(self):
        """
        Returns all known Nuimo controllers.
        """
        return self.devices()

    def start_discovery(self):
        """
        Starts a Bluetooth discovery for Nuimo controllers.

        Assign a `ControllerManagerListener` to the `listener` attribute to collect discovered Nuimos.
        """
        self._discovered_controllers = {}
        super().start_discovery(service_uuids=Controller.SERVICE_UUIDS)

    def make_device(self, mac_address):
        device = super().make_device(mac_address)
        if device.alias() != 'Nuimo':
            return None
        return Controller(adapter_name=self.adapter_name, mac_address=mac_address)

    def device_discovered(self, device):
        super().device_discovered(device)
        if device.mac_address in self.discovered_controllers:
            return
        self.discovered_controllers[device.mac_address] = device
        if self.listener is not None:
            self.listener.controller_discovered(device)


class ControllerManagerListener:
    """
    Base class for receiving discovery events from ``ControllerManager``.

    Assign an instance of your subclass to the ``listener`` attribute of your
    ``ControllerManager`` to receive discovery events.
    """
    def controller_discovered(self, controller):
        """
        This method gets called once for each Nuimo controller discovered nearby.

        :param controller: the Nuimo controller that was discovered
        """
        pass


class Controller(gatt.Device):
    """
    This class represents a Nuimo controller.

    Obtain instances of this class by using the discovery mechanism of
    ``ControllerManager`` or by manually creating an instance.

    Assign an instance of ``ControllerListener`` to the ``listener`` attribute to
    receive all Nuimo related events such as connection, disconnection and user input.

    :ivar adapter_name: name of Bluetooth adapter that can connect to this controller
    :ivar mac_address: MAC address of this Nuimo controller
    :ivar listener: instance of ``ControllerListener`` that will be notified with all events
    """
    NUIMO_SERVICE_UUID                    = 'f29b1525-cb19-40f3-be5c-7241ecb82fd2'
    BUTTON_CHARACTERISTIC_UUID            = 'f29b1529-cb19-40f3-be5c-7241ecb82fd2'
    TOUCH_CHARACTERISTIC_UUID             = 'f29b1527-cb19-40f3-be5c-7241ecb82fd2'
    ROTATION_CHARACTERISTIC_UUID          = 'f29b1528-cb19-40f3-be5c-7241ecb82fd2'
    FLY_CHARACTERISTIC_UUID               = 'f29b1526-cb19-40f3-be5c-7241ecb82fd2'
    LED_MATRIX_CHARACTERISTIC_UUID        = 'f29b152d-cb19-40f3-be5c-7241ecb82fd2'

    LEGACY_LED_MATRIX_SERVICE             = 'f29b1523-cb19-40f3-be5c-7241ecb82fd1'
    LEGACY_LED_MATRIX_CHARACTERISTIC_UUID = 'f29b1524-cb19-40f3-be5c-7241ecb82fd1'

    # TODO: Give services their actual names
    UNNAMED1_SERVICE_UUID                 = '00001801-0000-1000-8000-00805f9b34fb'
    UNNAMED2_SERVICE_UUID                 = '0000180a-0000-1000-8000-00805f9b34fb'
    UNNAMED3_SERVICE_UUID                 = '0000180f-0000-1000-8000-00805f9b34fb'

    SERVICE_UUIDS = [
        NUIMO_SERVICE_UUID,
        LEGACY_LED_MATRIX_SERVICE,
        UNNAMED1_SERVICE_UUID,
        UNNAMED2_SERVICE_UUID,
        UNNAMED3_SERVICE_UUID]

    def __init__(self, adapter_name, mac_address):
        """
        Create an instance with given Bluetooth adapter name and MAC address.

        :param adapter_name: name of the Bluetooth adapter, i.e. ``hci0`` (default)
        :param mac_address: MAC address of Nuimo controller with format: ``AA:BB:CC:DD:EE:FF``
        """
        super().__init__(adapter_name, mac_address)
        self.listener = None
        self._matrix_writer = _LedMatrixWriter(controller=self)

    def connect(self):
        """
        Tries to connect to this Nuimo controller and blocks until it has connected
        or failed to connect.

        Notifies ``listener`` as soon has the connection has succeeded or failed.
        """
        if self.listener:
            self.listener.started_connecting()
        super().connect()

    def connect_succeded(self):
        super().connect_succeeded()

    def connect_failed(self, error):
        if self.listener:
            self.listener.connect_failed(error)

    def disconnect(self):
        """
        Disconnects this Nuimo controller if connected.

        Notifies ``listener`` as soon as Nuimo was disconnected.
        """
        if self.listener:
            self.listener.started_disconnecting()
        super().disconnect()

    def disconnect_succeeded(self):
        super().disconnect_succeeded()
        if self.listener:
            self.listener.disconnect_succeeded()

    def services_resolved(self):
        super().services_resolved()

        nuimo_service = next((service for service in self.services if service.uuid == self.NUIMO_SERVICE_UUID), None)
        if nuimo_service is None:
            if self.listener:
                # TODO: Use proper exception subclass
                self.listener.connect_failed(Exception("Nuimo GATT service missing"))
            return

        self._matrix_writer.led_matrix_characteristic = next((
            characteristic for characteristic in nuimo_service.characteristics
            if characteristic.uuid == self.LED_MATRIX_CHARACTERISTIC_UUID), None)
        # TODO: Fallback to legacy led matrix service
        #       This is needed for older Nuimo firmware were the LED characteristic was a separate service)

        notification_characteristic_uuids = [
            self.BUTTON_CHARACTERISTIC_UUID,
            self.TOUCH_CHARACTERISTIC_UUID,
            self.ROTATION_CHARACTERISTIC_UUID,
            self.FLY_CHARACTERISTIC_UUID
        ]

        for characteristic_uuid in notification_characteristic_uuids:
            characteristic = next((
                characteristic for characteristic in nuimo_service.characteristics
                if characteristic.uuid == characteristic_uuid), None)
            if characteristic is None:
                # TODO: Use proper exception subclass
                self.listener.connect_failed(Exception("Nuimo GATT characteristic " + characteristic_uuid + " missing"))
                return
            characteristic.enable_notifications()

        # TODO: Only fire connected event when we read the firmware version or battery value as in other SDKs
        if self.listener:
            self.listener.connect_succeeded()

    def display_matrix(self, matrix, interval=2.0, brightness=1.0, fading=False, ignore_duplicates=False):
        """
        Displays an LED matrix on Nuimo's LED matrix display.

        :param matrix: the matrix to display
        :param interval: interval in seconds until the matrix disappears again
        :param brightness: led brightness between 0..1
        :param fading: if True, the previous matrix fades into the new matrix
        :param ignore_duplicates: if True, the matrix is not sent again if already being displayed
        """
        self._matrix_writer.write(
            matrix=matrix,
            interval=interval,
            brightness=brightness,
            fading=fading,
            ignore_duplicates=ignore_duplicates
        )

    def characteristic_value_updated(self, characteristic, value):
        {
            self.BUTTON_CHARACTERISTIC_UUID:   self._notify_button_event,
            self.TOUCH_CHARACTERISTIC_UUID:    self._notify_touch_event,
            self.ROTATION_CHARACTERISTIC_UUID: self._notify_rotation_event,
            self.FLY_CHARACTERISTIC_UUID:      self._notify_fly_event
        }[characteristic.uuid](value)

    def characteristic_write_value_succeeded(self, characteristic):
        if characteristic.uuid == self.LED_MATRIX_CHARACTERISTIC_UUID:
            self._matrix_writer.write_succeeded()

    def characteristic_write_value_failed(self, characteristic, error):
        if characteristic.uuid == self.LED_MATRIX_CHARACTERISTIC_UUID:
            self._matrix_writer.write_failed(error)

    def _notify_button_event(self, value):
        self._notify_gesture_event(gesture=Gesture.BUTTON_RELEASE if value[0] == 0 else Gesture.BUTTON_PRESS)

    def _notify_touch_event(self, value):
        gesture = {
            0:  Gesture.SWIPE_LEFT,
            1:  Gesture.SWIPE_RIGHT,
            2:  Gesture.SWIPE_UP,
            3:  Gesture.SWIPE_DOWN,
            4:  Gesture.TOUCH_LEFT,
            5:  Gesture.TOUCH_RIGHT,
            6:  Gesture.TOUCH_TOP,
            7:  Gesture.TOUCH_BOTTOM,
            8:  Gesture.LONGTOUCH_LEFT,
            9:  Gesture.LONGTOUCH_RIGHT,
            10: Gesture.LONGTOUCH_TOP,
            11: Gesture.LONGTOUCH_BOTTOM
        }.get(value[0])
        if gesture is not None:
            self._notify_gesture_event(gesture=gesture)

    def _notify_rotation_event(self, value):
        rotation_value = value[0] + (value[1] << 8)
        if (value[1] >> 7) > 0:
            rotation_value -= 1 << 16
        self._notify_gesture_event(gesture=Gesture.ROTATION, value=rotation_value)

    def _notify_fly_event(self, value):
        if value[0] == 0:
            self._notify_gesture_event(gesture=Gesture.FLY_LEFT)
        elif value[0] == 1:
            self._notify_gesture_event(gesture=Gesture.FLY_RIGHT)
        elif value[0] == 4:
            self._notify_gesture_event(gesture=Gesture.FLY_UPDOWN, value=value[1])

    def _notify_gesture_event(self, gesture, value=None):
        if self.listener:
            self.listener.received_gesture_event(GestureEvent(gesture=gesture, value=value))


class _LedMatrixWriter():
    def __init__(self, controller):
        self.controller = controller
        self.led_matrix_characteristic = None

        self.last_written_matrix = None
        self.last_written_matrix_interval = 0
        self.last_written_matrix_date = datetime.utcfromtimestamp(0)
        self.matrix = None
        self.interval = 0
        self.brightness = 0
        self.fading = False
        self.is_waiting_for_response = False
        self.write_on_response = False

    def write(self, matrix, interval, brightness, fading, ignore_duplicates):
        if (ignore_duplicates and
            (self.last_written_matrix is not None) and
            (self.last_written_matrix == matrix) and
            ((self.last_written_matrix_interval <= 0) or
             (datetime.now() - self.last_written_matrix_date).total_seconds() < self.last_written_matrix_interval)):
            return

        self.matrix = matrix
        self.interval = interval
        self.brightness = brightness
        self.fading = fading

        if (self.is_waiting_for_response and
            (datetime.now() - self.last_written_matrix_date).total_seconds() < 1.0):
            self.write_on_response = True
        else:
            self.write_now()

    def write_now(self):
        if not self.controller.is_connected() or self.led_matrix_characteristic is None:
            return

        matrix_bytes = list(
            map(lambda leds: functools.reduce(
                lambda acc, led: acc + (1 << led if leds[led] else 0), range(0, len(leds)), 0),
                [self.matrix.leds[i:i + 8] for i in range(0, 81, 8)]))

        matrix_bytes += [
            max(0, min(255, int(self.brightness * 255.0))),
            max(0, min(255, int(self.interval * 10.0)))]

        if self.fading:
            matrix_bytes[10] ^= 1 << 4

        # TODO: Support write requests without response
        #       bluetoothd probably doesn't support selecting the request mode
        self.is_waiting_for_response = True
        self.led_matrix_characteristic.write_value(matrix_bytes)

        self.last_written_matrix = self.matrix
        self.last_written_matrix_date = datetime.now()
        self.last_written_matrix_interval = self.interval

    def write_succeeded(self):
        self.is_waiting_for_response = False
        if self.write_on_response:
            self.write_on_response = False
            self.write_now()

    def write_failed(self, error):
        self.is_waiting_for_response = False


class ControllerListener:
    """
    Base class of listeners for a ``NuimoController`` with empty handler implementations.
    """
    def received_gesture_event(self, event):
        pass

    def started_connecting(self):
        pass

    def connect_succeeded(self):
        pass

    def connect_failed(self, error):
        pass

    def started_disconnecting(self):
        pass

    def disconnect_succeeded(self):
        pass


class GestureEvent:
    """
    A gesture event as it can be received from a Nuimo controller.

    :ivar gesture: gesture that was performed
    :ivar value: value associated with the gesture, i.e. number of rotation steps
    """
    def __init__(self, gesture, value=None):
        self.gesture = gesture
        self.value = value

    def __repr__(self):
        return str(self.gesture) + (("," + str(self.value)) if self.value is not None else "")


class Gesture(Enum):
    """
    A gesture that can be performed by the user on a Nuimo controller.
    """
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


class LedMatrix:
    """
    Represents an LED matrix to be displayed on a Nuimo controller.

    :ivar leds: Boolean array with 81 values each representing the LEDs being on or off.
    """
    def __init__(self, string):
        """
        Initializes an LED matrix with a string where each character represents one LED.

        :param string: 81 character string: ' ' and '0' represent LED off, all other characters represent LED on.
        """
        string = '{:<81}'.format(string[:81])
        self.leds = [c not in [' ', '0'] for c in string]

    def __eq__(self, other):
        return (other is not None) and (self.leds == other.leds)

    def __ne__(self, other):
        return not (self == other)
