'''
In this module we create a state machine to follow the state of the executor and launch other tasks form the 
Raspberry. The current setup wil manage the status lights.
'''

from fysom import Fysom

class StateMachine()
    def __init__(self):
        self.fsm = Fysom({'initial': 'configure',

def onpanic(e):
    print('panic! ' + e.msg)
def oncalm(e):
    print('thanks to ' + e.msg + ' done by ' + e.args[0])
def ongreen(e):
    print('green')
def onyellow(e):
    print('yellow')
def onred(e):
    print('red')
fsm = Fysom({'initial': 'green',
             'events': [
                 {'name': 'warn', 'src': 'green', 'dst': 'yellow'},
                 {'name': 'panic', 'src': 'yellow', 'dst': 'red'},
                 {'name': 'panic', 'src': 'green', 'dst': 'red'},
                 {'name': 'calm', 'src': 'red', 'dst': 'yellow'},
                 {'name': 'clear', 'src': 'yellow', 'dst': 'green'}],
             'callbacks': {
                 'onpanic': onpanic,
                 'oncalm': oncalm,
                 'ongreen': ongreen,
                 'onyellow': onyellow,
                 'onred': onred }})

fsm.panic(msg='killer bees')
fsm.calm('bob', msg='sedatives in the honey pots')
