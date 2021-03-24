from enum import Enum
from typing import Callable, Any

EventObserver = Callable[[], Any]


class _EventEmitterOperation(Enum):
    ADD_GLOBAL_OBSERVER = 0
    ADD_OBSERVER = 1
    REMOVE_GLOBAL_OBSERVER = 2
    REMOVE_OBSERVER = 3


class EventEmitter:
    def __init__(self):
        self._observers = {}
        self._global_observers = []
        self._emitting = False
        self._pending_operations = []

    def add_global_observer(self, observer: EventObserver):
        if self._emitting:
            self._pending_operations.append(
                (_EventEmitterOperation.ADD_GLOBAL_OBSERVER, observer)
            )
        else:
            self._global_observers.append(observer)
        return self

    def remove_global_observer(self, observer: EventObserver):
        if self._emitting:
            self._pending_operations.append(
                (_EventEmitterOperation.REMOVE_GLOBAL_OBSERVER, observer)
            )
        else:
            self._global_observers.remove(observer)
        return self

    def add_observer(self, event_type: Any, observer: EventObserver) -> 'EventEmitter':
        if self._emitting:
            self._pending_operations.append(
                (_EventEmitterOperation.ADD_OBSERVER, event_type, observer)
            )
        else:
            observers = self._observers.get(event_type, [])
            observers.append(observer)
            if event_type not in self._observers:
                self._observers[event_type] = observers
        return self

    def remove_observer(self, event_type: Any, observer: EventObserver) -> 'EventEmitter':
        if self._emitting:
            self._pending_operations.append(
                (_EventEmitterOperation.REMOVE_OBSERVER, event_type, observer)
            )
        else:
            observers = self._observers.get(event_type, set())
            observers.remove(observer)
        return self

    def emit(self, event_type: Any, *args, **kwargs):
        self._emitting = True
        observers = self._observers.get(event_type, set())
        for observer in observers:
            observer(*args, **kwargs)
        for observer in self._global_observers:
            observer(*args, **kwargs)

        self._emitting = False
        if len(self._pending_operations) > 0:
            for operation, *args in self._pending_operations:
                if operation is _EventEmitterOperation.ADD_GLOBAL_OBSERVER:
                    EventEmitter.add_global_observer(self, *args)
                elif operation is _EventEmitterOperation.REMOVE_GLOBAL_OBSERVER:
                    EventEmitter.remove_global_observer(self, *args)
                elif operation is _EventEmitterOperation.ADD_OBSERVER:
                    EventEmitter.add_observer(self, *args)
                elif operation is _EventEmitterOperation.REMOVE_OBSERVER:
                    EventEmitter.remove_observer(self, *args)
            self._pending_operations.clear()
        return self
