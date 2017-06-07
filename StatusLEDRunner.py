'''
In this module we create a state machine to follow the state of the executor and launch other tasks form the 
Raspberry. The current setup wil manage the status lights.
'''
from multiprocessing import Process, Queue
from transitions import Machine
import Pyro4

from LEDs import StatusLED

## TODO: get status led config from file

ringStart = (512 - 64)
ringsLEDs = (1, 6, 12, 24)
totalLEDs = sum(ringsLEDs)

cabinetStart = 0
cabinetLEDs = 30

states = ['idle', 'error', 'snapping', 'acquiring', 'booting', 'shutdown']

transitions = [
    {'trigger': 'on_experiment', 'source': 'idle', 'dest': 'acquiring'},
    {'trigger': 'on_error', 'source': ['idle', 'snapping', 'acquiring'], 'dest': 'error'},
    {'trigger': 'on_snap', 'source': 'idle', 'dest': 'snapping'},
    {'trigger': 'on_boot', 'source': 'shutdown', 'dest': 'booting'}
    {'trigger': 'on_reset', 'source': ['idle', 'error', 'snapping', 'acquiting', 'booting', 'shutdown'],
     'dest': 'shutdown'}
    {'trigger': 'on_configure', 'source': 'booting', 'dest': 'idle'}
]

# Define a State Machine
self.machine = Machine(model=self,
                       states=states,
                       transitions=transitions,
                       initial='shutdown',
                       auto_transitions=False)


class StatusLEDProcessor(Process):
    """This class runs the status LEDs as a different process
    so we can sync it with the state machine"""

    stateToEffect = {
        0: on_reset,
        1: on_boot,
        2: on_configure,
        3: on_error,
        4: on_snap,
        5: on_idle,
        6: on_experiment

    }

    def __init__(self,
                 totalLEDs = totalLEDs,
                 ringStart = ringStart,
                 cabinetStart = cabinetStart,
                 cabinetLEDs = cabinetLEDs
                 ):
        super(Processor, self).__init__()
        self.stateQueue = Queue()
        self.timerQueue = Queue()

        self.LEDs = StatusLED(totalLEDs=totalLEDs,
                              ringStart=ringStart,
                              cabinetStart=cabinetStart,
                              cabinetLEDs=cabinetLEDs)

    def run(self):
        newState = self.stateQueue.get()
        if newState == 0:
            self.join()
        else:
            self.stateToEffect[newState]()
            self.run()

    def on_idle(self):
        """
        Function to call on idle

        :return: None
        """
        self.LEDs.sineBeat(color=[50, 50, 50],
                           stateQueue=self.stateQueue,
                           frequency=2.0)

    def on_snap(self):
        """
        Function to call on an image snap

        :return: None
        """
        self.LEDs.singlePulse(pulseColor=[0,0,128], t=.2)

    def on_error(self):
        """
        Method to call on error. It blinks on the defined color and frequency

        :return: None
        """
        self.LEDs.squareBeat(color=[200, 0, 0], stateQueue=self.stateQueue, frequency=.5, duty=.3)

    def on_experiment(self):
        """
        Function to call on experiment start

        :return: None
        """
        self.LEDs.chaseLEDsTimer(chaseColor=[128, 0, 0],
                                 timerColor=[0, 128, 0],
                                 stateQueue=self.stateQueue,
                                 timerQueue=self.timerQueue,
                                 decay=1.0,
                                 chaseRing=3,
                                 timerRing=2,
                                 frequency=.6
                                 )

    def on_boot(self):
        pass

    def on_configure(self):
        pass

    def on_reset(self):
        pass

