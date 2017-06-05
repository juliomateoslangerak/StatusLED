# from threading import Thread, Lock
from multiprocessing import Value, Process, Queue
from time import sleep

StateQueue = Queue()

class StatePrinter():
    def __init__(self):
        self.curState = 0
        self.printState()

    def printState(self):
        print('started')
        while not self.curState == 5:
            sleep(.5)
            if StateQueue.empty():
                pass
            else:
                self.curState = StateQueue.get()
            print('running: ' + str(self.curState))

def changeState(newState):
    StateQueue.put(newState)
    print('Changed to: ' + str(newState))

if __name__ == '__main__':
    s = Process(target=StatePrinter)
    s.start()
    print('Process Started')
    sleep(3)
    print('gonna change to 5')
    changeState(5)
    sleep(3)
    s.join()
