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

"""
Nexa Runtime Meta Module

Provides runtime metadata access for loops and other control structures.

Usage in generated code:
    runtime.meta.loop_count  - Current loop iteration count
    runtime.meta.last_result - Result from the last loop iteration
"""

class RuntimeMeta:
    """Runtime metadata container"""
    
    def __init__(self):
        self._loop_count = 0
        self._last_result = None
    
    @property
    def loop_count(self) -> int:
        """Get the current loop iteration count"""
        return self._loop_count
    
    @loop_count.setter
    def loop_count(self, value: int):
        """Set the loop iteration count"""
        self._loop_count = value
    
    @property
    def last_result(self):
        """Get the result from the last loop iteration"""
        return self._last_result
    
    @last_result.setter
    def last_result(self, value):
        """Set the last result"""
        self._last_result = value
    
    def reset(self):
        """Reset all metadata"""
        self._loop_count = 0
        self._last_result = None


class MetaProxy:
    """Proxy object for runtime.meta access"""
    
    def __init__(self):
        self._current_meta = RuntimeMeta()
    
    @property
    def loop_count(self) -> int:
        """Access the current loop count"""
        return self._current_meta.loop_count
    
    @property
    def last_result(self):
        """Access the last result"""
        return self._current_meta.last_result
    
    def get_context(self) -> RuntimeMeta:
        """Get the current runtime meta context"""
        return self._current_meta
    
    def set_loop_count(self, count: int):
        """Set the loop count"""
        self._current_meta.loop_count = count
    
    def set_last_result(self, result):
        """Set the last result"""
        self._current_meta.last_result = result


# Global meta proxy instance
class _MetaNamespace:
    """Namespace for runtime.meta"""
    def __init__(self):
        self._proxy = MetaProxy()
    
    @property
    def loop_count(self) -> int:
        return self._proxy.loop_count
    
    @property
    def last_result(self):
        return self._proxy.last_result


class _RuntimeNamespace:
    """Namespace for runtime"""
    def __init__(self):
        self._meta = _MetaNamespace()
    
    @property
    def meta(self) -> _MetaNamespace:
        return self._meta


# Global runtime instance
runtime = _RuntimeNamespace()


# Convenience functions for generated code
def get_loop_count() -> int:
    """Get the current loop count from generated code"""
    return runtime.meta.loop_count


def get_last_result():
    """Get the last result from generated code"""
    return runtime.meta.last_result


def set_loop_count(count: int):
    """Set the loop count from generated code"""
    runtime.meta._proxy.set_loop_count(count)


def set_last_result(result):
    """Set the last result from generated code"""
    runtime.meta._proxy.set_last_result(result)


__all__ = [
    'runtime',
    'RuntimeMeta',
    'MetaProxy',
    'get_loop_count',
    'get_last_result',
    'set_loop_count',
    'set_last_result'
]