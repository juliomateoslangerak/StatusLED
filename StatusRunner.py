'''
In this module we create a state machine to follow the state of the executor and launch other tasks form the 
Raspberry. The current setup wil manage the status lights.
'''
from multiprocessing import Process, Queue, Lock
from transitions import Machine
import Pyro4

from LEDs import StatusLED
import socket

## TODO: get status led and UDP config from file

UDP_IP_ADDRESS = "10.6.19.12"
UDP_PORT_NO = 6666
FPGA_UPDATE_RATE = .1 # At which rate is the FPGA sending update status signals


RING_START = (512 - 64)
RING_LEDS = (1, 6, 12, 24)
TOTAL_LEDS = sum(RING_LEDS)

CABINET_START = 0
CABINET_LEDS = 30

OPC_HOST = 'localhost'
OPC_PORT = '7890'

states = ['default',
          'start',
          'configure',
          'idle',
          'error',
          {'name': 'action', 'children':['default',
                                         'prepare',
                                         'snap',
                                         'experiment',
                                         'mosaic',
                                         ]},
          'shutdown',
          ]

transitions = [
    ['on_default',       '*',            'default'],
    ['on_start',         'shutdown',     'start'],
    ['on_configure',     'start',        'configure'],
    ['on_idle',          '*',            'idle'],
    ['on_error',         '*',            'error'],
    ['on_prepare',       'idle',         'action_prepare'],
    ['on_snap',          'idle',         'action_snap'],
    ['on_experiment',    'idle',         'action_experiment'],
    ['on_mosaic',        'idle',         'action_mosaic'],
    ['on_shutdown',      '*',            'shutdown'],
]

MainFPGA_to_FSMachine_state = {
    '0':'default', # Default
    '1':'start', # Start
    '2':'configure', # Configuring
    '3':'idle', # Idle
    '4':'error', # Aborted
    '5':'action', # Running Action
    '6':'shutdown', # Shutdown
}

SecondaryFPGA_to_FSMachine_state = {
    '0':'default', # Default
    '1':'experiment', # Executing Experiment
    '2':'prepare', # Transferring Digitals
    '3':'prepare', # Transferring Analogues
    '4':'prepare', # Writing Indexes
    '5':'prepare', # Writing Digitals
    '6':'prepare', # Writing Analogue
    '7':'snap', # Taking Snap
    '8':'prepare', # Flushing FIFOs
    '9':'prepare', # Updating Repetitions
    '10':'mosaic', # Running Slow Mosaic
    '11':'mosaic', # Running Fast Mosaic
}

class FSMachine():
    """This is a class to hold a Finite State Machine.
    It is intended to handle the different states and control a response according to this state.
    The actions are running as separate processes and 
    there is a main loop getting status from the executor through a UDP socket and triggering the transitions"""
    # Define a State Machine
    def __init__(self):
        self.machine = Machine(model=self,
                               states=states,
                               transitions=transitions,
                               initial='start',
                               auto_transitions=False)

        # Create queues to pass state and timepoint
        self.stateQueue = Queue()
        self.timerQueue = Queue()
        self.effectQueue = Queue()

        # Create separate processes to run stuff

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

        # Create a FPGAStatus instance
        self.FPGAStatus = FPGAStatus(host=UDP_IP_ADDRESS,
                                     port=UDP_PORT_NO,
                                     stateQueue = self.stateQueue,
                                     timerQueue = self.timerQueue
                                     )

        # Create a statusLED processor
        self.statusLEDs = StatusLEDProcessor(stateQueue=self.stateQueue,
                                             timerQueue=self.timerQueue)

        # Start all the processes
        self.FPGAStatus.start()
        self.run()

    # Configure the callbacks of the machine
    def on_enter_idle(self):
        self.effectQueue.put(['on_enter_idle', None])

    def on_enter_error(self):
        self.effectQueue.put(['on_enter_error', None])

    def on_enter_snap(self):
        self.effectQueue.put(['on_enter_snap', None])

    def on_enter_experiment(self):
        self.effectQueue.put(['on_enter_experiment', None])

    def on_enter_start(self):
        self.effectQueue.put(['on_enter_start', None])

    def on_enter_shutdown(self):
        self.effectQueue.put(['on_enter_shutdown', None])

    def run(self):
        pass


class FPGAStatus(Process):
    def __init__(self, host, port, stateQueue, timerQueue):
        Process.__init__(self)
        ## Create a dictionary to store the full FPGA state
        self.currentFPGAStatus = {}

        ## Create the queues to communicate with the FSM
        self.stateQueue = stateQueue
        self.timerQueue - timerQueue

        ## create a socket
        self.socket = self.createReceiveSocket(host, port)

        ## Create a handle to stop the thread
        self.shouldRun = True

    def createReceiveSocket(self, host, port):
        '''
        Creates a UDP socket meant to receive status information
        form the RT-host
        returns the bound socket
        '''
        try:
            # Create an AF_INET, Datagram socket (UDP)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error, msg:
            print 'Failed to create socket. Error code: ' + str(msg[0]) + ' , Error message : ' + msg[1]

        try:
            # Bind Socket to local host and port
            s.bind((host , port))
        except socket.error, msg:
            print 'Failed to bind address. Error code:' + str(msg[0]) + ' , Error message : ' + msg[1]

        return s

    def getStatus(self, key = None):
        '''
        Method to call from outside to get the status
        '''
        if key and self.currentFPGAStatus is not None:
            try:
                return self.currentFPGAStatus[key]
            except:
                print('Key does not exist')
        else:
            return self.currentFPGAStatus

    def getFPGAStatus(self):
        '''
        This method polls to a UDP socket and get the status information
        of the RT-host and FPGA.
        It will update the FPGAStatus dictionary.
        '''
        try:
            # Receive Datagram
            datagramLength = int(self.socket.recvfrom(4)[0])
            datagram = self.socket.recvfrom(datagramLength)[0]
        except:
            print('No datagram')
            return None
        # parse json datagram
        return json.loads(datagram)

    def queueStateChanges(self, newStatus):
        '''
        FInd interesting status or status changes in the FPGA and queue them
        return the newStatus but with the status reset so not to queue multiple times
        '''
        if newStatus['FPGA Main State'] == 'FPGA done':
            events.publish('DSP done')
            newStatus['FPGA Main State'] = ''

        return newStatus

    def run(self):

        self.currentFPGAStatus = self.getFPGAStatus()

        while self.shouldRun:
            newFPGAStatus = self.getFPGAStatus()
            with self.FPGAStatusLock:
                if newFPGAStatus is not None and newFPGAStatus != self.currentFPGAStatus:
                    # Queue any state change and update
                    self.currentFPGAStatus = self.queueStateChanges(newStatus = newFPGAStatus)

            ## wait for a period of half the broadcasting rate of the FPGA
            time.sleep(FPGA_UPDATE_RATE / 2)


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

    def run(self)
        while True:
            f, x = self.effectQueue.get()
            if f != 'kill':
                getattr(self, f)(x)
            else:
                return

    def on_enter_idle(self):
        """
        Function to call on idle

        :return: None
        """
        self.LEDs.sineBeat(color=[50, 50, 50],
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
        self.LEDs.squareBeat(color=[200, 0, 0], frequency=.5, duty=.3)

    def on_experiment(self):
        """
        Function to call on experiment start

        :return: None
        """
        self.LEDs.chaseLEDsTimer(chaseColor=[128, 0, 0],
                                 timerColor=[0, 128, 0],
                                 decay=1.0,
                                 chaseRing=3,
                                 timerRing=2,
                                 frequency=.6
                                 )

        while is not self.timerQueue.empty(): # Clean the timer queue in case things go to quick or we abort
            self.timerQueue.get(block=False)

    def on_start(self):
        pass

    def on_configure(self):
        pass

    def on_reset(self):
        pass

    def on_terminate(self):
        self.terminate()
