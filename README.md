# iOS Metal HUD Launcher

Launch any iOS game with Apple's **Metal performance HUD** (FPS, frame time, GPU time, memory),
**wirelessly**, with **no Xcode, no jailbreak and no root**. Optionally, launch it with **one tap
from the iPhone itself**.

```
iPhone  ──Wi-Fi or Tailscale──  any Linux/macOS machine running `hud`
                                 └─ launches the game with MTL_HUD_ENABLED=1
```

- **Local:** the computer and the iPhone are on the same Wi-Fi.
- **Remote:** the computer is a cloud server, and the iPhone runs Tailscale. Launch from anywhere,
  and tap a home-screen Shortcut to start a game. See **[docs/remote-and-shortcuts.md](docs/remote-and-shortcuts.md)**.

No app code is modified and nothing is injected. `MTL_HUD_ENABLED` is Apple's own debug switch,
set when the game launches, exactly as Xcode does it.

---

## Requirements

| | |
|--|--|
| Computer | Linux or macOS with **Python 3.13+** (needed for the TLS-PSK ciphers) |
| iPhone | iOS 17 or later, with a passcode (Developer Mode is enabled in setup) |
| Cable | A USB cable, **once**, for pairing |
| Tools | `pipx install --python python3.13 pymobiledevice3` |
| Linux only | `sudo apt install usbmuxd libimobiledevice-utils` |

Tested with pymobiledevice3 9.33.1 on an iPhone 15 Pro Max running iOS 27.2, from Pop!_OS and Ubuntu.

---

## One-time setup (USB)

Plug the iPhone in, unlock it, and tap **Trust** when it asks.

**1. Pair**

```bash
pymobiledevice3 lockdown pair
```

If that fails with `BadDevError` (common on Linux), use libimobiledevice instead. pymobiledevice3
reads its pair record through usbmuxd:

```bash
idevicepair pair && idevicepair validate
```

If the iPhone isn't detected after replugging (`idevice_id -l` is empty), restart usbmuxd:
`sudo systemctl restart usbmuxd`.

**2. Allow Wi-Fi connections**

```bash
pymobiledevice3 lockdown wifi-connections --state on
```

**3. Enable Developer Mode** (required to launch apps with debug settings)

```bash
pymobiledevice3 amfi enable-developer-mode    # works only if the iPhone has NO passcode
pymobiledevice3 amfi reveal-developer-mode    # otherwise: reveal the toggle, then...
```

…on the iPhone, go to **Settings → Privacy & Security → Developer Mode → On → Restart**, then tap
**Turn On** after the reboot. Check it with `pymobiledevice3 amfi developer-mode-status`.

**4. Create the Wi-Fi pairing record**, still over USB, with no prompt on the phone:

```bash
pymobiledevice3 lockdown remotepairing --pair
```

This writes `~/.pymobiledevice3/remote_<UDID>.plist`. After this, unplug; you won't need the cable again.

**5. Configure**

```bash
git clone https://github.com/M-Shazim/ios-metal-hud && cd ios-metal-hud
cp config.example.env config.env
pymobiledevice3 usbmux list            # copy the UniqueDeviceID into UDID=
```

> You do **not** need to turn off *Private Wi-Fi Address*. Discovery works with it on.

---

## Usage

Keep the iPhone unlocked and on the same Wi-Fi.

```bash
./hud inmost                         # a game with no anti-cheat: a safe first test
./hud pubg                           # built-in names: pubg codm genshin roblox coc inmost
./hud com.miHoYo.GenshinImpact       # any bundle id
./hud apps                           # list installed apps (cached for a day)
./hud refresh                        # re-read the app list from the iPhone
```

```
$ ./hud pubg
✓ launched com.tencent.ig pid 835
```

The HUD stays until the game is closed. Launching from the home screen opens the game without it.

---

## How it works

`hud.py` uses pymobiledevice3 to:

1. find the iPhone on the Wi-Fi via Bonjour (`_remotepairing._tcp`), or connect to the IP you give it;
2. open the RemotePairing tunnel using pymobiledevice3's **userspace network stack**, so no
   TUN device, no sudo and no `tunneld` are needed;
3. ask the developer service to launch the bundle with `MTL_HUD_ENABLED=1`, then exit.

`hud` is a small wrapper around it: it holds the config, short names, the app-list cache and a
retry, and validates input so it can safely serve as an SSH forced command.

---

## Troubleshooting

| Symptom | Fix |
|--|--|
| `BadDevError` during `lockdown pair` | Use `idevicepair pair` (step 1) |
| `Cannot enable developer-mode when passcode is set` | Use `amfi reveal-developer-mode` and the Settings toggle (step 3) |
| iPhone not detected over USB after replugging | `sudo systemctl restart usbmuxd` |
| `iPhone not found on Wi-Fi` | Unlock it, check that both are on the same network, and that step 4 was done |
| `NO_CIPHERS_AVAILABLE` | Use Python 3.13+ |
| `ConnectionTerminatedError` from another machine | Set `HUD_PAIR_HOST` (see the remote guide) |
| First launch hangs | `hud` retries once automatically; the first connection after idle can stall |
| No HUD in a game | The app may not render with Metal, or may disable the HUD |

---

## FAQ

**Can it get me banned?**
Unknown. Use it at your own risk. Nothing in the game is modified, and the HUD is Apple's own
overlay. But a game's anti-cheat *could* notice that Developer Mode is on or that the game was
started through the developer service. Try it on a spare or guest account before using it on your
main account in online or ranked play.

**Does it need a computer?**
Something has to start the launch: a machine on the same Wi-Fi, or any server once the iPhone is on
Tailscale. iOS doesn't let an app launch other apps with debug settings.

**Can I turn Developer Mode off afterwards?**
Yes, in Settings → Privacy & Security. Launches stop working until you turn it back on.
