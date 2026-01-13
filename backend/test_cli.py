#!/usr/bin/env python
"""Quick test script for ContextForge CLI."""
import sys
sys.path.insert(0, ".")

from click.testing import CliRunner
from app.contextforge.cli.commands import cli

runner = CliRunner()

print("Testing ContextForge CLI...\n")

print("1. Testing --help")
result = runner.invoke(cli, ["--help"])
print(result.output)
print(f"Exit code: {result.exit_code}\n")

print("2. Testing status command")
result = runner.invoke(cli, ["status"])
print(result.output)
print(f"Exit code: {result.exit_code}\n")

print("3. Testing train --help")
result = runner.invoke(cli, ["train", "--help"])
print(result.output)
print(f"Exit code: {result.exit_code}\n")

print("4. Testing generate --help")
result = runner.invoke(cli, ["generate", "--help"])
print(result.output)
print(f"Exit code: {result.exit_code}\n")

print("5. Testing onboard --help")
result = runner.invoke(cli, ["onboard", "--help"])
print(result.output)
print(f"Exit code: {result.exit_code}\n")

print("All tests completed!")
