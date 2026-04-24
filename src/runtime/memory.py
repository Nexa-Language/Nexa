# ========================================================================
# Copyright (C) 2026 Nexa-Language
# This file is part of Nexa Project.
# 
# Nexa is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# Nexa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Nexa.  If not, see <https://www.gnu.org/licenses/>.
# ========================================================================

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
