from typing import Dict, Any

class MemoryManager:
    def __init__(self):
        self.local: Dict[str, Any] = {}
        self.shared: Dict[str, Any] = {}
        self.persistent: Dict[str, Any] = {}
        
    def get_context(self, scope: str = "local") -> Dict[str, Any]:
        if scope == "shared":
            return self.shared
        elif scope == "persistent":
            return self.persistent
        return self.local
    
    def add_to_context(self, key: str, value: Any, scope: str = "local"):
        if scope == "shared":
            self.shared[key] = value
        elif scope == "persistent":
            self.persistent[key] = value
        else:
            self.local[key] = value

global_memory = MemoryManager()
