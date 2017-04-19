#!/usr/bin/env python

# Test DeepSIM status lights.

import threading
import opc
import time
import copy
import waves


# import math
# import numpy as np


class FrameIntensity(waves.Signal):
    def __init__(self, intensity):
        self._intensity = intensity

    def update(self, newIntensity):
        self._intensity = newIntensity

    def __call__(self):
        return self._intensity


class FramePhase(waves.Signal):
    def __init__(self, piBased=False, phase=0):
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
        # Hack below to reduce the impact noisey ADC frequency.  When time
        # values build up to large number then small frequency variations (like
        # noise from the ADC/potentiometer) are greatly magnified.  By running
        # the current seconds through a modulo 60 it will prevent the frame
        # clock from getting large values while still increasing and wrapping
        # at the same rate. This will only work for driving repeating signals
        # like sine waves, etc.
        self._current_s = time.time()

    def __call__(self):
        return self._current_s


class StatusLED:
    def __init__(self,
                 ringsLEDs,
                 totalLEDs,
                 ringStart,
                 cabinetStart,
                 cabinetLEDs,
                 client=opc.Client('localhost:7890'),
                 glow=(0, 0, 0),  # a tupple containing the min background color
                 power=128,  # the max poser we want to drive the leds. int from 0 to 255
                 ):

        """

        :int totalLEDs: total nr of LEDs
        :tuple ringsLEDs: tupple containing the nr of leds of every concentric ring from center to edge
        """
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

        # Elements to control state
        self.stateDict = {'idle': 0,
                          'runningExp': 10,
                          'runningMosaic': 20,
                          'error': 30
                          }
        self.state = 0
        self.stateLock = threading.Lock

        # Some frames
        self.clock = FrameClock()
        self.frequency = FrameFrequency()
        self.decay = FrameDecay()
        self.duty = FrameDuty()
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

    def setState(self, state):
        with self.stateLock:
            self.state = state

    def getState(self):
        with self.stateLock:
            return self.state

    def onSnap(self, pattern=None):
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
                        0.1]]
        pulseIntensity = copy.copy(self.intensity)
        for p in pattern:
            for i in range(self.ringsLEDs[-1]):
                pulseIntensity[self.ringStart + i] = p[0]
            self.pulseLEDs(pulseIntensity, p[1])

    def onError(self, t=1.0, repeats=30):
        pulseIntensity = copy.copy(self.intensity)
        for i in range(self.ringsLEDs[-1]):
            pulseIntensity[self.ringStart + i] = (self.power, 0, 0)
        for i in range(repeats):
            self.pulseLEDs(pulseIntensity, t)
            time.sleep(t)

    def setWhite(self):
        for i in range(self.totalLEDs):
            self.intensity[self.ringStart + i] = (self.power, self.power, self.power)
        self.setLEDs(None)

    def setOff(self):
        for i in range(self.totalLEDs):
            self.intensity[self.ringStart + i] = (0, 0, 0)
        self.setLEDs(None)

    def pulseLEDs(self, pulseIntensity, t=0.1):
        self.setLEDs(None)
        self.setLEDs(pulseIntensity)
        time.sleep(float(t))
        self.setLEDs(pulseIntensity)
        self.setLEDs(None)

    def chaseLEDs(self, color, duration, decay=1.0, ring=-1, frequency=1.0):
        """
        Creates a LED chasing effect
        :param color: tupple with the color to display
        :param duration: for how long to turn the effect. In seconds
        :param decay: the decay factor
        :param ring: the ring to chase. Defaults to the outer ring
        :param frequency: how many turns per second. Defaults to 1
        :return: None
        """
        nbCycles = int(duration * frequency)

        self.redIntensity.update(color[0])
        self.greenIntensity.update(color[1])
        self.blueIntensity.update(color[2])

        self.frequency.update(frequency)
        self.decay.update(decay)


        waveIntensity = copy.copy(self.intensity)

        for cycle in range(nbCycles):
            self.clock.update()
            for led in range(self.ringsLEDs[ring]):
                self.noPiBasedPhase.update(led, self.ringsLEDs[ring])
                waveIntensity[self.ringStart + led] = (self.red_decayWave(),
                                                       self.green_decayWave(),
                                                       self.blue_decayWave())
            self.setLEDs(waveIntensity)
            # time.sleep(0.1)

        self.setLEDs(None)

    def sineBeat(self, color, frequency, state):

        self.redIntensity.update(color[0])
        self.greenIntensity.update(color[1])
        self.blueIntensity.update(color[2])

        self.frequency.update(frequency)
        self.piBasedPhase.update(0, 0)

        waveIntensity = copy.copy(self.intensity)

        for i in range(duration):
            self.clock.update()
            for led in range(self.totalLEDs):
                waveIntensity[self.ringStart + led] = (self.red_sineWave(),
                                                       self.green_sineWave(),
                                                       self.blue_sineWave())
            self.setLEDs(waveIntensity)
            # time.sleep(0.1)

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


PI = 3.14159
ringStart = (512 - 64)
ringsLEDs = (1, 6, 12, 24)
totalLEDs = sum(ringsLEDs)

cabinetStart = 0
cabinetLEDs = 30

# Setup stuff.
