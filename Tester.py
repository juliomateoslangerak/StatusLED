"""This module will emulate the UDP broadcasting of the FPGA
for testing purposes"""

import socket
from time import sleep, time
import json

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


class Tester:
    def __init__(self, ipAdress, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1)
        self.addr = (ipAdress, port)
        self.msg = {'FPGA Main State': '0',
                    'Action State': '0',
                    'Timer': '0',
                    'Other Status Elements': 'WhatEver'}
        self.send_msg()

    def send_msg(self):
        data = json.dumps(self.msg)
        self.sock.sendto(data.encode(), self.addr)

    def run_experiment(self, duration):

        self.msg['FPGA Main State'] = '5'
        self.msg['Action State'] = '1'

        start_time = time()
        end_time = start_time + duration

        while time() <= end_time:
            currentTime = str(round((time()-start_time / duration), 2))
            self.msg['Timer'] = currentTime
            self.send_msg()
            sleep(.1)

        self.msg['FPGA Main State'] = '3'
        self.msg['Action State'] = '0'

        self.send_msg()



    def run_snap(self):
        self.msg['FPGA Main State'] = '5'
        self.msg['Action State'] = '7'

        self.send_msg()

        self.msg['FPGA Main State'] = '3'
        self.msg['Action State'] = '0'

        self.send_msg()

    def run_start(self):
        self.msg['FPGA Main State'] = '1'
        self.msg['Action State'] = '0'

        self.send_msg()
        sleep(2)

        self.msg['FPGA Main State'] = '2'
        self.msg['Action State'] = '0'

        self.send_msg()
        sleep(3)

        self.msg['FPGA Main State'] = '3'
        self.msg['Action State'] = '0'

        self.send_msg()
        sleep(5)

    def run_abort(self):
        self.msg['FPGA Main State'] = '4'
        self.msg['Action State'] = '0'

        self.send_msg()

    def run_idle(self):
        self.msg['FPGA Main State'] = '3'
        self.msg['Action State'] = '0'

        self.send_msg()


if __name__ == '__main__':

    t = Tester(ipAdress='127.0.0.1', port=6666)
    print('Tester created')

    t.run_start()
    print('Starting...')

    sleep(4)

    t.run_experiment(10)

    t.run_idle()

    sleep(5)

    t.run_snap()

    sleep(3)

