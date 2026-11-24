# Remote launching and one-tap iPhone Shortcuts

Run `hud` on a cloud server and start games from the iPhone itself:

```
iPhone Shortcut ──SSH──▶ server: hud pubg ──Tailscale──▶ iPhone: game opens with the HUD
```

There is nothing to keep running at home, and it works from anywhere while Tailscale is on.
A launch takes about 10–15 s from a distant server, because of many round trips.

Do the [one-time USB setup](../README.md#one-time-setup-usb) on your own computer first.

---

## 1. Tailscale on both ends

- **iPhone:** install Tailscale from the App Store, sign in and connect.
- **Server:** [install Tailscale](https://tailscale.com/download/linux) and `sudo tailscale up` with the same account.
- Note the iPhone's address: `tailscale status` → `100.x.y.z  iphone-...`.

iOS accepts the developer connection over the Tailscale VPN, so Bonjour isn't needed; `hud` dials the IP directly.

## 2. Install on the server

```bash
pipx install --python python3.13 pymobiledevice3
git clone https://github.com/M-Shazim/ios-metal-hud ~/ios-hud
```

Copy both pair records from the computer you paired with, and keep them private:

```bash
scp ~/.pymobiledevice3/{<UDID>.plist,remote_<UDID>.plist} server:.pymobiledevice3/
ssh server 'chmod 700 ~/.pymobiledevice3 && chmod 600 ~/.pymobiledevice3/*'
```

Then set up `~/ios-hud/config.env` on the server:

```bash
UDID="<UDID>"
IPHONE_IP="100.x.y.z"          # the iPhone's Tailscale IP
HUD_PAIR_HOST="my-laptop"      # `hostname` of the computer you PAIRED from
```

> **Why `HUD_PAIR_HOST`:** pymobiledevice3 derives the host ID from the machine's hostname, and
> the iPhone only accepts the host ID it was paired with. Without this, a copied pair record fails
> with `ConnectionTerminatedError`.

Test it with something that doesn't launch a game: `~/ios-hud/hud refresh` should print your apps.

## 3. A locked SSH key for the iPhone

1. In **Shortcuts**, create a shortcut and add **Run Script Over SSH**.
2. Set **Authentication** to **SSH Key**, tap **ed25519 Key**, then **Share Public Key**, and copy it.
3. On the server, add it to `~/.ssh/authorized_keys` **locked to `hud`**:

```
restrict,command="/home/ubuntu/ios-hud/hud" ssh-ed25519 AAAA... iphone-shortcut
```

`restrict` blocks shells, port forwarding and PTYs. `command=` forces every connection with this
key to run `hud`, which receives what the Shortcut sent and accepts only game names and bundle ids.
If the key were taken from the phone, all it could do is launch games.

## 4. Shortcuts

Use the same SSH settings in every action: Host = the server's Tailscale IP (or its public IP),
Port 22, the user you added the key for, and Authentication **SSH Key**.

### One tap per game

1. **Run Script Over SSH**, Script: `pubg` (or any bundle id)
2. **Show Notification**: *Shell Script Result*

Add it to the home screen. One tap, and the game opens with the HUD.

### Game picker (every installed app)

1. **Run Script Over SSH**, Script: `apps`
2. **Split Text**: *Shell Script Result*, split by **New Lines**
3. **Choose from List**: *Split Text*
4. **Run Script Over SSH**, Script: the **Chosen Item** variable (blue bubble, nothing typed)
5. **Show Notification**: the *Shell Script Result* of step 4

New apps appear within a day; a Shortcut that sends `refresh` updates the list at once.

### If something goes wrong

The server logs every request it receives to `~/ios-hud/hud.log`:

| Log line | Meaning |
|--|--|
| `''` | The Script field was empty: step 4 is missing the Chosen Item variable |
| `apps` then nothing | The list didn't come back; check that Tailscale is on and the iPhone is unlocked |
| `PUBG\ MOBILE\ —\ com.tencent.ig` | Correct request; if nothing launched, run `hud refresh` on the server |

---

## Security notes

- The pair records give whoever holds them developer access to the iPhone (launching and inspecting
  apps) while it's reachable. Keep them `chmod 600`, on a server only you can log in to.
- To revoke access: delete the records on the server, or turn Developer Mode off on the iPhone.
