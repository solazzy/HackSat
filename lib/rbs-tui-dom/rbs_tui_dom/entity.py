import logging
from enum import Enum
from typing import Any, List, TypeVar, Generic, Union, Dict, Optional

from rbs_tui_dom.error import AlreadyExistError
from rbs_tui_dom.event_emitter import EventEmitter

T = TypeVar('T')
LOGGER = logging.getLogger("rbs_tui_dom.entity")


class EntityEventType(Enum):
    ENTITY_CHANGED = "entity_changed"
    ENTITY_LOAD = "entity_load"
    VALUE_CHANGED = "value_changed"


class EntityLoadEvent:
    def __init__(self, entity: 'ObservableEntity', is_loading: bool, is_loaded: bool):
        self.entity = entity
        self.is_loading = is_loading
        self.is_loaded = is_loaded


class EntityPropertyValueChangeEvent:
    def __init__(self, entity: 'ObservableEntity', property_name: str, value: Any, prev_value: Any):
        self.entity = entity
        self.value = value
        self.prev_value = prev_value
        self.property_name = property_name


class PropertyValueChangeEvent:
    def __init__(self, property_name: str, value: Any, prev_value: Any):
        self.property_name = property_name
        self.value = value
        self.prev_value = prev_value


class ObservableProperty(EventEmitter, Generic[T]):
    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self._value = None


class UpdatablePropertyValue(Generic[T]):
    def __init__(self, observable_property: ObservableProperty[T], value: T):
        self._observable_property = observable_property
        self.value = value

    @property
    def value(self) -> T:
        return self._observable_property._value

    @value.setter
    def value(self, value: T):
        if self._observable_property._value == value:
            return
        previous_value = self._observable_property._value
        self._observable_property._value = value
        LOGGER.debug(
            f"Triggering EntityEventType.VALUE_CHANGED on property"
            f" {self._observable_property.name}: value={value}, previous value={previous_value}"
        )
        self._observable_property.emit(
            EntityEventType.VALUE_CHANGED,
            PropertyValueChangeEvent(self._observable_property.name, value, previous_value)
        )


class ObservableEntity(EventEmitter, Generic[T]):
    def __init__(
            self,
            identifier: Union[str, int, bytes],
            observable_properties: List[ObservableProperty],
            model: T = None
    ):
        super().__init__()
        self.id = identifier
        self._is_loading = False
        self._model = model
        self._observable_properties = observable_properties
        for property in self._observable_properties:
            property.add_observer(EntityEventType.VALUE_CHANGED, self._on_property_change)

    def _on_property_change(self, event: PropertyValueChangeEvent):
        LOGGER.debug(
            f"Triggering EntityEventType.ENTITY_CHANGED on entity {type(self).__name__}:"
            f"{self.id} for property {event.property_name}: value={event.value}"
        )
        self.emit(
            EntityEventType.ENTITY_CHANGED,
            EntityPropertyValueChangeEvent(self, event.property_name, event.value, event.prev_value)
        )

    @property
    def is_loading(self) -> T:
        return self._is_loading

    @property
    def is_loaded(self) -> T:
        return self._model is not None

    @property
    def model(self) -> T:
        return self._model

    def set_loading(self):
        if self._is_loading is True:
            return
        self._is_loading = True
        self._model = None
        self.emit(
            EntityEventType.ENTITY_LOAD,
            EntityLoadEvent(self, self.is_loading, self.is_loaded)
        )

    def set_model(self, data: Optional[T]):
        if self._model == data:
            return
        self._is_loading = False
        self._model = data
        self.emit(
            EntityEventType.ENTITY_LOAD,
            EntityLoadEvent(self, self.is_loading, self.is_loaded)
        )


class CollectionLoadEvent:
    def __init__(self, collection: 'ObservableCollection', is_loading: bool, is_loaded: bool):
        self.collection = collection
        self.is_loading = is_loading
        self.is_loaded = is_loaded


class CollectionEvent(Enum):
    COLLECTION_LOAD = "load"
    COLLECTION_CHANGED = "changed"
    ITEM_ADDED = "added"
    ITEM_REMOVED = "removed"
    RESET = "reset"


class ObservableCollection(EventEmitter, Generic[T]):
    def __init__(self, children: List[T] = None):
        super().__init__()
        self._children: List[T] = []
        self._children_map: Dict[Union[int, str], int] = {}
        self._is_loaded = False
        self._is_loading = False
        if children is not None:
            self.set_children(children, True)

    @property
    def is_loaded(self):
        return self._is_loaded

    @property
    def is_loading(self):
        return self._is_loading

    def set_loading(self):
        if self._is_loading:
            return
        self._is_loading = True
        self.emit(
            CollectionEvent.COLLECTION_LOAD,
            CollectionLoadEvent(self, self.is_loading, self.is_loaded)
        )

    def get_children(self) -> List[T]:
        return self._children

    def get_child(self, index) -> T:
        return self._children[index]

    def get_child_by_id(self, id: Union[int, str, bytes]) -> Optional[T]:
        index = self._children_map.get(id, None)
        if index is None:
            return None
        return self._children[index]

    def get_child_index_by_id(self, id: Union[int, str, bytes]) -> Optional[T]:
        return self._children_map.get(id, None)

    def set_children(self, children: List[T], silent: bool = False):
        while len(self._children) > 0:
            self.remove_child_at(0, True)
        assert not self._children_map, "The collection children map should be empty"
        assert not self._children, "The collection children list should be empty"
        self._is_loaded = True
        self._is_loading = False
        for child in children:
            self.add_child(child, None, True)
        if not silent:
            self.emit(CollectionEvent.RESET)
            self.emit(
                CollectionEvent.COLLECTION_LOAD,
                CollectionLoadEvent(self, self.is_loading, self.is_loaded)
            )
        return self

    def _on_child_changed_event(self, event: EntityPropertyValueChangeEvent):
        self.emit(EntityEventType.ENTITY_CHANGED, event)

    def _on_child_load_event(self, event: EntityLoadEvent):
        self.emit(EntityEventType.ENTITY_LOAD, event)

    def add_child(self, child: T, index: int = None, silent: bool = False):
        if index is None:
            index = len(self._children)
        if not isinstance(child, ObservableEntity):
            raise ValueError("The collection can only wrap entities")
        if child.id in self._children_map:
            raise AlreadyExistError("An entity with the same ID already exist")
        child.add_observer(EntityEventType.ENTITY_CHANGED, self._on_child_changed_event)
        child.add_observer(EntityEventType.ENTITY_LOAD, self._on_child_load_event)
        self._children_map[child.id] = index
        self._children.insert(index, child)
        for i in range(index + 1, len(self._children)):
            self._children_map[self._children[i].id] = i
        if not silent:
            self.emit(CollectionEvent.ITEM_ADDED, index, child)
            self.emit(CollectionEvent.COLLECTION_CHANGED)
        return self

    def remove_child_at(self, index: int = None, silent: bool = False):
        child = self._children[index]
        child.remove_observer(EntityEventType.ENTITY_CHANGED, self._on_child_changed_event)
        child.remove_observer(EntityEventType.ENTITY_LOAD, self._on_child_load_event)
        del self._children[index]
        del self._children_map[child.id]
        for i in range(index, len(self._children)):
            self._children_map[self._children[i].id] = i

        if not silent:
            self.emit(CollectionEvent.ITEM_REMOVED, index, child)
            self.emit(CollectionEvent.COLLECTION_CHANGED)
        return self

    def remove_child(self, model: ObservableEntity, silent: bool = False):
        index = self.get_child_index_by_id(model.id)
        return self.remove_child_at(index, silent)

    def remove_child_by_id(self, id: Union[int, str], silent: bool = False):
        child = self.get_child_by_id(id)
        if child is None:
            return
        return self.remove_child(child, silent)


