"""Trusted workflow CLI boundary for capacity assessment and final armament."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

# Any is restricted to the closed, validated capacity receipt's JSON field values.

from .armament import CapacityRejected, check_prepared_capacity
from .arm_controller import arm_and_authorize
from .github_journal import GitHubRefJournal
from .identity import canonical_bytes


def add_capacity_arguments(subcommands: argparse._SubParsersAction) -> None:
    for name in ("internal-input-capacity", "internal-arm", "internal-arm-authorize"):
        command = subcommands.add_parser(name)
        command.add_argument("--request", required=True)
        command.add_argument("--packet-id", required=True)
        command.add_argument("--packet-dir", required=True, type=Path)
        command.add_argument("--executing-broker-sha", required=True)
        if name == "internal-arm-authorize":
            command.add_argument("--codespace-name", required=True)
            command.add_argument("--codespace-id", required=True)
            command.add_argument("--authorization-file", type=Path, required=True)


def run_capacity_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "internal-arm-authorize":
        import os
        if args.executing_broker_sha != os.environ.get("GITHUB_SHA"):
            raise ValueError("ARM_EXECUTING_SHA_MISMATCH")
        return arm_and_authorize(journal=GitHubRefJournal(args.broker_repo),
            packet_directory=args.packet_dir, request_id=args.request, packet_id=args.packet_id,
            codespace_name=args.codespace_name, codespace_id=args.codespace_id,
            authorization_file=args.authorization_file)
    try:
        return check_prepared_capacity(
            journal=GitHubRefJournal(args.broker_repo), packet_directory=args.packet_dir,
            request_id=args.request, packet_id=args.packet_id,
            executing_broker_sha=args.executing_broker_sha, arm=args.command == "internal-arm",
        )
    except CapacityRejected as exc:
        # Keep a structured capacity artifact even when the CLI deliberately exits nonzero.
        print(canonical_bytes(exc.receipt).decode("utf-8"))
        raise
