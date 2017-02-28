from threading import Thread
from time import sleep

from nuimo import Controller, ControllerManager, ControllerListener, LedMatrix


MAC_ADDRESS = "c4:d7:54:71:e2:ce"


class NuimoListener(ControllerListener):
    def __init__(self, controller):
        self.controller = controller

        self.stopping = False
        self.t = Thread(target=self.show_dots)

    def connect_succeeded(self):
        self.t.start()

    def show_dots(self):
        num_dots = 1

        while not self.stopping:
            sleep(0.5)

            s = "{:<81}".format("*" * num_dots)
            self.controller.display_matrix(LedMatrix(s), interval=3.0, brightness=1.0, fading=True)

            num_dots += 1
            if num_dots > 81:
                num_dots = 1

    def stop(self):
        self.controller.disconnect()
        self.stopping = True


controller = Controller(adapter_name="hci0", mac_address=MAC_ADDRESS)
listener = NuimoListener(controller)
controller.listener = listener
controller.connect()


manager = ControllerManager()

try:
    manager.run()
except KeyboardInterrupt:
    print("Stopping...")
    listener.stop()
    manager.stop()
