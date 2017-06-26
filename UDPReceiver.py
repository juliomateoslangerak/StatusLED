import socket
import json
from time import sleep

class FPGAStatus:
    def __init__(self, host, port):
        ## Create a dictionary to store the full FPGA state
        self.currentFPGAStatus = {}

        ## Create the queues to communicate with the FSM
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
        except socket.error as msg:
            print('Failed to create socket. Error code: {}. Error message: {}'.format(msg[0], msg[1]))
            return

        try:
            # Bind Socket to local host and port
            s.bind((host, port))
        except socket.error as msg:
            print('Failed to bind address. Error code: {}. Error message: {}'.format(msg[0], msg[1]))
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
        except socket.error as msg:
            print('Failed to get Datagram. Error code: {}. Error message: {}'.format(msg[0], msg[1]))
            return None
        return json.loads(datagram.decode())

    def trigger_event(self, newStatus):
        """
        FInd 'interesting' status or state changes in the FPGA and trigger events or
        the corresponding machine transitions.
        return the newStatus but with the status reset so not to queue multiple times
        """
        # Get a state change
        # if self.currentFPGAStatus['FPGA Main State'] != newStatus['FPGA Main State']:
        #     new_state = MainFPGA_to_FSMachine_state[newStatus['FPGA Main State']]
        #     # TODO: We have to generalize this into the Hierarchical SM. I do not know how to do this best
        #     if new_state == '5':
        #         new_state = new_state + '_' + ActionFPGA_to_FSMachine_state[newStatus['Action State']]
        #
        #     try:
        #         getattr(self.machine, new_state)()
        #     except:
        #         print('Could not get that new state')

        # # get a timer update and post it into the timer_queue
        # if self.currentFPGAStatus['Timer'] != newStatus['Timer']:
        #     self.timerQueue.put(newStatus['Timer'])

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
            # sleep(0.05)
