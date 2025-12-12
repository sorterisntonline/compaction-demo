from event_store import event

@event
class AppInit:
    timestamp: int
    version: str = "0.1.0"

@event
class ConfigChanged:
    timestamp: int
    being_id: str
    key: str
    value: str
