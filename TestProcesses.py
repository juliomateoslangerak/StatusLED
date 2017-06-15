from multiprocessing import Process, Queue
from time import sleep


class LED_processor(Process):
    def __init__(self, effectQueue, outQueue):
        Process.__init__(self)
        self.effectQueue = effectQueue
        self.outQueue = outQueue

    def effect(self, x):
        calc = x * x
        self.outQueue.put(calc)

    def run(self):
        while True:
            f, x = self.effectQueue.get()
            if f != 'kill':
                getattr(self, f)(x)
            else:
                return


class Machine:
    def __init__(self):
        print('Hi')
        self.effectQueue = Queue()
        self.outQueue = Queue()
        self.LED_processor = LED_processor(self.effectQueue, self.outQueue)
        print('LED_processor created')
        self.LED_processor.start()

    def run_effect(self, x):
        self.effectQueue.put(['effect', x])
        out = self.outQueue.get()
        print(out)

    def kill(self):
        self.effectQueue.put(['kill',0])



if __name__ == '__main__':
    m = Machine()
    sleep(2)
    m.run_effect(3)
    sleep(3)
    m.kill()
    m.LED_processor.join()