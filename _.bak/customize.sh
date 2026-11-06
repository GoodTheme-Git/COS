#!/bin/bash
# Runs INSIDE the new COS system (chroot) at the end of the build. build.sh
# has already synced in the overlay (autologin, cos-session, installer, sudo
# and polkit rules) and COS itself under /opt/cos.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# Security updates. Debian's keyring package in here has the keys the build
# host lacks; if they still do not verify, say so and go on without them.
cat > /etc/apt/sources.list.d/security.list <<'SRC'
deb http://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware
SRC
if apt-get update -q >/dev/null 2>&1 \
   && apt-get -y -q -o Dpkg::Options::=--force-confold upgrade >/dev/null 2>&1; then
    echo "I: security updates applied"
else
    echo "W: could not verify bookworm-security; no security updates past the point release" >&2
    rm -f /etc/apt/sources.list.d/security.list
fi

# Everything build.sh synced in (and every directory above it, which the
# sync re-stamped) belongs to root and is not group/world writable.
while IFS= read -r path; do
    [ -e "$path" ] || continue
    chown -h root:root "$path"
    [ -d "$path" ] && [ ! -L "$path" ] && chmod go-w "$path"
done < /root/cos-stage.list
chmod 755 /
chmod 700 /root
chmod 0440 /etc/sudoers.d/cos
chmod 755 /usr/local/bin/cos-session /usr/local/sbin/cos-install \
          /opt/cos/cos.py /opt/cos/cos_setup.py
ln -sf /opt/cos/cos.py /usr/local/bin/cos

# the user COS runs as: video for DRM, input for evdev, audio for sound
useradd -m -s /bin/bash -G video,input,audio cos
cat >> /home/cos/.bash_profile <<'PROFILE'
# COS: tty1 is COS's. A shell opened from COS's exit menu does not re-enter.
if [ "$(tty)" = /dev/tty1 ] && [ -z "${COS_SESSION:-}" ]; then
    export COS_SESSION=1
    exec /usr/local/bin/cos-session
fi
PROFILE
# The live system goes straight into COS, in graphics mode so the boot
# animation plays (COS falls back to text mode by itself if the hardware
# cannot do it). A disk install removes this so its first boot runs Setup.
cat > /home/cos/.cos_config <<'CFG'
{
  "setup_complete": true,
  "desktop_render": "graphics",
  "boot_seen": false
}
CFG
chown -R cos:cos /home/cos
# the sample gamepad driver, preinstalled
if [ -f /opt/cos/pkgs/Gamepad.cdi ]; then
    runuser -u cos -- env HOME=/home/cos python3 /opt/cos/cos.py \
        --install /opt/cos/pkgs/Gamepad.cdi --yes >/dev/null
fi

echo cos > /etc/hostname
printf '127.0.0.1\tlocalhost\n127.0.1.1\tcos\n' > /etc/hosts
# A minimal system never ran systemd's install presets, so nothing put a
# getty on tty1 -- and without one, the autologin drop-in has nothing to
# apply to and tty1 stays a blank screen.
systemctl enable getty@tty1.service >/dev/null 2>&1
systemctl enable cos-installer.service >/dev/null 2>&1
systemctl enable NetworkManager >/dev/null 2>&1 || true

# smaller image
apt-get clean
rm -rf /var/lib/apt/lists/* /usr/share/doc/* /usr/share/man/* /root/cos-customize.sh /root/cos-stage.list
