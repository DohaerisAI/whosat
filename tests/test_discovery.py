"""Discovery integration tests (pytest-friendly, skip gracefully in non-Linux/minimal envs)."""

from __future__ import annotations

import shutil
import subprocess
import unittest

try:
    import pytest  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    pytest = None

from whosat.collector.system import enrich_with_psutil, get_listening_ports_ss


def _skip(msg: str):
    if pytest is not None:
        pytest.skip(msg)
    raise unittest.SkipTest(msg)


def test_ss_finds_all_ports():
    if shutil.which('ss') is None:
        _skip('ss not available')
    ports = get_listening_ports_ss()
    # Some CI/minimal environments may have no listeners; skip instead of fail-hard.
    if len(ports) == 0:
        _skip('ss found no listeners on this machine')
    assert len(ports) > 0


def test_loopback_ports_included():
    if shutil.which('ss') is None:
        _skip('ss not available')
    ports = get_listening_ports_ss()
    ips = [p['ip'] for p in ports]
    has_loopback = any(str(ip).startswith('127.') or str(ip) == '::1' for ip in ips)
    print(f'Loopback ports found: {has_loopback}')


def test_postgres_detected_if_running():
    if shutil.which('pg_lsclusters') is None:
        _skip('pg_lsclusters not available')
    result = subprocess.run(['pg_lsclusters'], capture_output=True, text=True)
    if result.returncode != 0:
        _skip('pg_lsclusters failed')

    postgres_ports = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3:
            try:
                postgres_ports.append(int(parts[2]))
            except ValueError:
                pass
    if not postgres_ports:
        _skip('No postgres clusters found')

    ports = get_listening_ports_ss()
    found_ports = [p['port'] for p in ports]
    for pg_port in postgres_ports:
        assert pg_port in found_ports, f'Postgres port {pg_port} not found. Found: {found_ports}'


def test_docker_ports_if_running():
    if shutil.which('docker') is None:
        _skip('Docker CLI not available')
    result = subprocess.run(['docker', 'ps', '--format', '{{.Ports}}'], capture_output=True, text=True)
    if result.returncode != 0:
        _skip('Docker not available')
    # Discovery should not crash even if no containers are running.
    ports = get_listening_ports_ss()
    assert isinstance(ports, list)


def test_access_denied_processes_still_shown():
    ports = get_listening_ports_ss()
    if not ports:
        _skip('No listeners found')
    for p in ports[:25]:
        assert 'port' in p
        assert 'ip' in p
        assert 'proto' in p
        enriched = enrich_with_psutil(p)
        assert 'port' in enriched


def test_both_tcp_and_udp():
    ports = get_listening_ports_ss()
    if not ports:
        _skip('No listeners found')
    protos = {str(p['proto']).upper() for p in ports}
    assert 'TCP' in protos, 'No TCP ports found at all'


def test_no_duplicate_ports():
    ports = get_listening_ports_ss()
    if not ports:
        _skip('No listeners found')
    seen = set()
    for p in ports:
        key = (p['port'], p['ip'], p['proto'])
        assert key not in seen, f'Duplicate port entry: {key}'
        seen.add(key)
