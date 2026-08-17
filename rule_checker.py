"""
NetSage AI - Deterministic Rule Checker
-----------------------------------------
Runs simple, explainable checks over parsed device facts (no AI involved).
Meant to run BEFORE and/or AFTER the AI diagnosis, to catch clear-cut
config mistakes and to sanity-check the AI's output.

Each device/case is represented as a plain dict of "facts" you would pull
from show-command output (either by hand for the lab, or with a small
parser). This script does NOT parse raw CLI text — it works off structured
facts so the checks stay simple and testable. See `sample_cases` at the
bottom for the expected shape, and `parse_hint()` for notes on pulling
these fields out of raw `show` output.

Run:
    python3 rule_checker.py
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeviceFacts:
    case_id: str
    # interfaces: list of dicts: {name, admin_status, line_status, ip, mask, vlan, mode}
    interfaces: list = field(default_factory=list)
    # hosts: list of dicts: {name, ip, mask, gateway}
    hosts: list = field(default_factory=list)
    # dhcp_pools: list of dicts: {name, network, mask, default_router, dns_server, excluded_ranges}
    dhcp_pools: list = field(default_factory=list)
    # routes: list of dicts: {network, mask, next_hop, connected}
    routes: list = field(default_factory=list)
    # vlans expected to exist, e.g. {10, 20, 30}
    expected_vlans: set = field(default_factory=set)


@dataclass
class Finding:
    case_id: str
    check: str
    severity: str
    detail: str


def check_duplicate_ips(facts: DeviceFacts) -> list[Finding]:
    findings = []
    seen = {}
    for h in facts.hosts:
        ip = h.get("ip")
        if not ip:
            continue
        if ip in seen:
            findings.append(Finding(
                facts.case_id, "duplicate_ip", "High",
                f"IP {ip} is assigned to both '{seen[ip]}' and '{h.get('name')}'."
            ))
        else:
            seen[ip] = h.get("name")
    return findings


def check_gateway_mismatch(facts: DeviceFacts) -> list[Finding]:
    findings = []
    router_ips = {i.get("ip") for i in facts.interfaces if i.get("ip")}
    for h in facts.hosts:
        gw = h.get("gateway")
        if gw and router_ips and gw not in router_ips:
            findings.append(Finding(
                facts.case_id, "gateway_mismatch", "High",
                f"Host '{h.get('name')}' gateway {gw} does not match any router interface IP {router_ips}."
            ))
    return findings


def check_wrong_mask(facts: DeviceFacts) -> list[Finding]:
    findings = []
    valid_masks = {
        "255.255.255.0", "255.255.255.128", "255.255.255.192",
        "255.255.254.0", "255.255.0.0", "255.0.0.0", "255.255.255.252"
    }
    for h in facts.hosts:
        mask = h.get("mask")
        if mask and mask not in valid_masks:
            findings.append(Finding(
                facts.case_id, "wrong_mask", "Medium",
                f"Host '{h.get('name')}' has an unusual/likely-wrong mask: {mask}."
            ))
    return findings


def check_interface_down(facts: DeviceFacts) -> list[Finding]:
    findings = []
    for i in facts.interfaces:
        if i.get("admin_status") == "down":
            findings.append(Finding(
                facts.case_id, "interface_admin_down", "High",
                f"Interface {i.get('name')} is administratively down (needs 'no shutdown')."
            ))
        elif i.get("line_status") == "down" and i.get("admin_status") == "up":
            findings.append(Finding(
                facts.case_id, "interface_line_down", "Medium",
                f"Interface {i.get('name')} is up/down (physical or negotiation issue)."
            ))
    return findings


def check_missing_vlan(facts: DeviceFacts) -> list[Finding]:
    findings = []
    present_vlans = {i.get("vlan") for i in facts.interfaces if i.get("vlan") is not None}
    missing = facts.expected_vlans - present_vlans
    for vlan in missing:
        findings.append(Finding(
            facts.case_id, "missing_vlan", "Medium",
            f"Expected VLAN {vlan} not found assigned to any known interface."
        ))
    return findings


def check_missing_routes(facts: DeviceFacts) -> list[Finding]:
    findings = []
    # Flag any host whose subnet has no matching connected/static route on the router
    known_nets = set()
    for r in facts.routes:
        known_nets.add((r.get("network"), r.get("mask")))
    for h in facts.hosts:
        # crude /24 check placeholder — real lab would compute actual network from ip+mask
        net_guess = ".".join(h.get("ip", "0.0.0.0").split(".")[:3]) + ".0"
        mask = h.get("mask", "255.255.255.0")
        if (net_guess, mask) not in known_nets and facts.routes:
            findings.append(Finding(
                facts.case_id, "missing_route", "High",
                f"No route found for host '{h.get('name')}' network {net_guess}/{mask}."
            ))
    return findings


def check_dhcp_pool_sanity(facts: DeviceFacts) -> list[Finding]:
    findings = []
    for pool in facts.dhcp_pools:
        if not pool.get("default_router"):
            findings.append(Finding(
                facts.case_id, "dhcp_missing_default_router", "Medium",
                f"DHCP pool '{pool.get('name')}' has no default-router configured."
            ))
        if not pool.get("dns_server"):
            findings.append(Finding(
                facts.case_id, "dhcp_missing_dns", "Low",
                f"DHCP pool '{pool.get('name')}' has no dns-server configured."
            ))
    return findings


ALL_CHECKS = [
    check_duplicate_ips,
    check_gateway_mismatch,
    check_wrong_mask,
    check_interface_down,
    check_missing_vlan,
    check_missing_routes,
    check_dhcp_pool_sanity,
]


def run_checks(facts: DeviceFacts) -> list[Finding]:
    findings = []
    for check in ALL_CHECKS:
        findings.extend(check(facts))
    return findings


def parse_hint():
    """
    Notes on pulling DeviceFacts fields out of raw `show` command text
    (do this by hand for the lab, or write a small regex parser):

      interfaces  <- 'show interfaces status' / 'show ip interface brief'
                      (name, admin_status, line_status, ip, vlan, mode)
      hosts       <- PC 'ipconfig' output or lab documentation
                      (name, ip, mask, gateway)
      dhcp_pools  <- 'show running-config | section dhcp'
                      (name, network, default_router, dns_server, excluded_ranges)
      routes      <- 'show ip route'
                      (network, mask, next_hop, connected)
      expected_vlans <- from the lab topology diagram / cases.csv topology_note
    """
    pass


# ---------------------------------------------------------------------------
# Sample run against a few cases from the dataset (facts entered by hand,
# mirroring cases.csv C01, C05, C08, C09, C10)
# ---------------------------------------------------------------------------
sample_cases = [
    DeviceFacts(
        case_id="C01",
        interfaces=[
            {"name": "Fa0/2", "admin_status": "up", "line_status": "up", "vlan": 10},
            {"name": "Fa0/4", "admin_status": "up", "line_status": "up", "vlan": 1},  # should be 10
        ],
        expected_vlans={10},
    ),
    DeviceFacts(
        case_id="C05",
        interfaces=[{"name": "Gi0/0", "admin_status": "up", "line_status": "up", "ip": "192.168.5.1"}],
        hosts=[{"name": "PC1", "ip": "192.168.5.20", "mask": "255.255.255.0", "gateway": "192.168.6.1"}],
    ),
    DeviceFacts(
        case_id="C08",
        dhcp_pools=[{"name": "LAN1", "network": "192.168.10.0", "default_router": None, "dns_server": None}],
    ),
    DeviceFacts(
        case_id="C09",
        interfaces=[{"name": "Gi0/0", "admin_status": "up", "line_status": "down"}],
    ),
    DeviceFacts(
        case_id="C10",
        hosts=[
            {"name": "PC-static", "ip": "192.168.12.15", "mask": "255.255.255.0"},
            {"name": "PC-dhcp", "ip": "192.168.12.15", "mask": "255.255.255.0"},
        ],
    ),
]


if __name__ == "__main__":
    total = 0
    for facts in sample_cases:
        findings = run_checks(facts)
        total += len(findings)
        print(f"\n=== {facts.case_id} ===")
        if not findings:
            print("  No deterministic issues found.")
        for f in findings:
            print(f"  [{f.severity}] {f.check}: {f.detail}")
    print(f"\nTotal findings across sample cases: {total}")
