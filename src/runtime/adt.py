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
P3-4: ADT (Algebraic Data Types) Runtime

Runtime support for struct, enum, trait, and impl declarations.
Uses handle-as-dict pattern for JSON compatibility.

Struct instances: {'_nexa_struct': 'Point', '_nexa_struct_id': 1, 'x': 1, 'y': 2}
Enum variants: {'_nexa_variant': 'Some', '_nexa_enum': 'Option', '_nexa_variant_id': 1, '_nexa_fields': [42]}
Unit variants: {'_nexa_variant': 'None', '_nexa_enum': 'Option'}
"""

from __future__ import annotations
import threading
from typing import Any, Dict, List, Optional, Callable

from .contracts import ContractViolation


# ===== Struct Registry =====

_struct_registry: Dict[str, Dict] = {}  # name -> {'name', 'id', 'fields': [...]}
_struct_registry_lock = threading.Lock()
_struct_id_counter = 0


# ===== Enum Registry =====

_enum_registry: Dict[str, Dict] = {}  # name -> {'name', 'id', 'variants': [...]}
_enum_registry_lock = threading.Lock()
_enum_id_counter = 0


# ===== Trait Registry =====

_trait_registry: Dict[str, Dict] = {}  # trait_name -> {'name', 'id', 'methods': [...]}
_impl_registry: Dict[tuple, Dict] = {}  # (trait_name, type_name) -> {'trait_name', 'type_name', 'methods': {...}}
_trait_registry_lock = threading.Lock()
_impl_registry_lock = threading.Lock()
_trait_id_counter = 0


# ===== Struct Operations =====

def register_struct(name: str, fields: List[Dict]) -> Dict:
    'Register a struct definition. fields is a list of dicts with name and optional type.'
    global _struct_id_counter
    with _struct_registry_lock:
        _struct_id_counter += 1
        struct_id = _struct_id_counter
        _struct_registry[name] = {
            'name': name,
            'id': struct_id,
            'fields': fields,  # [{'name': 'x', 'type': 'Int'}, ...]
        }
    return _struct_registry[name]


def make_struct_instance(name: str, **kwargs) -> Dict:
    'Create a struct instance dict with _nexa_struct marker and individual field keys.'
    global _struct_id_counter
    with _struct_registry_lock:
        if name not in _struct_registry:
            raise ContractViolation(
                f'Struct {name} is not registered',
                clause_type='struct'
            )
        struct_def = _struct_registry[name]
        field_names = [f['name'] for f in struct_def['fields']]
        _struct_id_counter += 1
        instance_id = _struct_id_counter

    # Check for unknown fields
    for key in kwargs:
        if key not in field_names:
            raise ContractViolation(
                f'Unknown field {key} for struct {name}. Valid fields: {field_names}',
                clause_type='struct'
            )

    instance = {
        '_nexa_struct': name,
        '_nexa_struct_id': instance_id,
    }
    for field_name in field_names:
        if field_name in kwargs:
            instance[field_name] = kwargs[field_name]
        else:
            # Default value is None for missing fields
            instance[field_name] = None

    return instance


def struct_get_field(instance: Dict, field_name: str) -> Any:
    'Get struct field value. Raises ContractViolation for invalid field names.'
    struct_name = instance.get('_nexa_struct', '')
    if struct_name:
        with _struct_registry_lock:
            if struct_name in _struct_registry:
                struct_def = _struct_registry[struct_name]
                valid_fields = [f['name'] for f in struct_def['fields']]
                if field_name not in valid_fields:
                    raise ContractViolation(
                        f'Invalid field {field_name} for struct {struct_name}. Valid fields: {valid_fields}',
                        clause_type='struct'
                    )
    if field_name not in instance:
        raise ContractViolation(
            f'Field {field_name} not found in struct instance of {struct_name}',
            clause_type='struct'
        )
    return instance[field_name]


def struct_set_field(instance: Dict, field_name: str, value: Any) -> Dict:
    'Set struct field value. Returns a new dict (immutable update pattern). Raises ContractViolation for invalid fields.'
    struct_name = instance.get('_nexa_struct', '')
    if struct_name:
        with _struct_registry_lock:
            if struct_name in _struct_registry:
                struct_def = _struct_registry[struct_name]
                valid_fields = [f['name'] for f in struct_def['fields']]
                if field_name not in valid_fields:
                    raise ContractViolation(
                        f'Invalid field {field_name} for struct {struct_name}. Valid fields: {valid_fields}',
                        clause_type='struct'
                    )
    new_instance = dict(instance)
    new_instance[field_name] = value
    return new_instance


def lookup_struct(name: str) -> Optional[Dict]:
    'Look up a struct definition by name.'
    with _struct_registry_lock:
        return _struct_registry.get(name)


def get_all_structs() -> Dict[str, Dict]:
    'Get all registered struct definitions.'
    with _struct_registry_lock:
        return dict(_struct_registry)


def is_struct_instance(value: Any, struct_name: str = '') -> bool:
    'Check if a value is a struct instance, optionally of a specific struct.'
    if not isinstance(value, dict):
        return False
    if '_nexa_struct' not in value:
        return False
    if struct_name:
        return value.get('_nexa_struct') == struct_name
    return True


# ===== Enum Operations =====

def register_enum(name: str, variants: List[Dict]) -> Dict:
    'Register an enum definition. variants is a list of dicts with name and optional fields.'
    global _enum_id_counter
    with _enum_registry_lock:
        _enum_id_counter += 1
        enum_id = _enum_id_counter
        _enum_registry[name] = {
            'name': name,
            'id': enum_id,
            'variants': variants,  # [{'name': 'Some', 'fields': ['value']}, {'name': 'None', 'fields': []}]
        }
    return _enum_registry[name]


def make_variant(enum_name: str, variant_name: str, *values) -> Dict:
    'Create a variant dict compatible with pattern matching (_nexa_fields list). Raises ContractViolation for invalid enums/variants.'
    global _enum_id_counter
    with _enum_registry_lock:
        if enum_name not in _enum_registry:
            raise ContractViolation(
                f'Enum {enum_name} is not registered',
                clause_type='enum'
            )
        enum_def = _enum_registry[enum_name]
        variant_names = [v['name'] for v in enum_def['variants']]
        if variant_name not in variant_names:
            raise ContractViolation(
                f'Invalid variant {variant_name} for enum {enum_name}. Valid variants: {variant_names}',
                clause_type='enum'
            )
        # Find variant definition to check field count
        variant_def = None
        for v in enum_def['variants']:
            if v['name'] == variant_name:
                variant_def = v
                break
        expected_fields = variant_def.get('fields', []) if variant_def else []
        if len(values) != len(expected_fields):
            raise ContractViolation(
                f'Variant {enum_name}::{variant_name} expects {len(expected_fields)} fields, got {len(values)}',
                clause_type='enum'
            )
        _enum_id_counter += 1
        variant_id = _enum_id_counter

    variant = {
        '_nexa_enum': enum_name,
        '_nexa_variant': variant_name,
        '_nexa_variant_id': variant_id,
        '_nexa_fields': list(values),
    }
    return variant


def make_unit_variant(enum_name: str, variant_name: str) -> Dict:
    'Create a unit variant (no data fields). Same as make_variant with no values.'
    return make_variant(enum_name, variant_name)


def lookup_enum(name: str) -> Optional[Dict]:
    'Look up an enum definition by name.'
    with _enum_registry_lock:
        return _enum_registry.get(name)


def get_all_enums() -> Dict[str, Dict]:
    'Get all registered enum definitions.'
    with _enum_registry_lock:
        return dict(_enum_registry)


def is_variant_instance(value: Any, enum_name: str = '', variant_name: str = '') -> bool:
    'Check if a value is an enum variant, optionally of a specific enum and variant.'
    if not isinstance(value, dict):
        return False
    if '_nexa_variant' not in value:
        return False
    if enum_name and value.get('_nexa_enum') != enum_name:
        return False
    if variant_name and value.get('_nexa_variant') != variant_name:
        return False
    return True


# ===== Trait Operations =====

def register_trait(name: str, methods: List[Dict]) -> Dict:
    'Register a trait definition. methods is a list of dicts describing method signatures.'
    global _trait_id_counter
    with _trait_registry_lock:
        _trait_id_counter += 1
        trait_id = _trait_id_counter
        _trait_registry[name] = {
            'name': name,
            'id': trait_id,
            'methods': methods,  # [{'name': 'format', 'params': [...], 'return_type': 'String'}, ...]
        }
    return _trait_registry[name]


def register_impl(trait_name: str, type_name: str, methods: Dict[str, Callable]) -> Dict:
    'Register an impl (trait implementation for a type). methods maps method names to callable implementations.'
    with _impl_registry_lock:
        if trait_name not in _trait_registry:
            raise ContractViolation(
                f'Trait {trait_name} is not registered. Known traits: {list(_trait_registry.keys())}',
                clause_type='trait'
            )
        # Check that all required trait methods are implemented
        trait_def = _trait_registry[trait_name]
        trait_method_names = [m['name'] for m in trait_def['methods']]
        impl_method_names = list(methods.keys())
        for required_method in trait_method_names:
            if required_method not in impl_method_names:
                raise ContractViolation(
                    f'Impl for {trait_name} on {type_name} missing required method {required_method}',
                    clause_type='impl'
                )
        key = (trait_name, type_name)
        _impl_registry[key] = {
            'trait_name': trait_name,
            'type_name': type_name,
            'methods': methods,
        }
    return _impl_registry[key]


def call_trait_method(trait_name: str, type_name: str, method_name: str, instance: Any, *args) -> Any:
    'Call a trait method on an instance. Raises ContractViolation if no impl is registered.'
    with _impl_registry_lock:
        key = (trait_name, type_name)
        if key not in _impl_registry:
            raise ContractViolation(
                f'No impl registered for {trait_name} on {type_name}',
                clause_type='impl'
            )
        impl_def = _impl_registry[key]
        if method_name not in impl_def['methods']:
            raise ContractViolation(
                f'Method {method_name} not found in impl for {trait_name} on {type_name}',
                clause_type='impl'
            )
        method_func = impl_def['methods'][method_name]
    # Call the method with instance as first argument (self)
    return method_func(instance, *args)


def lookup_trait(name: str) -> Optional[Dict]:
    'Look up a trait definition by name.'
    with _trait_registry_lock:
        return _trait_registry.get(name)


def lookup_impl(trait_name: str, type_name: str) -> Optional[Dict]:
    'Look up an impl by trait name and type name.'
    with _impl_registry_lock:
        return _impl_registry.get((trait_name, type_name))


def get_all_traits() -> Dict[str, Dict]:
    'Get all registered trait definitions.'
    with _trait_registry_lock:
        return dict(_trait_registry)


def get_all_impls() -> Dict[tuple, Dict]:
    'Get all registered impl definitions.'
    with _impl_registry_lock:
        return dict(_impl_registry)


# ===== Utility Functions =====

def adt_reset_registries():
    'Reset all ADT registries (for testing).'
    global _struct_id_counter, _enum_id_counter, _trait_id_counter
    with _struct_registry_lock:
        _struct_registry.clear()
        _struct_id_counter = 0
    with _enum_registry_lock:
        _enum_registry.clear()
        _enum_id_counter = 0
    with _trait_registry_lock:
        _trait_registry.clear()
        _trait_id_counter = 0
    with _impl_registry_lock:
        _impl_registry.clear()


def adt_get_registry_summary() -> Dict:
    'Get a summary of all registered ADTs (for debugging/inspection).'
    return {
        'structs': get_all_structs(),
        'enums': get_all_enums(),
        'traits': get_all_traits(),
        'impls': {f'{k[0]}::{k[1]}': v for k, v in get_all_impls().items()},
    }