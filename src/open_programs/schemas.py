"""Installed, versioned schemas generated from the runtime's validated objects."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evolution import EvolutionApproval, EvolutionProposal, EvolutionReport
from .migration import MigrationReport
from .model import (
    ApplyResult,
    ApprovalGrant,
    BuildArtifact,
    BuildLock,
    CheckReport,
    CompilerEnvironment,
    EvidenceRecord,
    FrozenModel,
    PatchProposal,
    ProgramError,
    ProgramIR,
    RuntimeActivity,
)
from .protocol import METHOD_PARAMS
from .reuse import ImplementationCapsule

MODELS: dict[str, type[FrozenModel]] = {
    "program": ProgramIR, "check-report": CheckReport, "environment": CompilerEnvironment,
    "artifact": BuildArtifact, "lock": BuildLock, "evidence": EvidenceRecord, "activity": RuntimeActivity,
    "patch": PatchProposal, "approval": ApprovalGrant, "application": ApplyResult, "capsule": ImplementationCapsule,
    "migration": MigrationReport, "evolution-proposal": EvolutionProposal, "evolution-report": EvolutionReport,
    "evolution-approval": EvolutionApproval,
}


def schema_for(name: str) -> dict[str, object]:
    if name == "author-protocol":
        definitions = {}
        alternatives = []
        for method, model in METHOD_PARAMS.items():
            params = model.model_json_schema()
            definitions.update(params.pop("$defs", {}))
            alternatives.append({"type": "object", "required": ["jsonrpc", "method"], "additionalProperties": False,
                                 "properties": {"jsonrpc": {"const": "2.0"}, "id": {"type": ["string", "integer", "null"]},
                                                "method": {"const": method}, "params": params}})
        schema = {"$defs": definitions, "oneOf": alternatives}
    elif name in MODELS:
        schema = MODELS[name].model_json_schema()
    else:
        raise ProgramError("schema_unknown", "Available schemas: " + ", ".join((*MODELS, "author-protocol")))
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for name in (*MODELS, "author-protocol"):
        (args.output_directory / (name + ".schema.json")).write_text(json.dumps(schema_for(name), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
