Summary: A tool to detect and log TCP port scans
Name: scanlogd
Version: 2.2.8
Release: 1%{?dist}
License: BSD-compatible
URL: https://www.openwall.com/scanlogd/
Source0: https://www.openwall.com/scanlogd/scanlogd-%{version}.tar.gz
Source1: scanlogd.service

BuildRequires: gcc
BuildRequires: make
BuildRequires: systemd-rpm-macros
Requires(pre): shadow-utils
%{?systemd_requires}

%description
scanlogd detects port scans and writes one line per scan via the syslog(3)
mechanism. If a source address sends multiple packets to different ports
in a short time, the event will be logged.

%prep
%autosetup
# Keep the upstream privilege drop and chroot, but give this package its own
# empty root-owned chroot directory instead of sharing /var/empty.
sed -i 's|"/var/empty"|"/var/lib/scanlogd/empty"|' params.h

%build
%make_build linux CFLAGS="-Wall %{optflags}" LDFLAGS="%{build_ldflags}"

%install
install -Dpm 0755 scanlogd %{buildroot}%{_sbindir}/scanlogd
install -Dpm 0644 scanlogd.8 %{buildroot}%{_mandir}/man8/scanlogd.8
install -Dpm 0644 %{SOURCE1} %{buildroot}%{_unitdir}/scanlogd.service
install -d -m 0755 %{buildroot}%{_localstatedir}/lib/scanlogd/empty

%pre
getent group scanlogd >/dev/null || /usr/sbin/groupadd -r scanlogd
getent passwd scanlogd >/dev/null || /usr/sbin/useradd -r -g scanlogd -d / -s /sbin/nologin -M scanlogd

%post
%systemd_post scanlogd.service

%preun
%systemd_preun scanlogd.service

%postun
%systemd_postun_with_restart scanlogd.service

%files
%license LICENSE
%doc README.md
%{_sbindir}/scanlogd
%{_mandir}/man8/scanlogd.8*
%{_unitdir}/scanlogd.service
%dir %{_localstatedir}/lib/scanlogd
%dir %{_localstatedir}/lib/scanlogd/empty

%changelog
* Sun Oct 11 2026 EL9 packaging - 2.2.8-1
- Use systemd instead of the SysV init script
- Preserve upstream privilege drop and use dedicated empty chroot directory
- Replace chkconfig scriptlets with systemd RPM macros

* Wed Mar 10 2021 Solar Designer <solar-at-owl.openwall.com> 2.2.8-owl1
- Define _DEFAULT_SOURCE for new glibc, keep _BSD_SOURCE for old glibc
- Clarify that SCANLOGD_CHROOT directory must be root-owned
- Add README.md based on man page

* Mon Jun 30 2014 (galaxyMaster) <galaxy-at-owl.openwall.com> 2.2.7-owl2
- Replaced the deprecated PreReq tag with Requires(post,preun).

* Wed Aug 15 2012 Solar Designer <solar-at-owl.openwall.com> 2.2.7-owl1
- Fixed an off-by-one bug in the safety check against SCAN_MAX_COUNT.  In
properly configured builds of scanlogd, SCAN_WEIGHT_THRESHOLD is such that it's
always hit before SCAN_MAX_COUNT would be hit, so this bug did not matter for
those.  However, other projects reusing this code could make these settings
runtime (mis)configurable, thereby exposing the bug.  Luckily, in scanlogd
itself, if it is misconfigured like this, a port number written right beyond
the array limit would overwrite relatively unimportant data only (part of the
same struct), which could be directly provided/spoofed by the remote system
anyway.  However, in other projects reusing code from scanlogd this could be
different.  Thanks to Florian Westphal for reporting this bug.
- Switched to heavily cut-down BSD license.

* Sun Mar 05 2006 Solar Designer <solar-at-owl.openwall.com> 2.2.6-owl1
- Use sysconf(_SC_CLK_TCK) instead of CLK_TCK when _SC_CLK_TCK is known to be
available or CLK_TCK is not.

* Thu Jun 10 2004 Solar Designer <solar-at-owl.openwall.com> 2.2.5-owl1
- Dropped the cleanup() stuff because it was not async-signal-safe and
to implement it properly would depend on pcap_breakloop() and on a
non-existent(?) equivalent for it with libnids; this code was only used
when running as root which is something to not do anyway.

* Thu Jun 03 2004 Solar Designer <solar-at-owl.openwall.com> 2.2.4-owl1
- Detach from the tty by opening /dev/null on fd 0, 1, 2.

* Wed Jun 02 2004 Solar Designer <solar-at-owl.openwall.com> 2.2.3-owl1
- When built with libnids or direct libpcap support, use Pavel Kankovsky's
smart pcap expression, with a minor enhancement.
- Explained "any" and "all" magic device names in a comment in params.h.
- Dropped the rlog stuff; librlog was never released.
- chroot to /var/empty.
- Do register scanlogd with chkconfig, but don't enable it for any runlevels
by default.
- Moved this spec file and the init script to under scanlogd/ to include
them in the non-Owl-specific distribution of scanlogd.

* Sun May 23 2004 Solar Designer <solar-at-owl.openwall.com> 2.2.2-owl1
- #include <stdlib.h> for exit(3) (apparently this is actually needed on
FreeBSD).
- Obfuscated e-mail addresses in the man page and sources.

* Wed May 08 2002 Solar Designer <solar-at-owl.openwall.com> 2.2.1-owl1
- Start after syslogd.
- Don't abuse glibc-internal __feature macros.

* Wed Feb 06 2002 Solar Designer <solar-at-owl.openwall.com>
- Enforce our new spec file conventions.

* Thu Jul 12 2001 Solar Designer <solar-at-owl.openwall.com>
- Packaged scanlogd for Owl.
