#!/usr/bin/env python

# Test DeepSIM status lights.

import opc, time, copy
import waves
# import math
# import numpy as N

##### This section is for CircuitPython, change to your pin & NeoPixel count: #####
# import board
# import nativeio
# NEOPIXEL_PIN   = board.D6
# NEOPIXEL_COUNT = 12
# def seconds():
#     return time.monotonic()  # CircuitPython function for current seconds.

##### This section is for MicroPython, change to your pin & NeoPixel count: #####
# import machine
# import utime
# NEOPIXEL_PIN   = machine.Pin(6, machine.Pin.OUT)
# NEOPIXEL_COUNT = 12
# def seconds():
#     return utime.ticks_ms()/1000  # MicroPython code for current seconds

# This section is for the FadeCandy

# # Setup NeoPixels:
# import neopixel
# pixels = neopixel.NeoPixel(NEOPIXEL_PIN, NEOPIXEL_COUNT)
# pixels.fill((0,0,0))
# pixels.write()
#

# print(time.monotonic())
# seconds()
# for i in range(1,1000):
#     clock.update()
#     color = (red_wave(), green_wave(), 0)
#     pixels.fill(color)
#     pixels.write()
#     # print("r={}\tg={}\tb={}".format(*color))
#     # time.sleep(0.1)
#
# print(time.monotonic())
# seconds()
#


PI = 3.14159
ringStart = (512-64)
ringsLEDs = (1, 6, 12, 24)
totalLEDs = sum(ringsLEDs)

cabinetStart=0
cabinetLEDs=30

#Setup stuff.

glow = 0 # Sets the background brightness. We could define here a function to keep a changing background signal
power = 128 # Sets the maximum power

clock = FrameClock()
piBasedPhase = FramePhase(piBased = True)
noPiBasedPhase = FramePhase(piBased = False)
sine_wave   = waves.TransformedSignal(waves.SineWave(phase = piBasedPhase)),
                                      y0 = glow,
                                      y1 = power,
                                      discrete = True)

decay_wave = waves.TransformedSignal(waves.DecayWave(decay = 2.0,
                                                     phase = noPiBasedPhase),
                                      y0 = glow,
                                      y1 = power,
                                      discrete=True)


class FramePhase(waves.Signal):

    def __init__(self, nrOfLEDs, piBased = False):
        self.nrOfLEDs = nrOfLEDs
        self.piBased = piBased
        self.update(0)

    def update(self, LED):
        if self.piBased:
            self._current_phase = (2 * PI * LED) / self.nrOfLEDs
        else:
            self._current_phase = LED / self.nrOfLEDs

    def __call__(self):
        return self._current_phase


class FrameClock(waves.Signal):

    def __init__(self):
        self.update()

    def update(self):
        # Hack below to reduce the impact noisey ADC frequency.  When time
        # values build up to large number then small frequency variations (like
        # noise from the ADC/potentiometer) are greatly magnified.  By running
        # the current seconds through a modulo 60 it will prevent the frame
        # clock from getting large values while still increasing and wrapping
        # at the same rate. This will only work for driving repeating signals
        # like sine waves, etc.
        self._current_s = seconds() % 60

    def __call__(self):
        return self._current_s


class StatusLED():
    def __init__(self):
        self.client = opc.Client('localhost:7890')
        #make an intensity array for the whole fadecandy addressable pixels.
        self.intensity = [(0,0,0)] * 512 
        #inital ppower level is 100 (out of 255)
        self.power = power
        self.ringsLEDs = ringsLEDs
        self.totalLEDs = totalLEDs
        self.ringStart = ringStart
        self.cabinetStart = cabinetStart
        self.cabinetLEDs = cabinetLEDs
        self.progress = 0
        self.savedProgress = (0,0,0)
        
    #Function to call on an image snap
    def onSnap(self,t=0.1):
        pulseIntensity=copy.copy(self.intensity)
        for i in range(self.outerLEDs):
            pulseIntensity[self.ringStart+i]=(self.power,self.power,self.power)
        self.pulseLEDs(pulseIntensity,t)


    def onError(self,t=1.0, repeats=30):
        pulseIntensity=copy.copy(self.intensity)
        for i in range(outerLEDs):
            pulseIntensity[self.ringStart+i]=(self.power,0,0)
        for i in range(repeats):
            self.pulseLEDs(pulseIntensity,t)
            time.sleep(t)

    def setWhite(self):
        for i in range(self.totalLEDs):
            self.intensity[self.ringStart+i]=(self.power,self.power,self.power)
        self.setLEDs(None)

    def setOff(self):
        for i in range(self.totalLEDs):
            self.intensity[self.ringStart+i]=(0,0,0)
        self.setLEDs(None)
    

    def pulseLEDs(self,pulseIntensity,t=0.1):
        self.setLEDs(None)
        self.setLEDs(pulseIntensity)
        time.sleep(float(t))
        self.setLEDs(pulseIntensity)
        self.setLEDs(None)
        
    def setLEDs(self,intensity):
        if intensity is None:
            self.client.put_pixels(self.intensity)
            self.client.put_pixels(self.intensity)
        else:
            self.client.put_pixels(intensity)
            self.client.put_pixels(intensity)


    def setInner(self,col=(100,100,100)):
        for i in range(self.innerLEDs):
            self.intensity[self.ringStart+self.outerLEDs+i]=(col)
        self.setLEDs(None)

    

    def setOuter(self,col=(100,100,100)):
        for i in range(self.outerLEDs):
            self.intensity[self.ringStart+i]=(col)
        self.setLEDs(None)

    def incProgress(self,col=(0,100,0)):
        self.intensity[self.ringStart+self.progress]=self.savedProgress
        self.progress=self.progress+1
        if self.progress>(self.outerLEDs-1):
            self.progress=0
        self.savedProgress=copy.copy(self.intensity[self.ringStart+self.progress])
        self.intensity[self.ringStart+self.progress]=col
        self.setLEDs(None)

    def stopProgress(self):
        self.intensity[self.ringStart+self.progress]=self.savedProgress
        self.setLEDs(None)


    def cabinetOn(self):
        for i in range(self.cabinetLEDs):
            self.intensity[self.cabinetStart+i]=(255,255,255)
        self.setLEDs(None)

    def cabinetOff(self):
        for i in range(self.cabinetLEDs):
            self.intensity[self.cabinetStart+i]=(0,0,0)
        self.setLEDs(None)


    def demo1(self):
        for i in range(23):
            self.intensity[self.ringStart+i]=(255,0,0)
            self.intensity[self.ringStart+i+1]=(255,0,0)      
            if i%2 == 0:
                self.intensity[self.ringStart+self.outerLEDs+int(i/2)]=(255,0,0)
            else:
                self.intensity[self.ringStart+self.outerLEDs+int(i/2)]=(150,0,0)
                self.intensity[self.ringStart+self.outerLEDs+int(i/2)+1]=(150,0,0)
            self.setLEDs(None)
            time.sleep(1)
            self.intensity[self.ringStart+i]=(100,100,100)
            self.intensity[self.ringStart+i+1]=(100,100,100)
            self.intensity[self.ringStart+self.outerLEDs+int(i/2)]=(100,100,100)
            self.setLEDs(None)


    def demo2(self):
        self.onSnap()
        self.setInner((150,0,0))
        self.incProgress()
        time.sleep(1)
        self.onSnap()
        self.setInner((0,150,0))
        self.incProgress()
        time.sleep(1)
        
