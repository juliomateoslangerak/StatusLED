#!/usr/bin/env python

# Test DeepSIM status lights.

from multiprocessing import Process, Value
import opc
import time
import copy
import waves
from multiprocessing import Queue

class FrameIntensity(waves.Signal):
    def __init__(self, intensity):
        self._intensity = intensity

    def update(self, newIntensity):
        self._intensity = newIntensity

    def __call__(self):
        return self._intensity


class FramePhase(waves.Signal):
    def __init__(self, piBased=False, phase=0.0):
        self.piBased = piBased
        self._current_phase = phase

    def update(self, LED, nrOfLEDs):
        if self.piBased:
            self._current_phase = (2 * PI * LED) / nrOfLEDs
        else:
            self._current_phase = LED / nrOfLEDs

    def __call__(self):
        return self._current_phase


class FrameFrequency(waves.Signal):
    def __init__(self, frequency=1.0):
        self._current_frequency = frequency

    def update(self, frequency):
        self._current_frequency = frequency

    def __call__(self):
        return self._current_frequency


class FrameDecay(waves.Signal):
    def __init__(self, decay=1.0):
        self._current_decay = decay

    def update(self, decay):
        self._current_decay = decay

    def __call__(self):
        return self._current_decay


class FrameDuty(waves.Signal):
    def __init__(self, duty=0.5):
        self._current_duty = duty

    def update(self, duty):
        self._current_duty = duty

    def __call__(self):
        return self._current_duty


class FrameClock(waves.Signal):
    def __init__(self):
        self._current_s = time.time()

    def update(self):
        self._current_s = time.time()

    def __call__(self):
        return self._current_s


class FrameTimer(waves.Signal):
    """A class to manage a timer effect"""
    def __init___(self, fraction=0.0):
        self._current_t = fraction

    def update(self, newFraction):
        self._current_t = newFraction

    def __call__(self):
        return self._current_t


class StatusLED:
    def __init__(self,
                 effectQueue,
                 timerQueue,
                 totalLEDs,
                 ringStart,
                 ringsLEDs,
                 cabinetStart,
                 cabinetLEDs,
                 glow=(0, 0, 0),  # a tupple containing the min background color
                 power=128,  # the max poser we want to drive the leds. int from 0 to 255
                 host = 'localhost',
                 port = '7890',
                 ):
        """
        :int totalLEDs: total nr of LEDs
        :tuple ringsLEDs: tuple containing the nr of leds of every concentric ring from center to edge
        """
        self.effectQueue = effectQueue
        self.timerQueue = timerQueue
        self.client = client
        self.glow = glow
        self.power = power
        self.ringsLEDs = ringsLEDs
        self.totalLEDs = totalLEDs
        self.ringStart = ringStart
        self.cabinetStart = cabinetStart
        self.cabinetLEDs = cabinetLEDs
        self.intensity = [(0, 0, 0)] * 512  # make an intensity array for the whole fadecandy addressable pixels.
        self.progress = 0
        self.savedProgress = (0, 0, 0)
        self.client = opc.Client(host + ':' + port),

        # Some frames
        self.clock = FrameClock()
        self.frequency = FrameFrequency()
        self.decay = FrameDecay()
        self.duty = FrameDuty()
        self.timer = FrameTimer()
        self.piBasedPhase = FramePhase(piBased=True)
        self.noPiBasedPhase = FramePhase(piBased=False)
        self.redIntensity = FrameIntensity(self.power)
        self.greenIntensity = FrameIntensity(self.power)
        self.blueIntensity = FrameIntensity(self.power)

        # Some basic waves
        self.red_decayWave = waves.TransformedSignal(waves.DecayWave(time=self.clock,
                                                                     frequency=self.frequency,
                                                                     phase=self.noPiBasedPhase,
                                                                     decay=self.decay,
                                                                     ),
                                                     y0=self.glow,
                                                     y1=self.redIntensity,
                                                     discrete=True)

        self.green_decayWave = waves.TransformedSignal(waves.DecayWave(time=self.clock,
                                                                       frequency=self.frequency,
                                                                       phase=self.noPiBasedPhase,
                                                                       decay=self.decay
                                                                       ),
                                                       y0=self.glow,
                                                       y1=self.greenIntensity,
                                                       discrete=True)

        self.blue_decayWave = waves.TransformedSignal(waves.DecayWave(time=self.clock,
                                                                      frequency=self.frequency,
                                                                      phase=self.noPiBasedPhase,
                                                                      decay=self.decay
                                                                      ),
                                                      y0=self.glow,
                                                      y1=self.blueIntensity,
                                                      discrete=True)

        self.red_sineWave = waves.TransformedSignal(waves.SineWave(time=self.clock,
                                                                   frequency=self.frequency,
                                                                   phase=self.piBasedPhase,
                                                                   ),
                                                    y0=self.glow,
                                                    y1=self.redIntensity,
                                                    discrete=True)

        self.green_sineWave = waves.TransformedSignal(waves.SineWave(time=self.clock,
                                                                     frequency=self.frequency,
                                                                     phase=self.piBasedPhase,
                                                                     ),
                                                      y0=self.glow,
                                                      y1=self.greenIntensity,
                                                      discrete=True)

        self.blue_sineWave = waves.TransformedSignal(waves.SineWave(time=self.clock,
                                                                    frequency=self.frequency,
                                                                    phase=self.piBasedPhase,
                                                                    ),
                                                     y0=self.glow,
                                                     y1=self.blueIntensity,
                                                     discrete=True)

        self.red_squareWave = waves.TransformedSignal(waves.SquareWave(time=self.clock,
                                                                       frequency=self.frequency,
                                                                       phase=self.piBasedPhase,
                                                                       duty=self.duty
                                                                       ),
                                                      y0=self.glow,
                                                      y1=self.redIntensity,
                                                      discrete=True)

        self.green_squareWave = waves.TransformedSignal(waves.SquareWave(time=self.clock,
                                                                         frequency=self.frequency,
                                                                         phase=self.piBasedPhase,
                                                                         duty=self.duty
                                                                         ),
                                                        y0=self.glow,
                                                        y1=self.greenIntensity,
                                                        discrete=True)

        self.blue_squareWave = waves.TransformedSignal(waves.SquareWave(time=self.clock,
                                                                        frequency=self.frequency,
                                                                        phase=self.piBasedPhase,
                                                                        duty=self.duty
                                                                        ),
                                                       y0=self.glow,
                                                       y1=self.blueIntensity,
                                                       discrete=True)

        self.red_timerWave = waves.TransformedSignal(waves.SquareWave(time=0,
                                                                      frequency=1,
                                                                      phase=self.timer,
                                                                      duty=self.duty
                                                                      ),
                                                     y0=self.glow,
                                                     y1=self.redIntensity,
                                                     discrete=True)

        self.green_timerWave = waves.TransformedSignal(waves.SquareWave(time=0,
                                                                        frequency=1,
                                                                        phase=self.timer,
                                                                        duty=self.duty
                                                                        ),
                                                       y0=self.glow,
                                                       y1=self.greenIntensity,
                                                       discrete=True)

        self.blue_timerWave = waves.TransformedSignal(waves.SquareWave(time=0,
                                                                       frequency=1,
                                                                       phase=self.timer,
                                                                       duty=self.duty
                                                                       ),
                                                      y0=self.glow,
                                                      y1=self.blueIntensity,
                                                      discrete=True)

    def setWhite(self):
        for i in range(self.totalLEDs):
            self.intensity[self.ringStart + i] = (self.power, self.power, self.power)
        self.setLEDs(None)

    def setOff(self):
        for i in range(self.totalLEDs):
            self.intensity[self.ringStart + i] = (0, 0, 0)
        self.setLEDs(None)

    def multiplePulse(self, pattern=None, t=0.2, ring=-1):
        """
        Function to call on an image snap

        :param pattern: a list of lists of two elements from which the first one is
        a list containing the color to pulse and the second is the pulse duration
        :return: None
        """
        if pattern is None:
            pattern = [[[self.redIntensity(),
                         self.greenIntensity(),
                         self.blueIntensity()],
                        t]]
        pulseColor = copy.copy(self.intensity)
        for p in pattern:
            for i in range(self.ringsLEDs[ring]):
                pulseColor[self.ringStart + i] = p[0]
            self.singlePulse(pulseColor=pulseColor, p[1])

    def singlePulse(self, pulseColor, t=0.2):
        self.setLEDs(None)
        self.setLEDs(pulseColor)
        time.sleep(float(t))
        self.setLEDs(pulseColor)
        self.setLEDs(None)

    def chaseLEDs(self, color, decay=1.0, ring=-1, frequency=1.0):
        """
        Creates a LED chasing effect
        :param color: tupple with the color to display
        :param state: which state is holding this effect
        :param decay: the decay factor
        :param ring: the ring to chase. Defaults to the outer ring
        :param frequency: how many turns per second. Defaults to 1
        :return: None
        """
        self.redIntensity.update(color[0])
        self.greenIntensity.update(color[1])
        self.blueIntensity.update(color[2])

        self.frequency.update(frequency)
        self.decay.update(decay)

        waveIntensity = copy.copy(self.intensity)

        while self.effectQueue.empty():
            self.clock.update()
            for led in range(self.ringsLEDs[ring]):
                self.noPiBasedPhase.update(led, self.ringsLEDs[ring])
                waveIntensity[self.ringStart + led] = (self.red_decayWave(),
                                                       self.green_decayWave(),
                                                       self.blue_decayWave())
            self.setLEDs(waveIntensity)
            # time.sleep(0.1)

        self.setLEDs(None)

    def chaseLEDsTimer(self, chaseColor, timerColor, decay=1.0, chaseRing=3, timerRing=2, frequency=1.0):
        """
        Creates a LED chasing effect
        :param color: tupple with the color to display
        :param state: which state is holding this effect
        :param decay: the decay factor
        :param ring: the ring to chase. Defaults to the outer ring
        :param frequency: how many turns per second. Defaults to 1
        :return: None
        """
        self.redIntensity.update(chaseColor[0])
        self.greenIntensity.update(chaseColor[1])
        self.blueIntensity.update(chaseColor[2])

        redTimerIntensity = FrameIntensity(timerColor[0])
        greenTimerIntensity = FrameIntensity(timerColor[1])
        blueTimerIntensity = FrameIntensity(timerColor[2])

        self.frequency.update(frequency)
        self.decay.update(decay)
        self.timer.update(0.0)
        self.duty.update(1 / self.ringsLEDs[timerRing])

        waveIntensity = copy.copy(self.intensity)

        while self.effectQueue.empty():
            self.clock.update()
            self.timer.update(self.timerQueue.get(block=False))
            for led in range(self.ringsLEDs[chaseRing]):
                self.noPiBasedPhase.update(led, self.ringsLEDs[chaseRing])
                waveIntensity[self.ringStart + led] = (self.red_decayWave(),
                                                       self.green_decayWave(),
                                                       self.blue_decayWave())
            for led in range(self.ringsLEDs[timerRing]):
                waveIntensity[self.ringStart + led] = (self.red_timerWave(),
                                                       self.green_timerWave(),
                                                       self.blue_timerWave())
            self.setLEDs(waveIntensity)
            # time.sleep(0.1)

        while is not self.timerQueue.empty():
            self.timerQueue.get()

        self.setLEDs(None)

    def sineBeat(self, color, frequency=1.0):
        """
        Creates a sinusoidal 'heart beat' of all leds
        :param color: tupple with the color to display
        :param state: which state is holding this effect
        :param frequency: how many turns per second. Defaults to 1
        :return: None
        """
        self.redIntensity.update(color[0])
        self.greenIntensity.update(color[1])
        self.blueIntensity.update(color[2])

        self.frequency.update(frequency)
        self.piBasedPhase.update(0, 0)

        waveIntensity = copy.copy(self.intensity)

        while self.effectQueue.empty():
            self.clock.update()
            for led in range(self.totalLEDs):
                waveIntensity[self.ringStart + led] = (self.red_sineWave(),
                                                       self.green_sineWave(),
                                                       self.blue_sineWave())
            self.setLEDs(waveIntensity)
            time.sleep(0.1)

        self.setLEDs(None)

    def squareBeat(self, color, frequency=1.0, duty=.5):
        """
        Creates a square 'heart beat' of all leds.
        :param color: tupple with the color to display
        :param state: which state is holding this effect
        :param frequency: how many turns per second. Defaults to 1
        :return: None
        """
        self.redIntensity.update(color[0])
        self.greenIntensity.update(color[1])
        self.blueIntensity.update(color[2])

        self.frequency.update(frequency)
        self.duty.update(duty)
        self.piBasedPhase.update(0, 0)

        waveIntensity = copy.copy(self.intensity)

        while self.effectQueue.empty():
            self.clock.update()
            for led in range(self.totalLEDs):
                waveIntensity[self.ringStart + led] = (self.red_squareWave(),
                                                       self.green_squareWave(),
                                                       self.blue_squareWave())
            self.setLEDs(waveIntensity)
            time.sleep(0.1)

        self.setLEDs(None)

    def setLEDs(self, intensity):
        if intensity is None:
            self.client.put_pixels(self.intensity)
            self.client.put_pixels(self.intensity)
        else:
            self.client.put_pixels(intensity)
            self.client.put_pixels(intensity)

    def setRing(self, ring, col):
        for i in range(self.ringsLEDs[ring]):
            self.intensity[self.ringStart + self.ringsLEDs[ring] + i] = col
        self.setLEDs(None)

    def setInner(self, col):
        self.setRing(ring=0, col=col)

    def setOuter(self, col):
        self.setRing(ring=-1, col=col)

    def incrementProgress(self, col=(0, 100, 0)):
        self.intensity[self.ringStart + self.progress] = self.savedProgress
        self.progress = self.progress + 1
        if self.progress > (self.ringsLEDs[-1] - 1):
            self.progress = 0
        self.savedProgress = copy.copy(self.intensity[self.ringStart + self.progress])
        self.intensity[self.ringStart + self.progress] = col
        self.setLEDs(None)

    def stopProgress(self):
        self.intensity[self.ringStart + self.progress] = self.savedProgress
        self.setLEDs(None)

    def cabinetOn(self):
        for i in range(self.cabinetLEDs):
            self.intensity[self.cabinetStart + i] = (255, 255, 255)
        self.setLEDs(None)

    def cabinetOff(self):
        for i in range(self.cabinetLEDs):
            self.intensity[self.cabinetStart + i] = (0, 0, 0)
        self.setLEDs(None)

    def demo1(self):
        for i in range(23):
            self.intensity[self.ringStart + i] = (255, 0, 0)
            self.intensity[self.ringStart + i + 1] = (255, 0, 0)
            if i % 2 == 0:
                self.intensity[self.ringStart + self.ringsLEDs[-1] + int(i / 2)] = (255, 0, 0)
            else:
                self.intensity[self.ringStart + self.ringsLEDs[-1] + int(i / 2)] = (150, 0, 0)
                self.intensity[self.ringStart + self.ringsLEDs[-1] + int(i / 2) + 1] = (150, 0, 0)
            self.setLEDs(None)
            time.sleep(1)
            self.intensity[self.ringStart + i] = (100, 100, 100)
            self.intensity[self.ringStart + i + 1] = (100, 100, 100)
            self.intensity[self.ringStart + self.ringsLEDs[-1] + int(i / 2)] = (100, 100, 100)
            self.setLEDs(None)

    def demo2(self):
        self.onSnap()
        self.setInner((150, 0, 0))
        self.incrementProgress()
        time.sleep(1)
        self.onSnap()
        self.setInner((0, 150, 0))
        self.incrementProgress()
        time.sleep(1)


if __name__ == '__main__':
    """test the module"""

    ringStart = (512 - 64)
    ringsLEDs = (1, 6, 12, 24)
    totalLEDs = sum(ringsLEDs)

    cabinetStart = 0
    cabinetLEDs = 30

    effectQueue = Queue()
    timerQueue = Queue()

    LEDs = StatusLED(effectQueue=effectQueue,
                          timerQueue=timerQueue,
                          totalLEDs=totalLEDs,
                          ringStart=ringStart,
                          ringsLEDs=ringsLEDs,
                          cabinetStart=cabinetStart,
                          cabinetLEDs=cabinetLEDs,
                          )

    p






# Setup stuff.
