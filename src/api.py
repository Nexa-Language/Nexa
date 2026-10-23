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

import sys
import os
import io
import contextlib
import importlib.util
from .compiler import compile_file
from .runtime.mcp_client import mcp_session_scope
import uuid

class NexaRuntime:
    @staticmethod
    def run_script(file_path: str, inputs: dict) -> dict:
        py_code = compile_file(file_path).python_code

        # Create a temporary py file in .nexa_build directory
        build_dir = os.path.join(os.path.dirname(file_path), ".nexa_build")
        os.makedirs(build_dir, exist_ok=True)
        py_path = os.path.join(build_dir, os.path.basename(file_path).replace(".nx", ".py"))

        with open(py_path, 'w', encoding='utf-8') as f:
            f.write(py_code)

        # 4. Use importlib to load dynamically
        module_name = "nexa_ephemeral_" + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(module_name, py_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            f_out = io.StringIO()
            with mcp_session_scope(), contextlib.redirect_stdout(f_out):
                spec.loader.exec_module(module)

                # Inject inputs into the module
                for k, v in inputs.items():
                    setattr(module, k, v)

                result = None
                if hasattr(module, 'flow_main'):
                    result = module.flow_main()

        finally:
            sys.modules.pop(module_name, None)

        output = f_out.getvalue()

        return {
            "result": result,
            "stdout": output
        }
