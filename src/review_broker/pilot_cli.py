"""CLI parser and execution helpers for permanently bounded pilot commands."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .identity import canonical_bytes
PILOT_COMMANDS = frozenset({
    "pilot-synthetic", "pilot-synthetic-02", "pilot-synthetic-03",
    "pilot-synthetic-03-controller", "pilot-synthetic-04",
    "pilot-synthetic-04-controller", "pilot-synthetic-05",
    "pilot-synthetic-05-controller",
})


def add_pilot_controller(subcommands: Any, name: str) -> None:
    controller = subcommands.add_parser(name)
    controller.add_argument("--execution-authorization", type=Path)
    controller.add_argument("--source-sha", required=True)
    controller.add_argument("--broker-wheel", required=True, type=Path)
    controller.add_argument("--codespace", required=True)
    controller.add_argument("--ssh-config", required=True, type=Path)
    controller.add_argument("--ssh-host-alias", required=True)


def run_prepared_controller(
    args: Any,
    runtime: Any,
    controller: Callable[..., Any],
    authorization_loader: Callable[..., Any],
    transport_factory: Callable[..., Any],
) -> int:
    authorization = authorization_loader(args.execution_authorization)
    transport = transport_factory(
        args.codespace, args.ssh_host_alias, args.ssh_config, runtime=runtime,
    )
    result = controller(
        authorization=authorization, source_sha=args.source_sha,
        wheel_path=args.broker_wheel, codespace_identity=args.codespace,
        transport=transport,
    )
    print(canonical_bytes(result).decode("utf-8"))
    return 0 if result.get("pilot_acceptance") == "PASS" else 1


def run_remote_pilot(args: Any, runner: Callable[..., Any]) -> int:
    result = runner(broker_wheel_sha256=args.broker_wheel_sha256)
    print(canonical_bytes(result).decode("utf-8"))
    return 0 if result.get("pilot_functional") == "PASS" else 1
