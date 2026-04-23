"""
P3-3: Pattern Matching Runtime Helpers

Runtime support functions for Nexa pattern matching and destructuring.
These functions are used by the generated Python code to perform
pattern matching at runtime.
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Optional, Tuple, Union


def nexa_match_pattern(pattern: Dict, value: Any) -> Optional[Dict]:
    """
    Match a value against a pattern AST and return bindings if successful.
    
    Args:
        pattern: Pattern AST dict with 'kind' and associated fields
        value: The value to match against
    
    Returns:
        Dict of variable bindings if match succeeds, None if match fails
    """
    kind = pattern.get('kind', '')
    
    if kind == 'wildcard':
        # Wildcard always matches, no binding
        return {}
    
    elif kind == 'variable':
        # Variable always matches, binds the value to the variable name
        return {pattern['name']: value}
    
    elif kind == 'literal':
        # Literal matches if value equals the literal value
        pat_value = pattern.get('value')
        # Convert pattern value to appropriate type
        if pattern.get('value_type') == 'int':
            pat_value = int(pat_value) if pat_value is not None else 0
        elif pattern.get('value_type') == 'float':
            pat_value = float(pat_value) if pat_value is not None else 0.0
        elif pattern.get('value_type') == 'bool':
            if isinstance(pat_value, str):
                pat_value = pat_value.lower() == 'true'
        if value == pat_value:
            return {}
        return None
    
    elif kind == 'tuple':
        # Tuple matches if value is list/tuple of exact length
        elements = pattern.get('elements', [])
        if not isinstance(value, (list, tuple)):
            return None
        if len(value) != len(elements):
            return None
        bindings = {}
        for i, elem_pattern in enumerate(elements):
            result = nexa_match_pattern(elem_pattern, value[i])
            if result is None:
                return None
            bindings.update(result)
        return bindings
    
    elif kind == 'array':
        # Array matches if value is list with minimum length
        elements = pattern.get('elements', [])
        rest = pattern.get('rest')
        if not isinstance(value, (list, tuple)):
            return None
        min_len = len(elements)
        if rest is None:
            # Exact length match
            if len(value) != min_len:
                return None
        else:
            # At least min_len elements
            if len(value) < min_len:
                return None
        bindings = {}
        for i, elem_pattern in enumerate(elements):
            result = nexa_match_pattern(elem_pattern, value[i])
            if result is None:
                return None
            bindings.update(result)
        # Rest collector
        if rest is not None:
            bindings[rest] = list(value[min_len:])
        return bindings
    
    elif kind == 'map':
        # Map matches if value is dict with required keys
        entries = pattern.get('entries', [])
        rest = pattern.get('rest')
        if not isinstance(value, dict):
            return None
        bindings = {}
        required_keys = []
        for entry in entries:
            key = entry.get('key')
            value_pattern = entry.get('value_pattern')
            required_keys.append(key)
            if key not in value:
                return None
            if value_pattern is not None:
                result = nexa_match_pattern(value_pattern, value[key])
                if result is None:
                    return None
                bindings.update(result)
            else:
                # Shorthand: {name} binds value to variable 'name'
                bindings[key] = value[key]
        if rest is None:
            # Exact key match (no extra keys allowed) — actually we allow extra keys
            # for map patterns without rest, we just don't bind them
            pass
        else:
            # Rest collector: bind remaining keys
            remaining = {k: v for k, v in value.items() if k not in required_keys}
            bindings[rest] = remaining
        return bindings
    
    elif kind == 'variant':
        # Variant matches enum variant
        enum_name = pattern.get('enum_name', '')
        variant_name = pattern.get('variant_name', '')
        fields = pattern.get('fields', [])
        if not isinstance(value, dict):
            return None
        # Check variant marker
        if value.get('_nexa_variant') != variant_name:
            return None
        if value.get('_nexa_enum') != enum_name:
            return None
        bindings = {}
        variant_fields = value.get('_nexa_fields', [])
        for i, field_pattern in enumerate(fields):
            if i < len(variant_fields):
                result = nexa_match_pattern(field_pattern, variant_fields[i])
                if result is None:
                    return None
                bindings.update(result)
        return bindings
    
    return None


def nexa_destructure(pattern: Dict, value: Any) -> Dict:
    """
    Destructure a value according to a pattern, returning bindings.
    
    Similar to nexa_match_pattern but always succeeds (assumes the pattern
    is valid for the value). Used for let-destructuring and for-destructuring.
    
    Args:
        pattern: Pattern AST dict
        value: The value to destructure
    
    Returns:
        Dict of variable bindings
    """
    result = nexa_match_pattern(pattern, value)
    if result is None:
        raise ValueError(
            f'Destructuring pattern {pattern.get("kind")} does not match value: {value}'
        )
    return result


def nexa_make_variant(enum_name: str, variant_name: str, *fields: Any) -> Dict:
    """
    Create a variant value for enum pattern matching.
    
    Args:
        enum_name: The enum type name
        variant_name: The variant name
        fields: Field values for the variant
    
    Returns:
        Dict representing the variant
    """
    return {
        '_nexa_enum': enum_name,
        '_nexa_variant': variant_name,
        '_nexa_fields': list(fields),
    }


# ===== Helper functions for generated code pattern matching =====

def _nexa_is_tuple_like(value: Any, length: int) -> bool:
    'Check if value is a list/tuple of specific length'
    return isinstance(value, (list, tuple)) and len(value) == length


def _nexa_is_list_like(value: Any, min_length: int) -> bool:
    'Check if value is a list with at least min_length elements'
    return isinstance(value, (list, tuple)) and len(value) >= min_length


def _nexa_is_dict_with_keys(value: Any, keys: List[str]) -> bool:
    'Check if value is a dict containing all required keys'
    return isinstance(value, dict) and all(k in value for k in keys)


def _nexa_is_variant(value: Any, enum_name: str, variant_name: str) -> bool:
    'Check if value is a specific enum variant'
    return isinstance(value, dict) and \
           value.get('_nexa_enum') == enum_name and \
           value.get('_nexa_variant') == variant_name


def _nexa_list_rest(value: Any, prefix_length: int) -> List:
    'Get the rest of a list after the prefix'
    return list(value[prefix_length:])


def _nexa_dict_rest(value: Dict, required_keys: List[str]) -> Dict:
    'Get the remaining dict entries not in required_keys'
    return {k: v for k, v in value.items() if k not in required_keys}