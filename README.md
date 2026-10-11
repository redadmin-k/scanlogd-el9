 scanlogd for Enterprise Linux 9

RPM packaging for [Openwall scanlogd](https://www.openwall.com/scanlogd/) 2.2.8 on Enterprise Linux 9, using a native **systemd** unit instead of the upstream SysV init script.

This repository targets **AlmaLinux 9**. The package is intended to be buildable on other RHEL 9-compatible distributions, but those distributions have not been independently runtime-tested here.

> **Scope:** `scanlogd` detects and logs certain TCP port scans. It does **not** block packets by itself. Optional Fail2Ban integration can turn detections into iptables blocks. It is not an IDS/IPS replacement.

## Changes from upstream packaging

- Replace the SysV init script and `chkconfig` integration with `scanlogd.service` and RPM systemd scriptlet macros.
- Preserve the upstream Linux raw-socket capture implementation (no libpcap required for this build).
- Preserve scanlogd's own privilege drop to a dedicated `scanlogd` account.
- Change the compile-time empty chroot path from `/var/empty` to `/var/lib/scanlogd/empty` in the RPM `%prep` step.
- Package the systemd unit, manual page, upstream documentation, and license.

The scan detection algorithm is **not modified**.

## Repository files

```text
scanlogd-el9/
├── README.md
├── scanlogd.spec
└── scanlogd.service
```

The original source archive is downloaded from Openwall; it is **not** maintained in this repository.

## Build an RPM with Mock (AlmaLinux 9)

The following commands use a root shell on an AlmaLinux 9 build machine. For an unprivileged build account, adjust the paths and permissions accordingly.

### 1. Install build tools

Enable EPEL as needed, then install the tools:

```bash
dnf install -y epel-release
dnf install -y mock rpm-build curl git
```

Install a suitable AlmaLinux 9 Mock configuration if it is not already available, and check its name:

```bash
ls /etc/mock/*9*x86_64*.cfg
```

The commands below assume `/etc/mock/alma+epel-9-x86_64.cfg` is available. Mock configuration names vary between installations.

### 2. Clone the packaging repository

```bash
git clone https://github.com/redadmin-k/scanlogd-el9.git
cd scanlogd-el9
```

### 3. Prepare the RPM build tree and upstream source

```bash
mkdir -p ~/rpmbuild/{SOURCES,SPECS,SRPMS,RPMS}
curl -fL https://www.openwall.com/scanlogd/scanlogd-2.2.8.tar.gz -o ~/rpmbuild/SOURCES/scanlogd-2.2.8.tar.gz
cp scanlogd.spec ~/rpmbuild/SPECS/
cp scanlogd.service ~/rpmbuild/SOURCES/
```

**Both** the upstream source archive and `scanlogd.service` must be present in `SOURCES`. Otherwise, `rpmbuild -bs` will report a missing source file.

For source authenticity, consult Openwall's published detached signature (`scanlogd-2.2.8.tar.gz.sign`) and verify it using a trusted copy of the Openwall signing key before building for production.

### 4. Build the source RPM

```bash
rpmbuild -bs ~/rpmbuild/SPECS/scanlogd.spec
```

Expected output:

```text
~/rpmbuild/SRPMS/scanlogd-2.2.8-1.el9.src.rpm
```

### 5. Rebuild in a clean Mock environment

```bash
mock -r alma+epel-9-x86_64 --rebuild ~/rpmbuild/SRPMS/scanlogd-2.2.8-1.el9.src.rpm
```

The RPMs and logs are normally written to:

```text
/var/lib/mock/alma+epel-9-x86_64/result/
```

Check the results:

```bash
ls -lh /var/lib/mock/alma+epel-9-x86_64/result/
```

## Install and start the service

Copy the built binary RPM to the destination EL9 host, then run:

```bash
dnf install -y ./scanlogd-2.2.8-1.el9.x86_64.rpm
systemctl enable --now scanlogd
systemctl status scanlogd --no-pager -l
pgrep -a scanlogd
```

On this build, scanlogd daemonizes itself, so the systemd unit uses `Type=forking`. The service starts with the privileges required to open a TCP raw socket, then scanlogd chroots and drops privileges internally. Do not force `User=scanlogd` in the unit without validating that startup still works.

Check its logs:

```bash
journalctl -t scanlogd -f
grep 'scanlogd\[' /var/log/messages | tail -20
```

The `/var/log/messages` command assumes rsyslog is configured to write the corresponding syslog messages there. A running process alone does not demonstrate successful packet capture.

## Reproduce port-scan detection

Only scan hosts you own or are explicitly authorized to test. Prefer a staging system, and use a separate external test host to avoid blocking your management connection.

From the **external test host** (replace the hostname with your own):

```bash
nmap -n -Pn -sS -T4 -p 22,25,53,80,110,143,443,465,587,993,995 <your-server-hostname>
```

On the **destination EL9 host**, watch for a scanlogd event:

```bash
journalctl -t scanlogd -f
```

Example format (documentation-only addresses):

```text
scanlogd[12345]: 203.0.113.35:39864 to 192.0.2.10 ports 110, 143, 80, 22, 25, 53, ...
```

Detection depends on the number, timing, and weights of destination ports **actually delivered to scanlogd**. The upstream defaults require at least seven distinct ports and a weighted threshold of 21 within the configured timing window. It is not guaranteed that every Nmap invocation will be logged. Packets discarded by an upstream firewall or the local iptables INPUT hook may never reach the TCP raw socket. LXC containers can observe only traffic delivered to their network namespace.

## Optional: Fail2Ban + iptables automatic blocking

This is **optional**: it is not part of the `scanlogd` RPM.

Install and enable Fail2Ban using your distribution's packages, then create `/etc/fail2ban/filter.d/scanlogd.conf`:

```ini
[Definition]
failregex = ^.*scanlogd\[\d+\]:\s+<HOST>:\d+\s+to\s+\S+\s+ports\b
ignoreregex =
```

Create `/etc/fail2ban/jail.d/scanlogd.local`:

```ini
[scanlogd]
enabled = true
filter = scanlogd
logpath = /var/log/messages
backend = auto
maxretry = 1
findtime = 60
bantime = 600
banaction = iptables-allports
```

Review `ignoreip` in your Fail2Ban configuration to protect management, monitoring, and other trusted addresses **before** enabling automatic blocking. Confirm that your installed Fail2Ban provides the selected iptables action.

Test and reload:

```bash
fail2ban-regex /var/log/messages /etc/fail2ban/filter.d/scanlogd.conf --print-all-matched
fail2ban-client -t
systemctl restart fail2ban
fail2ban-client status scanlogd
```

After another **authorized external scan**, verify both the ban list and installed iptables rules:

```bash
fail2ban-client status scanlogd
iptables -S | grep f2b-scanlogd
iptables -nvL f2b-scanlogd --line-numbers
```

A `DROP` rule for the scanner's source IP demonstrates that Fail2Ban installed a rule. A nonzero `pkts` counter on that rule further demonstrates matching traffic was actually dropped. The exact chain name depends on the Fail2Ban action configuration.

### Security considerations

- **Source-IP spoofing:** scanlogd can classify scans without an established TCP connection. A spoofed source IP could therefore cause Fail2Ban to block an innocent third party. Do **not** treat scanlogd-only detections as sufficient justification for a permanent ban.
- **False positives:** the scan threshold, `ignoreip`, and ban duration should be tuned for each deployment.
- **Firewall coverage:** this mechanism does not replace a default-deny firewall, patch management, WAF, authentication controls, or upstream DDoS mitigation.
- **Resource usage:** logging and per-IP blocklists carry operational costs, especially at high traffic rates.

## Tested configuration

Tested on **2026-10-11**:

| Item | Result |
| --- | --- |
| AlmaLinux 9 / x86_64 RPM build | Passed (reported from a local Mock build) |
| Native systemd startup | Passed |
| LXC TCP raw socket | Confirmed for the scanlogd process |
| Internal TCP port-scan detection | Passed |
| External TCP port-scan detection | Passed |
| Fail2Ban log filter | Passed (`fail2ban-regex`: 1 matching event in the test log) |
| Fail2Ban ban action | Passed |
| iptables DROP enforcement | Passed (256 matching packets observed in the test) |

This is a **single-environment functional test**, not an EL9 distribution-wide compatibility certification. SELinux Enforcing behavior and performance under production traffic have not been independently validated. The EL7, EL8, and EL10 packages are maintained separately and are outside the scope of this repository.

## Troubleshooting

- **`Bad file: .../SOURCES/scanlogd.service`:** copy `scanlogd.service` into `~/rpmbuild/SOURCES/` before running `rpmbuild -bs`.
- **No scanlogd events:** check `systemctl status scanlogd`, `journalctl -u scanlogd`, TCP SYN arrival (`tcpdump` where permitted), upstream firewall policies, and the scan threshold.
- **Logs appear but Fail2Ban does not ban:** confirm the actual log path and run `fail2ban-regex`, then check `fail2ban-client get scanlogd ignoreip` and `fail2ban-client get scanlogd maxretry`.
- **Fail2Ban reports a ban but traffic continues:** inspect the effective iptables rules, INPUT hook ordering, source address, and packet counters.
- **LXC restrictions:** check whether the container has the necessary network namespace access and capabilities; successful service startup does not imply that every external packet is observable.

## Upstream, copyright, and license

- Upstream project: <https://www.openwall.com/scanlogd/>
- Upstream source: <https://github.com/openwall/scanlogd>
- Upstream license text: <https://github.com/openwall/scanlogd/blob/main/LICENSE>

scanlogd is distributed under Openwall's **heavily simplified BSD-like license**, permitting source and binary redistribution and modifications, with no warranty. This is **not** a claim that its text is identical to SPDX `BSD-2-Clause` or `BSD-3-Clause`. The RPM SPEC retains the upstream `License: BSD-compatible` designation; check your distribution's packaging policy before adopting a more specific SPDX identifier.

This repository is an **unofficial community packaging project** and is not affiliated with or endorsed by Openwall.
