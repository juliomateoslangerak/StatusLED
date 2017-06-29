"""
In this module we create a state machine to follow the state of the executor and launch other tasks form the 
Raspberry. The current setup wil manage the status lights.
"""
from multiprocessing import Process, Queue
from transitions.extensions import HierarchicalMachine as Machine
from time import sleep
import json
import socket
import logging

from LEDs import StatusLED

## TODO: get status led and UDP config from file

UDP_IP_ADDRESS = "localhost"
UDP_PORT_NO = 6666
FPGA_UPDATE_RATE = .1  # At which rate is the FPGA sending update status signals


RING_START = (512 - 64)
RING_LEDS = (1, 6, 16, 24)
TOTAL_LEDS = sum(RING_LEDS)

CABINET_START = 0
CABINET_LEDS = 30

OPC_HOST = '127.0.0.1'
OPC_PORT = '7890'

STATES = ['default',
          'start',
          'configure',
          'idle',
          'error',
          {'name': 'action', 'children': ['default',
                                          'prepare',
                                          'snap',
                                          'experiment',
                                          'mosaic',
                                          ]},
          'shutdown',
          ]

TRANSITIONS = [
    ['on_default',           '*',            'default'],
    ['on_start',             'shutdown',     'start'],
    ['on_configure',         'start',        'configure'],
    ['on_idle',              '*',            'idle'],
    ['on_error',             '*',            'error'],
    ['on_action_prepare',    'idle',         'action_prepare'],
    ['on_action_snap',       'idle',         'action_snap'],
    ['on_action_experiment', 'idle',         'action_experiment'],
    ['on_action_mosaic',     'idle',         'action_mosaic'],
    ['on_shutdown',          '*',            'shutdown'],
]

MainFPGA_to_FSMachine_state = {
    '0': 'default',     # Default
    '1': 'start',       # Start
    '2': 'configure',   # Configuring
    '3': 'idle',        # Idle
    '4': 'error',       # Aborted
    '5': 'action',      # Running Action
    '6': 'shutdown',    # Shutdown
}

ActionFPGA_to_FSMachine_state = {
    '0': 'default',     # Default
    '1': 'experiment',  # Executing Experiment
    '2': 'prepare',     # Transferring Digitals
    '3': 'prepare',     # Transferring Analogues
    '4': 'prepare',     # Writing Indexes
    '5': 'prepare',     # Writing Digitals
    '6': 'prepare',     # Writing Analogue
    '7': 'snap',        # Taking Snap
    '8': 'prepare',     # Flushing FIFOs
    '9': 'prepare',     # Updating Repetitions
    '10': 'mosaic',     # Running Slow Mosaic
    '11': 'mosaic',     # Running Fast Mosaic
}


class FSMachine:
    """This is a class to hold a Finite State Machine.
    It is intended to handle the different states and control a response according to this state.
    The actions are running as separate processes and 
    there is a main loop getting status from the executor through a UDP socket and triggering the transitions"""
    # Define a State Machine
    def __init__(self, states, transitions, timerQueue, effectQueue, initialState='start'):
        self.machine = Machine(model=self,
                               states=states,
                               transitions=transitions,
                               initial=initialState,
                               auto_transitions=False)

        # Create queues to pass state and time point
        self.timerQueue = timerQueue
        self.effectQueue = effectQueue

        ## Create separate processes to run stuff and start them

        # A status LED processor
        self.statusLEDs = StatusLEDProcessor(effectQueue=self.effectQueue,
                                             timerQueue=self.timerQueue,
                                             totalLEDs=TOTAL_LEDS,
                                             ringStart=RING_START,
                                             ringLEDs=RING_LEDS,
                                             cabinetStart=CABINET_START,
                                             cabinetLEDs=CABINET_LEDS,
                                             host=OPC_HOST,
                                             port=OPC_PORT,
                                             )
        self.statusLEDs.start()

    # Configure the callbacks of the machine
    def on_enter_start(self):
        self.effectQueue.put(['on_enter_start', ()])

    def on_enter_configure(self):
        self.effectQueue.put(['on_enter_configure', ()])

    def on_enter_idle(self):
        self.effectQueue.put(['on_enter_idle', ()])

    def on_enter_error(self):
        self.effectQueue.put(['on_enter_error', ()])

    def on_enter_action_experiment(self):
        self.effectQueue.put(['on_enter_action_experiment', ()])

    def on_enter_action_prepare(self):
        self.effectQueue.put(['on_enter_action_prepare', ()])

    def on_enter_action_snap(self):
        self.effectQueue.put(['on_enter_action_snap', ()])

    def on_enter_action_mosaic(self):
        self.effectQueue.put(['on_enter_action_mosaic', ()])

    def on_enter_shutdown(self):
        self.effectQueue.put(['on_enter_shutdown', ()])

    def on_kill(self):
        self.effectQueue.put(['kill', ()])
        while not self.timerQueue.empty():  # Clean the timer queue
            self.timerQueue.get(block=False)


class FPGAStatus:
    def __init__(self, host, port):
        ## Create a dictionary to store the full FPGA state
        self.currentFPGAStatus = {}

        ## Create the queues to communicate with the FSM
        self.timerQueue = Queue()
        self.effectQueue = Queue()

        ## Create the FSM
        self.machine = FSMachine(states=STATES,
                                 transitions=TRANSITIONS,
                                 timerQueue=self.timerQueue,
                                 effectQueue=self.effectQueue,
                                 )

        ## create a socket to listen
        self.socket = self.createReceiveSocket(host, port)

        ## Create a handle to stop the thread
        self.shouldRun = True

    def createReceiveSocket(self, host, port):
        """
        Creates a UDP socket meant to receive status information
        form the RT-host
        returns the bound socket
        """
        try:
            # Create an AF_INET, Datagram socket (UDP)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error as e:
            print(f'Failed to create socket. Error message: {e}')
            return

        try:
            # Bind Socket to local host and port
            s.bind((host, port))
        except socket.error as e:
            print(f'Failed to bind address. Error message: {e}')
            return

        return s

    def get_status(self, key=None):
        """
        Method to call from outside to get the status
        """
        if key and self.currentFPGAStatus is not None:
            try:
                return self.currentFPGAStatus[key]
            except:
                print('Key does not exist')
        else:
            return self.currentFPGAStatus

    def poll_fpga_status(self):
        """
        This method polls to the UDP socket and gets the status information
        of the RT-host and FPGA.
        Returns a json object that we can use to update the status dictionary
        """
        try:
            # Receive Datagram
            datagramLength = int(self.socket.recvfrom(4)[0])
            datagram = self.socket.recvfrom(datagramLength)[0]
        except socket.error as e:
            print(f'Failed to get Datagram. Error message: {e}')
            return None
        return json.loads(datagram.decode())

    def trigger_event(self, newStatus):
        """
        FInd 'interesting' status or state changes in the FPGA and trigger events or
        the corresponding machine transitions.
        return the newStatus but with the status reset so not to queue multiple times
        """
        # Get a state change
        if self.currentFPGAStatus['FPGA Main State'] != newStatus['FPGA Main State']:
            new_state = MainFPGA_to_FSMachine_state[newStatus['FPGA Main State']]
            # TODO: We have to generalize this into the Hierarchical SM. I do not know how to do this best
            if new_state == 'action':
                new_state = new_state + '_' + ActionFPGA_to_FSMachine_state[newStatus['Action State']]
                print(new_state)

            try:
                getattr(self.machine, 'on_' + new_state)()
            except:
                print('Could not get that new state')

        # get a timer update and post it into the timer_queue
        if self.currentFPGAStatus['Timer'] != newStatus['Timer']:
            self.timerQueue.put(newStatus['Timer'])

        print(newStatus)
        return newStatus

    def run(self):

        self.currentFPGAStatus = self.poll_fpga_status()

        while self.shouldRun:
            newFPGAStatus = self.poll_fpga_status()
            if newFPGAStatus is not None and newFPGAStatus != self.currentFPGAStatus:
                # Trigger a transition and update current state
                self.currentFPGAStatus = self.trigger_event(newStatus=newFPGAStatus)

            ## wait for a period of half the broadcasting rate of the FPGA
            sleep(FPGA_UPDATE_RATE / 2)


class StatusLEDProcessor(Process):
    """This class runs the status LEDs. It provides 
    the link between the state and a particular effect 
    with its parameters so we can sync it with the state machine"""

    def __init__(self,
                 effectQueue,
                 timerQueue,
                 totalLEDs,
                 ringStart,
                 ringLEDs,
                 cabinetStart,
                 cabinetLEDs,
                 host,
                 port):
        Process.__init__(self)
        self.effectQueue = effectQueue
        self.timerQueue = timerQueue

        self.LEDs = StatusLED(effectQueue=self.effectQueue,
                              timerQueue=self.timerQueue,
                              totalLEDs=totalLEDs,
                              ringStart=ringStart,
                              ringsLEDs=ringLEDs,
                              cabinetStart=cabinetStart,
                              cabinetLEDs=cabinetLEDs,
                              host=host,
                              port=port,)

    def run(self):
        self.initializeLEDs()
        while True:
            f, args = self.effectQueue.get()
            if f != 'kill':
                getattr(self, f)(*args)
            else:
                return

    def initializeLEDs(self):
        self.LEDs.setLEDs(intensity=None)

    def on_enter_start(self):
        pass

    def on_enter_configure(self):
        pass

    def on_enter_idle(self):
        """
        Function to call on idle

        :return: None
        """
        self.LEDs.sineBeat(color=[50, 50, 50],
                           glow=[20, 20, 20],
                           frequency=1.0)

    def on_enter_error(self):
        """
        Method to call on error. It blinks on the defined color, duty and frequency

        :return: None
        """
        self.LEDs.squareBeat(color=[150, 0, 0],
                             glow=[50, 0, 0],
                             frequency=2,
                             duty=.3)

    def on_enter_action_experiment(self):
        """
        Function to call on experiment start

        :return: None
        """
        self.LEDs.chaseLEDsTimer(chaseColor=[128, 0, 0],
                                 timerColor=[0, 128, 0],
                                 decay=8.0,
                                 chaseRing=-1,
                                 timerRing=-2,
                                 speed=2,
                                 frequency=1
                                 )

        while not self.timerQueue.empty():  # Clean the timer queue in case things go to quick or we abort
            self.timerQueue.get(block=False)

    def on_enter_action_prepare(self):
        pass

    def on_enter_action_snap(self):
        """
        Function to call on an image snap

        :return: None
        """
        self.LEDs.multiplePulse(pattern=[[[0, 0, 255], 0.005]])

    def on_enter_action_mosaic(self):
        pass

    def on_enter_shutdown(self):
        pass

    def on_reset(self):
        pass

    def on_terminate(self):
        self.terminate()

if __name__ == '__main__':

    Status_controller = FPGAStatus(host=UDP_IP_ADDRESS, port=UDP_PORT_NO)
    print('Status Controller created')

    print('Status Controller running')
    Status_controller.run()

