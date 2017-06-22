# Micro/CircuitPython NeoPixel Color Synthesis Experiments pt. 1
# Author: Tony DiCola
# License: Public Domain
#
# This is like an ipython experiment 'notebook' but insted a raw .py file.
# There are 6 commented example blocks below, uncomment _one_ block at a time
# to run it.  You're meant to go through example by example to see the
# progression from the start to the 'final' state.  Comment out an example
# after you're done running it before moving on to uncomment and run the next
# example!
#
# You'll need a strip of NeoPixels connected to your hardware:
#  - Pixel power line connected to 5V or 3.7V lipo battery (VBAT on Feathers).
#    NOTE: If you use 5V power your pixels may or may not light up depending
#    on if your board's IO output is a high enough voltage to drive the pixels.
#    You can use a power diode to drop the pixel voltage down to a level that
#    makes them 'see' the board IO (see pixels on Raspberry Pi:
#    https://learn.adafruit.com/neopixels-on-raspberry-pi/wiring) or a level
#    shifter to raise board IO voltage up to 5V.
#  - Pixel ground to board ground.
#  - Pixel data in to a board digital IO.
#
# In addition for CircuitPython you'll need neopixel.mpy from the latest release
# here: https://github.com/adafruit/Adafruit_CircuitPython_NeoPixel/releases
# to your board's root filesystem.
#
# MicroPython boards besides the ESP8266 will need to have neopixel support
# built in.
#
# Modify the sections below that note the board/pin specific configs and
# MicroPython / CircuitPython specific configs.

# Necessary imports:
import math

################################################################################
# Example 6:
# Add a physical control signal, the value of a potentiometer!  Twist a knob
# to change the frequency of one of the color waves.  Notice how little the
# main code has to change, only the addition of a new signal for the ADC value
# and setting the frequency to it instead of a fixed value--everything
# 'just works' as far as the main loops knows!
#
# You'll need a potentiometer wired to your board as follows:
#  - One of the outer (left or right) three pins connected to board ground.
#  - The opposite outer pin connect to board 3.3V or ADC max reference voltage.
#  - The middle pin connected to an analog input.
################################################################################


class Signal:

    @property
    def range(self):
        return None

    def __call__(self):
        raise NotImplementedError('Signal must have a callable implementation!')

    def transform(self, y0, y1):
        # Transform the current value of this signal to a new value inside the
        # specified target range (y0...y1).  If this signal has no bounds/range
        # then the value is just clamped to the specified range.
        x = self()
        if callable(y0):
            y0 = y0()
        if callable(y1):
            y1 = y1()
        if self.range is not None:
            # This signal has a known range so we can interpolate between it
            # and the desired target range (y0...y1).
            return y0 + (x-self.range[0]) * \
                        ((y1-y0)/(self.range[1]-self.range[0]))
        else:
            # No range of values for this signal, can't interpolate so just
            # clamp to a value inside desired target range.
            return max(y0, min(y1, x))

    def discrete_transform(self, y0, y1):
        # Transform assuming discrete integer values instead of floats.
        return int(self.transform(y0, y1))


class SignalSource:

    def __init__(self, source=None):
        self.set_source(source)

    def __call__(self):
        # Get the source signal value and return it when reading this signal
        # source's value.
        return self._source()

    def set_source(self, source):
        # Allow setting this signal source to either another signal (anything
        # callable) or a static value (for convenience when something is a
        # fixed value that never changes).
        if callable(source):
            # Callable source, save it directly.
            self._source = source
        else:
            # Not callable, assume it's a static value and make a lambda
            # that's callable to capture and always return it.
            self._source = lambda: source


class SineWave(Signal):

    def __init__(self, time=0.0, amplitude=1.0, frequency=1.0, phase=0.0):
        self.time = SignalSource(time)
        self.amplitude = SignalSource(amplitude)
        self.frequency = SignalSource(frequency)
        self.phase = SignalSource(phase)

    @property
    def range(self):
        # Since amplitude might be a changing signal, the range of this signal
        # changes too and must be computed on the fly!  This might not really
        # be necessary in practice and could be switched back to a
        # non-SignalSource static value set once at initialization.
        amplitude = self.amplitude()
        return -amplitude, amplitude

    def __call__(self):
        return self.amplitude() * \
               math.sin(2*math.pi*self.frequency()*self.time() + self.phase())


class SquareWave(Signal):

    def __init__(self, time=0.0, amplitude=1.0, frequency=1.0, phase=0.0, duty=0.5):
        self.time = SignalSource(time)
        self.amplitude = SignalSource(amplitude)
        self.frequency = SignalSource(frequency)
        self.phase = SignalSource(phase)
        self.duty = SignalSource(duty)

    @property
    def range(self):
        # Since amplitude might be a changing signal, the range of this signal
        # changes too and must be computed on the fly!  This might not really
        # be necessary in practice and could be switched back to a
        # non-SignalSource static value set once at initialization.
        amplitude = self.amplitude()
        return -amplitude, amplitude

    def __call__(self):
        cycle = 1 / self.frequency()
        reminder = (self.time() + self.phase()) % cycle
        if reminder < self.duty() * cycle:
            return self.amplitude()
        else:
            return -1 * self.amplitude()


class DecayWave(Signal):

    def __init__(self, time=0.0, amplitude=1.0, frequency=1.0, phase=0.0, decay=0.0):
        self.time = SignalSource(time)
        self.amplitude = SignalSource(amplitude)
        self.frequency = SignalSource(frequency)
        self.phase = SignalSource(phase)
        self.decay = SignalSource(decay)

    @property
    def range(self):
        # Since amplitude might be a changing signal, the range of this signal
        # changes too and must be computed on the fly!  This might not really
        # be necessary in practice and could be switched back to a
        # non-SignalSource static value set once at initialization.
        amplitude = self.amplitude()
        return 0, amplitude

    def __call__(self):
        reminder = (self.time() + self.phase()) % (1 / self.frequency())
        return self.amplitude() * math.exp(-1 * self.decay() * reminder)


class TransformedSignal(Signal):

    def __init__(self, source_signal, y0, y1, discrete=False):
        self.source = source_signal
        self.y0 = y0
        self.y1 = y1
        if not discrete:
            self._transform = self.source.transform
        else:
            self._transform = self.source.discrete_transform

    @property
    def range(self):
        return self.y0, self.y1

    def __call__(self):
        return self._transform(self.y0, self.y1)
