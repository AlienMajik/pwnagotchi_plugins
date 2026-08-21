# Pwnagotchi Plugins Collection

**Author:** AlienMajik  

### Support & Contributions
Feel free to open issues or pull requests to improve this plugin or suggest new features. Enjoy leveling up your Pwnagotchi!

## Table of Contents
1. [Age Plugin](#age-plugin)
2. [ADSBsniffer Plugin](#adsbsniffer-plugin)
3. [Neurolyzer Plugin](#neurolyzer-plugin)
4. [ProbeNpwn Plugin](#probenpwn-plugin)
5. [SnoopR Plugin](#snoopr-plugin)
6. [SkyHigh Plugin](#skyhigh-plugin)
7. [MadHatter Plugin](#madhatter-plugin)
8. [TheyLive Plugin](#theylive-plugin)

---

# Age Plugin

**Version 5.2.0** · MIT · by AlienMajik

A narrative-driven progression plugin for Pwnagotchi. It tracks how long your unit has
lived, how hard it's been working, and what it has captured — then wraps all of it in
titles, lore, cheeky quotes, random events and a prestige/rebirth cycle.

Tested against **Jayofelony Pwnagotchi 2.9.5.8**. Works on 2.9.3 and later; see
[Compatibility](#compatibility) if you're upgrading from an older image.

---

## What it tracks

### Age

Counts the epochs your Pwnagotchi has lived through, and awards a title at each
threshold — "Baby Steps" at 100, "Neon Spawn" at 1,000, "Data Raider" at 10,000, all the
way to "Intergalactic" at 111,111. After a rebirth every title gains a `Reborn` prefix.

### Strength

Reflects training effort. On images with the AI removed (which is all current Jayofelony
releases) strength accrues passively at `passive_train_rate` per epoch — 0.1 by default,
so one strength point per ten epochs. If a fork *does* emit AI training steps, the plugin
switches to counting real steps automatically, and falls back to passive accrual if those
steps stop arriving.

Titles run from "Sparring Novice" (100) through "Deauth King" (2,000) to "Kuato" (11,111).

### Network Points

Earned per handshake, scaled by encryption strength and your prestige multiplier:

| Encryption | Base points |
|---|---|
| WPA3 | 10 |
| WPA2 | 5 |
| WPA / WEP | 2 |
| Open / unknown | 1 |

Bettercap reports encryption as strings like `WPA2 CCMP PSK`, so the plugin normalizes
whatever it gets into one of those families before scoring.

Points **decay** during long stretches of inactivity, and there's a **streak bonus** of
+20% once you've captured five in a row without a decay event.

### Personality

Three traits grow from how you actually play:

| Trait | Grows when |
|---|---|
| Aggro | +3 per handshake (`aggro_per_handshake`) |
| Scholar | +1 every 10 epochs |
| Stealth | +1 per 5 consecutive quiet epochs (`stealth_quiet_epochs`) |

The dominant trait can be shown on screen with `show_personality`.

---

## Prestige and rebirth

Max out both the age and strength title tables and a rebirth becomes available. Taking it
resets epochs, strength, points, streaks, personality and the current handshake count, and
grants a permanent **+10% point multiplier per prestige level** (1.1×, 1.2×, …), tunable
with `prestige_bonus`.

Your **lifetime** handshake total and your unlocked achievements survive rebirth.

By default rebirth triggers automatically on the next epoch. Set `auto_rebirth = false`
to hold it, then spend it from the web UI when you're ready.

---

## Random events

Every `event_interval` epochs (100 by default) there's a `random_event_chance` roll for one
of:

| Event | Effect |
|---|---|
| Lucky Break | Double points, next 5 handshakes |
| Overclock | Triple points, next 3 handshakes |
| Signal Noise | Half points, next handshake |
| Hacker's Block | Zero points, next 3 handshakes |
| Windfall | +50 points instantly (scaled by prestige) |
| Time Warp | Strength grows 2× for 100 epochs |
| Ghost | Swaps your aggro and stealth scores |

Events persist across reboots and expire cleanly.

---

## Achievements

Milestones fire off your **lifetime** handshake count, so they aren't lost to a rebirth:
First Blood (1), Double Digits (10), Century Mark (100), Thousand Claps (1,000) and
Legend (5,000) — each worth +50 points.

Two are hidden: **Night Owl** (10 handshakes between 2am and 4am) and **Crypto King**
(capture WPA3, WPA2, WPA and WEP).

---

## Installation

Copy `age.py` into the custom plugins directory:

```bash
sudo scp age.py pi@<pwnagotchi_ip>:/tmp/
sudo mv /tmp/age.py /etc/pwnagotchi/custom-plugins/
```

Then add the config below to `/etc/pwnagotchi/config.toml` and restart:

```bash
sudo systemctl restart pwnagotchi
```

### Configuration

Bracketed form, recommended:

```toml
[main.plugins.age]
enabled = true

# UI positions. Keep every y below your panel height — a Waveshare 2.13 is
# only 122px tall, and anything at or past that gets clamped with a warning.
age_x_coord = 101
age_y_coord = 80
strength_x_coord = 160
strength_y_coord = 80
points_x_coord = 10
points_y_coord = 60
progress_x_coord = 10
progress_y_coord = 100
personality_x_coord = 10
personality_y_coord = 20
age_status_x_coord = 10
age_status_y_coord = 110

# Which elements to draw
show_personality = false
show_points = true
show_progress = true
show_status = true

# Decay
decay_interval = 50
decay_amount = 5

# Events and prestige
random_event_chance = 0.05
event_interval = 100
prestige_bonus = 0.1
auto_rebirth = true
```

Flat `main.plugins.age.<key> = <value>` form works identically if you prefer it.

### All options

| Option | Default | What it does |
|---|---|---|
| `decay_interval` | 50 | Epochs of inactivity before points decay |
| `decay_amount` | 10 | Points lost per decay interval |
| `random_event_chance` | 0.05 | Probability of an event at each interval |
| `event_interval` | 100 | Epochs between event rolls |
| `prestige_bonus` | 0.1 | Multiplier gained per prestige level |
| `auto_rebirth` | true | Spend a pending rebirth automatically |
| `passive_train_rate` | 0.1 | Strength gained per epoch without AI |
| `ai_idle_epochs` | 20 | Epochs without a training step before passive accrual resumes |
| `stealth_quiet_epochs` | 5 | Quiet epochs per stealth point |
| `aggro_per_handshake` | 3 | Aggro gained per capture |
| `repeat_ap_penalty` | false | Diminishing returns for re-capturing the same BSSID |
| `takeover_status` | true | Briefly borrow the main status line for new messages |
| `max_status_len` | 40 | Characters before a message is truncated |
| `msg_hold` | 3 | UI refreshes a queued message stays up |
| `save_interval` | 60 | Seconds between disk writes |
| `log_max_bytes` | 524288 | Rotate the points log past this size |
| `show_personality` | false | Draw the dominant trait |
| `show_points` / `show_progress` / `show_status` | true | Draw those elements |
| `data_path` | `/root/age_strength.json` | Stats file |
| `log_path` | `/root/network_points.log` | Points log |
| `handshake_dir` | auto | Override the handshake directory |
| `age_titles` / `strength_titles` | built-in | Custom threshold → title maps |
| `points_map` | built-in | Custom per-encryption scores (merges with defaults) |

Bad values are logged and replaced with the default rather than crashing the plugin, and a
partial `points_map` merges with the built-in one instead of wiping the entries it didn't
mention.

---

## Web UI

Live stats at `http://<pwnagotchi_ip>:8080/plugins/age/` — titles, points, prestige,
lifetime handshakes, streak, personality breakdown, encryption families seen and unlocked
achievements. When `auto_rebirth = false` and a rebirth is pending, a link there triggers
it.

---

## Compatibility

| Image | Status |
|---|---|
| Jayofelony 2.9.5.5 – 2.9.5.8 | Supported |
| Jayofelony 2.9.3 – 2.9.5.4 | Supported |
| Older / evilsocket | Should work; handshake paths and faces are probed defensively |

Two things changed in the Jayofelony line that this plugin now accounts for:

- **Handshakes are `.pcapng` as of the 2.9.5.5+ images.** The initial scan counts both
  `.pcapng` and `.pcap`. If you're carrying over old captures, note that Jayofelony's own
  advice is to rename `.pcap` to `.pcapng` so the rest of the tooling still sees them.
- **The handshake directory moved to `/home/pi/handshakes`** in 2.9.3. That path is probed
  first, then `/root/handshakes` for older images. Override with `handshake_dir` if yours
  lives elsewhere.

Because pcapng files are appended to rather than recreated, a single network can raise
`on_handshake` more than once. If one router at home ends up dominating your score,
`repeat_ap_penalty = true` applies diminishing returns per BSSID.

The AI is gone from current images, so strength accrues passively — that's expected, not a
fault. Nothing here depends on the AI being present.

---

## Files

**`/root/age_strength.json`** — all persistent state: epochs, strength, points, current and
lifetime handshakes, prestige, personality, achievements, active events and event
progress. Written atomically (temp file, fsync, rename) at most once per `save_interval`,
so a power cut can't leave you with a truncated file. If it ever is unreadable it's moved
aside to `.corrupt` rather than silently zeroing your progress.

**`/root/network_points.log`** — one CSV line per handshake: timestamp, quoted ESSID,
encryption family, points awarded. Rotates to `.1` past `log_max_bytes`.

---

## Upgrading from v4.0.0

Drop in the new `age.py` and restart. Your existing `age_strength.json` is read as-is and
new fields are filled with sane defaults.

Expect your **points total to change on first run**. v4 applied the prestige multiplier
twice (once when earning, once when displaying) and mis-rendered any value under 1,000 —
100 points showed as `1`. The number you see now is the correct one.

Two balance changes worth knowing about: stealth no longer gains a point every single
quiet epoch, so the dominant trait will stop defaulting to Stealth; and handshake
milestones now key off your lifetime total, so several may unlock at once the first time
you capture something.
---

# ADSBsniffer Plugin

A plugin that captures ADS-B data from aircraft using RTL-SDR and logs it.

## Requirements
A RTL-SDR Dongle is required to run this plugin.

## Setup Instructions

### 1. Connect the RTL-SDR Dongle
First, connect your RTL-SDR dongle to one of the USB ports on your Raspberry Pi (the hardware running Pwnagotchi). Ensure the dongle is properly seated and secure.

### 2. Access the Pwnagotchi Terminal
To configure the RTL-SDR and test rtl_adsb, you'll need to access the terminal on your Pwnagotchi. You can do this in several ways:

- **Directly via Keyboard and Monitor:** If you have a monitor and keyboard connected to your Raspberry Pi, you can access the terminal directly.
- **SSH:** If your Pwnagotchi is connected to your network, you can SSH into it. The default username is usually pi, and the password is raspberry, unless you've changed it. The IP address can be found on the Pwnagotchi screen or through your router's DHCP client list.

### 3. Install RTL-SDR Drivers and Utilities
Once you're in the terminal, you'll likely need to install the RTL-SDR drivers and the rtl_adsb utility. Pwnagotchi is based on Raspbian, so you can use apt-get to install these packages. Run the following commands:
     
```bash
sudo apt-get install rtl-sdr
```

### 4. Verify RTL-SDR Dongle Recognition
After installation, verify that the RTL-SDR dongle is recognized by the system:

```bash
rtl_test
```

This command checks if the RTL-SDR dongle is properly recognized. You should see output indicating the detection of the dongle. If there are errors or the dongle is not detected, ensure it's properly connected or try reconnecting it.

### 5. Run rtl_adsb
Now, try running rtl_adsb to see if you can receive ADS-B signals:

```bash
rtl_adsb
```

This command starts the ADS-B reception. If your RTL-SDR is set up correctly and there are aircraft in range, you should see ADS-B messages appearing in the terminal.

## Installation

Add `adsbsniffer.py` to `/usr/local/share/pwnagotchi/installed-plugins` and `/usr/local/share/pwnagotchi/available-plugins`

In `/etc/pwnagotchi/config.toml` file add: 

```toml
main.plugins.adsbsniffer.enabled = true
main.plugins.adsbsniffer.timer = 60
main.plugins.adsbsniffer.aircraft_file = "/root/handshakes/adsb_aircraft.json"
main.plugins.adsbsniffer.adsb_x_coord = 120
main.plugins.adsbsniffer.adsb_y_coord = 50
```

## Disclaimer for ADSBSniffer Plugin

The ADSBSniffer plugin ("the Plugin") is provided for educational and research purposes only. By using the Plugin, you agree to use it in a manner that is ethical, legal, and in compliance with all applicable local, state, federal, and international laws and regulations. The creators, contributors, and distributors of the Plugin are not responsible for any misuse, illegal activity, or damages that may arise from the use of the Plugin.

The Plugin is designed to capture ADS-B data from aircraft using RTL-SDR technology. It is important to understand that interfacing with ADS-B signals, aircraft communications, and related technologies may be regulated by governmental agencies. Users are solely responsible for ensuring their use of the Plugin complies with all relevant aviation and communications regulations.

The information provided by the Plugin is not guaranteed to be accurate, complete, or up-to-date. The Plugin should not be used for navigation, air traffic control, or any other activities where the accuracy and completeness of the information are critical.

The use of the Plugin to interfere with, disrupt, or intercept aircraft communications is strictly prohibited. Respect privacy and safety laws and regulations at all times when using the Plugin.

The creators of the Plugin make no warranties, express or implied, about the suitability, reliability, availability, or accuracy of the information, products, services, or related graphics contained within the Plugin for any purpose. Any reliance you place on such information is therefore strictly at your own risk.

By using the Plugin, you agree to indemnify and hold harmless the creators, contributors, and distributors of the Plugin from and against any and all claims, liabilities, damages, losses, or expenses, including legal fees and costs, arising out of or in any way connected with your access to or use of the Plugin.

This disclaimer is subject to changes and updates. Users are advised to review it periodically.

---

# Neurolyzer Plugin

**Version:** 2.0.0

## Overview
The Neurolyzer plugin has evolved into a powerful tool for enhancing the stealth and privacy of your Pwnagotchi. Now at version 2.0.0, it goes beyond simple MAC address randomization to provide a comprehensive suite of features that minimize your device's detectability by network monitoring systems, Wireless Intrusion Detection/Prevention Systems (WIDS/WIPS), and other security measures. By reducing its digital footprint while scanning networks, Neurolyzer ensures your Pwnagotchi operates discreetly and efficiently. This update introduces non-intrusive hardware discovery, dynamic monitor interface preservation and recreation, prioritized MAC change methods with detailed error logging, explicit Nexmon verification via nexutil and dmesg for Raspberry Pi 5 compatibility, integrated deauthentication via Bettercap or agent, enhanced command execution with exit codes, case-insensitive WIDS detection, and refined channel hopping tied to stealth levels—along with adaptive stealth levels based on environmental factors (e.g., number of nearby APs), SSID whitelisting to avoid targeting trusted networks, deauthentication throttling for balanced aggression, and an expanded list of realistic OUIs for better blending.

## Key Features and Improvements

### 1. Advanced WIDS/WIPS Evasion

- **What's New:** A sophisticated system to detect and evade WIDS/WIPS.
- **How It Works:** Scans for known WIDS/WIPS SSIDs (e.g., "wids-guardian", "airdefense") with case-insensitive matching and triggers evasion tactics like MAC address rotation, channel hopping, TX power adjustments, traffic throttling, and random delays.
- **What's Better:** Proactively avoids detection in secured environments with more resilient and unpredictable evasion measures, making your Pwnagotchi stealthier than ever.

### 2. Hardware-Aware Adaptive Countermeasures
- **What's New:** Adapts to your device's hardware capabilities, now with non-intrusive detection for Broadcom chipsets (e.g., Raspberry Pi 5's CYW43455) and precise Nexmon verification requiring both dmesg logs and the nexutil binary.
- **How It Works:** Detects support for TX power control, monitor mode, MAC spoofing (based on macchanger presence), and packet injection at startup without invasive tests, tailoring operations accordingly. If Nexmon is confirmed on Broadcom hardware, enables monitor mode, 5GHz channels, and injection features; falls back to passive mode otherwise.
- **What's Better:** Ensures compatibility and stability across diverse Pwnagotchi setups, including Raspberry Pi 5 and the jayofelony 2.9.5.4 framework, avoiding errors from unsupported features, reducing boot-time disruptions, and enabling advanced capabilities with accurate patches detection.

### 3. Atomic MAC Rotation with Locking Mechanism
- **What's Improved:** MAC changes are now atomic, using an exclusive lock, with prioritized methods (macchanger first, then ip link, then ifconfig) and detailed error collection for logging.
- **How It Works:** A lock file prevents conflicts during MAC updates; dynamically detects and preserves the monitor interface (bringing it down/up instead of deleting/recreating), ensuring smooth execution across methods.
- **What's Better:** Enhances reliability, especially on resource-constrained devices or with multiple plugins, by minimizing interruptions to Pwnagotchi's scanning and providing better debugging through method-specific errors.

### 4. Realistic MAC Address Generation with Common OUIs
- **What's Improved:** Generates MAC addresses using OUIs from popular manufacturers (e.g., Raspberry Pi, Apple, Cisco).
- **How It Works:** In noided mode, it combines a real OUI with random bytes to mimic legitimate devices.
- **What's Better:** Blends into network traffic, reducing suspicion compared to fully random MACs in earlier versions.

### 5. Flexible Operation Modes
- **What's New:** Three modes: normal, stealth, and noided.
- **How It Works:**
  - **normal:** No randomization or evasion.
  - **stealth:** Periodic MAC randomization with flexible intervals (30 minutes to 2 hours).
  - **noided:** Full evasion suite with MAC rotation, channel hopping, TX power tweaks, and traffic throttling.
- **What's Better:** Offers customizable stealth levels, unlike the simpler normal and stealth modes in prior versions.

### 6. Robust Command Execution with Retries and Fallbacks
- **What's Improved:** Enhanced reliability for system commands, now always using sudo, logging exit codes on failures, and providing targeted fallbacks (e.g., iwconfig for iw txpower commands).
- **How It Works:** Retries failed commands with timeouts and handles specific errors like "device busy," using alternatives where appropriate.
- **What's Better:** Increases stability across varied setups, fixing issues from inconsistent command execution and improving debugging with precise failure details.

### 7. Traffic Throttling for Stealth
- **What's New:** Limits network traffic in noided mode.
- **How It Works:** Uses tc to shape packet rates with netem for realistic delays and jitter, falling back to pfifo_fast limits, mimicking normal activity.
- **What's Better:** Avoids triggering rate-based WIDS/WIPS alarms, a leap beyond basic MAC randomization, with more natural traffic patterns.

### 8. Enhanced UI Integration
- **What's Improved:** Displays detailed status on the Pwnagotchi UI.
- **How It Works:** Shows mode, next MAC change time, TX power, channel, and stealth level. The positions for all these labels are fully customizable in `config.toml`.
- **What's Better:** Offers real-time monitoring with error-resilient updates (try-except with tracebacks), improving on the basic UI updates of past releases.

### 9. Improved Error Handling and Logging
- **What's Improved:** Better logging and adaptive error responses throughout, including tracebacks in UI updates and wifi hooks.
- **How It Works:** Logs detailed errors/warnings, catches exceptions per operation, and adjusts to hardware limits with debug messages for each sub-action.
- **What's Better:** Easier troubleshooting and more reliable operation than before, preventing full crashes from isolated failures.

### 10. Safe Channel Hopping
- **What's New:** Implements safe, regular channel switching tied to stealth levels.
- **How It Works:** Uses safe channels (e.g., 1, 6, 11) for higher stealth or all supported/detected ones for aggressive modes, with fallbacks if detection fails.
- **What's Better:** Reduces detection risk by avoiding static channel use while optimizing for environment-specific efficiency.

### 11. TX Power Adjustment
- **What's New:** Randomizes transmission power in noided mode.
- **How It Works:** Adjusts TX power within hardware limits using iw (with dBm suffix for compatibility) or iwconfig.
- **What's Better:** Mimics normal device behavior, enhancing stealth over static signal strength, with better support for varied drivers.

### 12. Comprehensive Cleanup on Unload
- **What's Improved:** Restores default settings when disabled.
- **How It Works:** Resets traffic shaping and releases locks, preserving monitor mode stability.
- **What's Better:** Leaves your device stable post-use, unlike earlier versions with minimal cleanup.

### 13. Adaptive Stealth Levels
- **What's New:** Dynamically adjusts stealth based on environment.
- **How It Works:** Levels 1-3: Aggressive (high TX/deauth in quiet areas) to passive (low TX/deauth in crowds), adapting MAC intervals, TX power, channel hops, and deauth throttle based on AP count, with error handling for adaptation.
- **What's Better:** Balances handshake farming with evasion, making operations smarter and less detectable.

### 14. SSID Whitelisting and Deauth Throttling
- **What's New:** Avoids targeting trusted networks and controls deauth rate with integrated execution.
- **How It Works:** Filters whitelisted SSIDs from deauth targets; throttles deauth (20-80% based on stealth, min 1 target) if packet injection supported (e.g., via Nexmon), using Pwnagotchi agent or Bettercap subprocess.
- **What's Better:** Prevents accidental disruption of home/office networks while reducing WIPS triggers from excessive deauths, with efficient integration for minimal overhead.

### 15. Nexmon Integration for Raspberry Pi 5
- **What's New:** Automatic detection and enablement for Broadcom chipsets with stricter verification.
- **How It Works:** Checks for Nexmon patches via dmesg and nexutil; enables monitor mode, packet injection (where supported), and 5GHz channels on compatible hardware like Pi 5's bcm43455c0.
- **What's Better:** Overcomes native limitations on Pi 5 for full evasion features, with fallback to passive mode if unpatched and reduced false positives.

### 16. Monitor Interface Management
- **What's New:** Dynamic detection, preservation, and recreation of monitor interfaces.
- **How It Works:** Automatically detects monitor iface (e.g., mon* or wlan0mon) linked to the wifi phy; ensures it's up or recreates with retries if missing, configurable via options.
- **What's Better:** Prevents scanning interruptions by avoiding unnecessary deletions, improving compatibility with Pwnagotchi's workflow on Pi 5 and other setups.

## Legacy Improvements Retained and Enhanced
- **Initial MAC Randomization:** Randomizes the MAC address on load for immediate privacy, now deferred to wifi updates for better timing.
- **Monitor Mode Handling:** Preserves monitor interfaces during MAC changes (down/up instead of delete/recreate), enhanced with dynamic detection and recreation for stability.
- **Time-Dependent Randomization:** Dynamically calculates MAC change schedules for unpredictability, now adaptive to stealth level and checked in wifi updates.
## Other Features
- **Varied Operational Modes:** Choose normal, stealth, or noided to match your needs.
- **Wi-Fi Interface Customization:** Supports custom interface names for flexibility, including optional monitor_iface.
- **Comprehensive Logging:** Tracks events and errors for easy monitoring, with added debug for sub-actions and tracebacks.
- **Seamless Activation/Deactivation:** Auto-starts when enabled, ensuring smooth transitions with deferred initial configs.

## Installation Instructions

### Requirements
**macchanger:** Install with:
```bash
sudo apt install macchanger
```
Select "No" when asked about changing the MAC on startup.

### Steps:
1. **Clone the Plugin Repository:**
   Add to `/etc/pwnagotchi/config.toml`:
   ```toml
   main.confd = "/etc/pwnagotchi/conf.d/"
   main.custom_plugin_repos = [
   "https://github.com/jayofelony/pwnagotchi-torch-plugins/archive/master.zip",
   "https://github.com/Sniffleupagus/pwnagotchi_plugins/archive/master.zip",
   "https://github.com/NeonLightning/pwny/archive/master.zip",
   "https://github.com/marbasec/UPSLite_Plugin_1_3/archive/master.zip",
   "https://github.com/wpa-2/Pwnagotchi-Plugins/archive/master.zip",
   "https://github.com/cyberartemio/wardriver-pwnagotchi-plugin/archive/main.zip",
   "https://github.com/AlienMajik/pwnagotchi_plugins/archive/refs/heads/main.zip"
   ]
   main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins/"
   ```

2. **Update and install:**
   ```bash
   sudo pwnagotchi plugins update
   sudo pwnagotchi plugins install neurolyzer
   ```

### Manual Installation (Alternative)
1. **Clone the repo:**
   ```bash
   sudo git clone https://github.com/AlienMajik/pwnagotchi_plugins.git
   cd pwnagotchi_plugins
   ```
2. **Copy and make executable:**
   ```bash
   sudo cp neurolyzer.py /usr/local/share/pwnagotchi/custom-plugins/
   sudo chmod +x /usr/local/share/pwnagotchi/custom-plugins/neurolyzer.py
   ```
3. **Configure the Plugin:**
   Edit `/etc/pwnagotchi/config.toml`:
   ```toml
    main.plugins.neurolyzer.enabled = true
    main.plugins.neurolyzer.wifi_interface = "wlan0" # Your wireless adapter
    main.plugins.neurolyzer.monitor_iface = "wlan0mon" # Optional: Your monitor interface
    main.plugins.neurolyzer.operation_mode = "noided" # 'normal', 'stealth', or 'noided'
    main.plugins.neurolyzer.mac_change_interval = 3600 # Seconds
    # -- UI Label Positions --
    main.plugins.neurolyzer.mode_label_x = 0
    main.plugins.neurolyzer.mode_label_y = 35
    main.plugins.neurolyzer.next_mac_change_label_x = 0
    main.plugins.neurolyzer.next_mac_change_label_y = 45
    main.plugins.neurolyzer.tx_power_label_x = 0
    main.plugins.neurolyzer.tx_power_label_y = 55
    main.plugins.neurolyzer.channel_label_x = 0
    main.plugins.neurolyzer.channel_label_y = 65
    main.plugins.neurolyzer.stealth_label_x = 0
    main.plugins.neurolyzer.stealth_label_y = 75
    # ------------------------
    main.plugins.neurolyzer.stealth_level = 2 # Optional: Initial stealth level (1=aggressive, 2=medium, 3=passive); still adapts dynamically

   Confi.toml bracketed format for Jayofelony image 2.9.5.4:
   
   [main.plugins.neurolyzer]
   enabled = false
   wifi_interface = "wlan0"
   monitor_iface = "wlan0mon"
   operation_mode = "noided"
   mac_change_interval = 1111
   mode_label_x = 101
   mode_label_y = 50
   next_mac_change_label_x = 101
   next_mac_change_label_y = 60
   stealth_label_x = 0
   stealth_label_y = 75
   
   ```
   For maximum stealth:
   ```toml
   personality.advertise = false
   ```
4. **Restart Pwnagotchi**
   Run:
   ```bash
   sudo systemctl restart pwnagotchi
   ```
5. **Verify the Plugin**
   Check logs:
   ```
   [INFO] [Neurolyzer] Loaded in noided mode.
   [INFO] [Neurolyzer] MAC changed to xx:xx:xx:xx:xx:xx (monitor preserved)
   ```
## Known Issues
- **Wi-Fi Adapter Compatibility:** Works best with external adapters. Optimized for Raspberry Pi 5's built-in Broadcom CYW43455 chip with Nexmon; compatible with other stock Wi-Fi chipset Pi models (e.g., Zero W, 3B) via fallbacks, but injection requires patches. Please share feedback on non-Pi5 models!

## Summary
Neurolyzer 2.0.0 elevates Pwnagotchi's stealth and privacy with advanced WIDS/WIPS evasion, hardware-aware operations (including precise Pi 5 Nexmon support), realistic MAC generation, adaptive modes, and new features like monitor preservation, integrated deauth, non-intrusive discovery, and enhanced logging. Compared to 1.6.0, it offers smarter environmental adaptation, better reliability on modern hardware and jayofelony frameworks, deeper evasion (throttled deauth, 5GHz hopping with verification), and enhanced usability (UI stealth display, error-resilient hooks). Whether you're testing security or keeping a low profile, Neurolyzer 2.0.0 is a significant upgrade—more versatile, intelligent, and robust than ever.

## Neurolyzer Plugin Disclaimer
Please read this disclaimer carefully before using the Neurolyzer plugin ("Plugin") developed for the Pwnagotchi platform.
- **General Use:** The Neurolyzer Plugin is intended for educational and research purposes only. It is designed to enhance the privacy and stealth capabilities of the Pwnagotchi device during ethical hacking and network exploration activities. The user is solely responsible for ensuring that all activities conducted with the Plugin adhere to local, state, national, and international laws and regulations.
- **No Illegal Use:** The Plugin must not be used for illegal or unauthorized network access or data collection. The user must have explicit permission from the network owner before engaging in any activities that affect network operations or security.
- **Liability:** The developers of the Neurolyzer Plugin, the Pwnagotchi project, and any associated parties will not be liable for any misuse of the Plugin or for any direct, indirect, incidental, special, exemplary, or consequential damages (including, but not limited to, procurement of substitute goods or services; loss of use, data, or profits; or business interruption) however caused and on any theory of liability, whether in contract, strict liability, or tort (including negligence or otherwise) arising in any way out of the use of this Plugin, even if advised of the possibility of such damage.
- **Network Impact:** Users should be aware that randomizing MAC addresses and altering device behavior can impact network operations and other users. It is the user's responsibility to ensure that their activities do not disrupt or degrade network performance and security.
- **Accuracy and Reliability:** While efforts have been made to ensure the reliability and functionality of the Neurolyzer Plugin, the developers make no representations or warranties of any kind, express or implied, about the completeness, accuracy, reliability, suitability, or availability with respect to the Plugin or the information, products, services, or related graphics contained within the Plugin for any purpose. Any reliance placed on such information is therefore strictly at the user's own risk.
- **Modification and Discontinuation:** The developers reserve the right to modify, update, or discontinue the Plugin at any time without notice. Users are encouraged to periodically check for updates to ensure optimal performance and compliance with new regulations.
By using the Neurolyzer Plugin, you acknowledge and agree to this disclaimer. If you do not agree with these terms, you are advised not to use the Plugin.
---

# ProbeNpwn Plugin

**Version:** 3.3.0

### Recent Update (v3.3.0)

- **Quiet Association Attacks (No Deauth Required)**
  Added full suite of stealthy PMKID-focused attacks: PMKID association request, auth frame harvest (Open/Shared/FT), reassociation PMKID, RSN probe (with WPA3/SAE IE), and CSA probe — captures handshakes/PMKIDs without any deauth frames.
- **WPS Attack Engine with PIN Capture**
  Full integration of bully + reaver: real-time stdout parsing with regex extraction of 8-digit PINs, auto-saves captured PINs (with BSSID, tool, timestamp) to `/root/handshakespin/`.
- **New Config Options**
  `enable_pmkid_attack`, `enable_auth_harvest`, `enable_reassociation`, `enable_rsn_probe`, `pin_save_path`, plus toggles for every advanced attack (`enable_wpa3_downgrade`, `enable_ft_handshake`, `enable_tdls`, `enable_mesh`, `enable_wps`, `enable_eapol_start`, `enable_eapol_logoff`, `enable_disassociation`, `enable_null_data`, `enable_csa`, `enable_beacon_flood`, `enable_probe_response_flood`, `enable_auth_flood`, `enable_assoc_flood`, `enable_ps_poll`, `enable_cf_end`, `enable_mimo`), `mac_randomization`, `dry_run`, `low_battery_threshold`, `high_cpu_threshold`, `upload_url`, `upload_interval`, `auto_install_scapy`, and many more.
- **Improved External Tool Process Handling**
  Semaphore-limited concurrent processes (max 3), real-time output monitoring, proper PID tracking, graceful termination, and semaphore release on completion.
- **Respects Pwnagotchi Personality Settings**
  Now honors core `deauth` and `associate` flags from the agent’s personality config.
- **Adaptive Token Bucket Rate Limiting**
  Per-AP buckets that dynamically adjust refill rate based on real-time success ratio.
- **Time-of-Day Channel Scoring Bonus**
  Learns busiest channels per time period (night/morning/afternoon/evening) and adds bonus to UCB1 selection.
- **Deep Capability Parsing**
  Automatically detects and stores WPS, WPA3 (SAE), FT, Enterprise, PMF, TDLS, and Mesh capabilities from raw packets (with thread-safe locks).
- **State Persistence**
  Full JSON state save/restore (`/root/handshakes/probenpwn_state.json`) for handshake_db, blacklist, client scores, channel stats — atomic writes + automatic backup.
- **MAC Randomization**
  Generates and rotates a pool of locally-administered unicast MACs on every injected frame.
- **Power & Resource Awareness**
  Auto-pauses attacks on low battery (<15%) or high CPU (>80%) using psutil.
- **Dry-Run Mode**
  Configurable `dry_run = true` — logs what it *would* do without transmitting any packets.
- **Enhanced UI with New Elements**
  Attack rate (attacks/second), top targets (shortened MACs), GPS lock indicator, ETA estimate, current PMF method, external processes count, battery % + charging icon — all individually toggleable and position-configurable.
- **Dedicated Background Sniffer Threads**
  SAE auth frame sniffer (for future WPA3 capture) + client capability sniffer.
- **Optional Background Handshake Uploader**
  Queued upload of every captured handshake to a custom `upload_url` (requires `requests`).
- **Massive Thread-Safety & Reliability Upgrades**
  Locks on all shared structures, fixed retry queue with proper bounding, external process cleanup, state save interval, and comprehensive error handling.
- **Expanded Attack Arsenal**
  WPA3 downgrade, FT handshake, TDLS, Mesh, EAPOL-Start/Logoff, Disassociation, Null Data, PS-Poll, CF-End, MIMO, probe client, plus improved PMF variants and flood attacks (maniac mode only).

### Compatibility with jayofelony Image 2.9.5.4 (Debian Trixie)
ProbeNpwn v3.3.0 is fully compatible with the latest jayofelony image (2.9.5.4), which is based on Debian Trixie.
Benefits on this image:
- Reliable Scapy installation (via `apt` — no PEP 668 issues)
- Improved monitor mode/injection stability for all quiet attacks and PMF bypass
- Faster Python 3.12 performance
- Better concurrency with fixed thread pools and background sniffers
- Native support for bully/reaver and full external tool suite

### Config Example (`config.toml`) Use the **bracketed config.toml format** below (required on newer image 2.9.5.4):
```toml
[main.plugins.probenpwn]
enabled = true
mode = "adaptive"
attacks_x_coord = 110
attacks_y_coord = 20
success_x_coord = 110
success_y_coord = 30
handshakes_x_coord = 110
handshakes_y_coord = 40
pnp_status_x_coord = 110
pnp_status_y_coord = 10
mode_x_coord = 110
mode_y_coord = 50
top_channels_x_coord = 110
top_channels_y_coord = 60
pmf_status_x_coord = 110
pmf_status_y_coord = 70
success_bar_x_coord = 110
success_bar_y_coord = 80
attack_rate_x_coord = 120
attack_rate_y_coord = 20
top_targets_x_coord = 120
top_targets_y_coord = 30
gps_indicator_x_coord = 120
gps_indicator_y_coord = 40
eta_x_coord = 120
eta_y_coord = 50
pmf_method_x_coord = 120
pmf_method_y_coord = 60
ext_procs_x_coord = 120
ext_procs_y_coord = 70
battery_x_coord = 120
battery_y_coord = 80
show_attacks = true
show_success = true
show_handshakes = true
show_mode = true
show_top_channels = true
show_pmf_status = true
show_success_bar = true
show_pnp_status = true
show_attack_rate = true
show_top_targets = true
show_gps_indicator = true
show_eta = true
show_pmf_method = false
show_ext_procs = false
show_battery = false
verbose = true
enable_5ghz = true
enable_6ghz = true
max_retries = 5
env_check_interval = 3
min_recon_time = 2
max_recon_time = 30
min_ap_ttl = 30
max_ap_ttl = 300
min_sta_ttl = 30
max_sta_ttl = 300
min_deauth_prob = 0.9
max_deauth_prob = 1
min_assoc_prob = 0.9
max_assoc_prob = 1
min_min_rssi = -85
max_min_rssi = -60
min_throttle_a = 0.1
max_throttle_a = 0.2
min_throttle_d = 0.1
max_throttle_d = 0.2
pmf_bypass_methods = ["bad_msg", "assoc_sleep", "rsn_corrupt", "frag"]
use_external_tools = false
enable_pmkid_attack = true
enable_auth_harvest = true
enable_reassociation = true
enable_rsn_probe = true
pin_save_path = "/root/handshakespin/"
mac_randomization = true
dry_run = false
low_battery_threshold = 15
high_cpu_threshold = 80
upload_url = "https://your-upload-endpoint.com"
upload_interval = 3600
enable_wpa3_downgrade = true
enable_ft_handshake = true
enable_sae_capture = false
enable_tdls = false
enable_mesh = false
enable_wps = true
enable_eapol_start = true
enable_eapol_logoff = true
enable_disassociation = true
enable_null_data = true
enable_csa = false
enable_beacon_flood = false
enable_probe_response_flood = false
enable_auth_flood = false
enable_assoc_flood = false
enable_ps_poll = true
enable_cf_end = false
enable_mimo = false
rate_limit_refill_rate = 0.5
rate_limit_max_tokens = 10
blacklist_path = "/root/handshakes/probenpwn_blacklist.json"
log_path = "/root/handshakes/probenpwn_captures.jsonl"
log_max_bytes = 10485760
log_backup_count = 3
state_path = "/root/handshakes/probenpwn_state.json"
```

**Educational and Research Tool Only**
This plugin is provided strictly for **Educational purposes, Security research, and Authorized penetration testing**. It must only be used on networks and devices you own or have explicit written permission to test. Unauthorized use is illegal under laws such as the Computer Fraud and Abuse Act (CFAA) in the United States and equivalent legislation worldwide. The author and contributors are not responsible for any misuse or legal consequences.

## Overview
ProbeNpwn is the **ultimate aggressive handshake/PMKID/WPS capture plugin** for Pwnagotchi — now completely rebuilt as v3.3.0 with stealthy quiet attacks, full WPS PIN extraction, state persistence, MAC randomization, power awareness, and an expanded arsenal that works on WPA3, FT, Enterprise, Mesh, TDLS, and every modern protected network. Built on the solid foundation of v2.0.0, this version adds **quiet association attacks (no deauth)**, **WPS PIN saving**, **adaptive token buckets**, **time-of-day scoring**, **capability-aware attacks**, **background sniffers**, **optional uploader**, and a much richer configurable UI. It remains the smartest, most stable, and most undetectable capture engine available.

## Key Features
- **Quiet Association Attacks (PMKID, Auth Harvest, Reassociation, RSN Probe, CSA)**
  Stealthy handshakes without any deauth — perfect for PMF-protected and monitored networks.
- **WPS Attack with PIN Capture**
  bully/reaver integration with real-time PIN extraction and automatic saving to dedicated folder.
- **Quad Modes (Tactical, Maniac, Stealth, Adaptive)**
  Adaptive mode now uses success ratio + density for smarter switching.
- **Advanced PMF Bypass + Expanded Attacks**
  All previous methods plus WPA3 downgrade, FT handshake, TDLS, Mesh, EAPOL-Start/Logoff, Disassociation, Null Data, PS-Poll, CF-End, MIMO, floods, and more.
- **UCB1 Intelligent Channel Hopping with Time-of-Day Bonus**
  Learns busiest channels by hour and adds period-specific scoring.
- **Multi-Band Support (2.4/5/6 GHz)**
  Fully configurable with unique channel lists.
- **Dynamic Mobility + Resource Scaling**
  GPS + AP rate mobility score + battery/CPU awareness — auto-pauses when needed.
- **Adaptive Token Bucket Rate Limiting**
  Per-AP, success-aware dynamic throttling.
- **MAC Randomization**
  Rotating locally-administered MAC pool.
- **State Persistence & Reliability**
  JSON state save/restore, atomic writes, backup, retry queue, TTL caches, decay mechanisms.
- **Full Capability Parsing**
  WPS, WPA3, FT, Enterprise, PMF, TDLS, Mesh detection.
- **Richer Custom UI**
  13 individually toggleable elements including attack rate, ETA, top targets, battery, etc.
- **Background Sniffers & Uploader**
  SAE + client capability sniffers + queued upload support.
- **Dry-Run Mode, External Tool Fallback, and Full Thread Safety**
- 
## What's New in ProbeNpwn v3.3.0?
This release is a complete evolution — adding stealth, WPS support, persistence, intelligence, and usability upgrades that make it the most capable handshake plugin ever.

### 1. Quiet Association Attacks (No Deauth)
**What's New:**  
PMKID association, auth frame harvest, reassociation PMKID, RSN probe, CSA probe.  
**How It Works:**  
Uses random or rotated MACs and carefully crafted association/probe/auth frames.  
**Why It's Better:**  
Captures on PMF/WPA3 networks without triggering deauth alarms or client logs.
### 2. WPS Attack with PIN Saving
**What's New:**  
Full bully/reaver support with PIN regex parsing and auto-save to `/root/handshakespin/`.  
**How It Works:**  
Semaphore-limited concurrent processes, real-time output monitoring, early termination on PIN found.  
**Why It's Better:**  
Many routers still expose WPS — instant crack path saved automatically.
### 3. Adaptive Token Bucket + Time-of-Day Scoring
**What's New:**  
Success-ratio adaptive rate limiting and per-period channel bonuses.  
**How It Works:**  
Buckets adjust on-the-fly; UCB1 now includes night/morning/etc. patterns.  
**Why It's Better:**  
Smarter, more efficient targeting in real-world environments.
### 4. State Persistence & MAC Randomization
**What's New:**  
JSON state file + rotating locally-administered MAC pool.  
**How It Works:**  
Atomic saves, backup on load, MAC pool refreshed per frame.  
**Why It's Better:**  
Survives reboots and defeats MAC-based defenses.
### 5. Power/Resource Management + Dry-Run
**What's New:**  
Battery/CPU pause + dry_run flag.  
**How It Works:**  
psutil checks; logs actions without transmitting when dry_run=true.  
**Why It's Better:**  
Prevents draining devices and allows safe testing.
### 6. Richer UI + Background Features
**What's New:**  
Attack rate, top targets, GPS, ETA, PMF method, ext procs, battery + background sniffers and uploader.  
**How It Works:**  
All elements toggleable/positionable; sniffers run in dedicated threads.  
**Why It's Better:**  
Real-time performance visibility and optional cloud upload.
### 7. Expanded Attack Arsenal & Personality Respect
**What's New:**  
WPA3/FT/TDLS/Mesh/EAPOL/Null/PS-Poll/CF-End/MIMO + full respect for core personality flags.  
**How It Works:**  
Capability-aware + config toggles for every attack type.  
**Why It's Better:**  
Covers every modern Wi-Fi weakness with maximum control.
## Why You'll Love It
ProbeNpwn v3.3.0 is now the **most complete, intelligent, and user-friendly** handshake/PMKID/WPS plugin:
- **Stealth King:** Quiet attacks + MAC randomization = works where others fail.
- **WPS Ready:** Automatic PIN capture and saving.
- **Future-Proof:** WPA3, FT, Mesh, TDLS, 6 GHz, capability-aware.
- **Rock-Solid:** State persistence, resource awareness, thread safety, adaptive everything.
- **Customizable:** 13 UI elements, dry-run, uploader, per-attack toggles.


## How to Get Started
### Dependencies Needed
- **Scapy**: Auto-installed by the plugin (prefers `sudo apt install python3-scapy`, falls back to `pip3 install --user scapy`). Required for all quiet attacks, PMF bypass, and advanced packet crafting.
- **psutil** (optional but recommended): For battery/CPU monitoring and auto-pause. Install via `sudo apt install python3-psutil` or `pip3 install psutil`.
- **requests** (optional): For background handshake upload feature. Install via `sudo apt install python3-requests` or `pip3 install requests`.
- **External Tools** (optional):
  - `aireplay-ng`, `mdk4`, `hcxdumptool` (for fallback deauth) → `sudo apt install aircrack-ng mdk4 hcxdumptool`
  - `bully` and/or `reaver` (for WPS attacks) → `sudo apt install bully reaver`
### Easy Way (Recommended)
1. **Add Repo to config.toml** (if not already):
   ```toml
   main.custom_plugin_repos = [
    "https://github.com/jayofelony/pwnagotchi-torch-plugins/archive/master.zip",
    "https://github.com/Sniffleupagus/pwnagotchi_plugins/archive/master.zip",
    "https://github.com/NeonLightning/pwny/archive/master.zip",
    "https://github.com/marbasec/UPSLite_Plugin_1_3/archive/master.zip",
    "https://github.com/AlienMajik/pwnagotchi_plugins/archive/refs/heads/main.zip",
    "https://github.com/cyberartemio/wardriver-pwnagotchi-plugin/archive/main.zip",
   ]
   main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins/"
   ```
2. **Install**:
   ```bash
   sudo pwnagotchi plugins update
   sudo pwnagotchi plugins install probenpwn
   ```
   
### Manual Way
```bash
git clone https://github.com/AlienMajik/pwnagotchi_plugins.git
sudo cp probenpwn.py /usr/local/share/pwnagotchi/custom-plugins/
```

### Config Example (`config.toml`)
(See the full example in the Recent Update section above — it includes every new option.)
Restart: `sudo systemctl restart pwnagotchi`

## Pro Tip
Start with **adaptive mode** — it now handles quiet attacks, WPS, and resource management automatically. Enable all quiet association methods and WPS for maximum coverage on modern networks. Use `dry_run = true` first to see what it will do. For stealth ops, set `mode = "stealth"`, enable MAC randomization, and keep rate limiting conservative. Watch the new UI elements for real-time stats! For WPS-heavy environments, make sure bully/reaver are installed and `enable_wps = true`.
https://papers.mathyvanhoef.com/wisec2022.pdf

## Disclaimer
This software is provided for educational and research purposes only. Use of this plugin on networks or devices that you do not own or have explicit permission to test is strictly prohibited. The author(s) and contributors are not responsible for any misuse, damages, or legal consequences that may result from unauthorized or improper usage. By using this plugin, you agree to assume all risks and take full responsibility for ensuring that all applicable laws and regulations are followed.

---
 
# SnoopR Plugin

Welcome to **SnoopR**, the most advanced surveillance-detection and wardriving plugin for **Pwnagotchi**! SnoopR turns your pocket-sized AI companion into a powerful multi-modal sensor that logs Wi-Fi, Bluetooth/BLE, and even overhead aircraft, while intelligently identifying potential tails or persistent trackers through movement, velocity, spatial clustering, and RSSI-based positioning.

This release (**v7.0.1**) is a correctness and performance overhaul of v6.0.0. Several headline v6 features were present in the code but never actually ran: persistence scoring was dead outside UTC, velocity was always zero, trilateration compared degrees against metres, the OUI parser loaded zero entries from the documented Wireshark database, threat alerts were never generated or reachable, mesh was send-only and unauthenticated, and circling detection was gated behind a condition that made it impossible to satisfy. All of those are fixed and verified. On top of that, the snooper rule was rebuilt so it stops flagging every access point you drive past, the web UI is no longer vulnerable to a hostile SSID, and the plugin no longer holds the database lock through its own analysis. v7.0.1 adds compatibility work for recent jayofelony images (Trixie/venv, relocated handshakes, real `bluetooth_device` support).

**v7 is a drop-in replacement.** Same database file, same plugin name, same web path. The schema migrates itself on first start and existing data is preserved — stored timestamps were always UTC, so old rows begin scoring correctly immediately.

Key enhancements and fixes over previous versions (and why they’re better):
- **UTC end-to-end (fixed)** – SQLite's `CURRENT_TIMESTAMP` is UTC but v6 compared it against local time, so outside UTC the scoring windows never matched: `persistence_score` stayed 0, nothing was ever flagged, and pruning cut at the wrong instant. Everything now uses a single UTC clock and converts only for display.
- **Velocity and movement analysis (fixed)** – Detection rows were returned newest-first while the loop assumed oldest-first, so every time delta was negative and `max_velocity` could never be anything but zero. Rows are now chronological; velocity is stored and reported in **mph**.
- **Trilateration in a real coordinate system (fixed)** – v6 minimised an objective mixing degrees (positions) with metres (path-loss distances). Solving now happens in a local metre plane and unprojects, recovering a test transmitter within 10 m from six observations.
- **OUI database that actually loads (fixed)** – The v6 parser only understood IEEE `oui.txt`, but the documented install (`wireshark-common`) provides the tab-separated `manuf` format, so it loaded **zero** entries. Every vendor came back `Unknown` — and because the rogue heuristic matched the literal string "unknown", every device on the air was flagged rogue. Both formats now parse, including `/28` and `/36` masks.
- **Threat alerts that fire (fixed)** – `add_alert()` had no call site and the browser subscribed to absolute `/alerts` and `/stream`, which 404 under `/plugins/snoopr/`. Alerts are now raised for aircraft anomalies, geofence breaches and new snooper flags, over one relative `events` stream with keepalives.
- **Authenticated mesh with a receive loop (fixed)** – v6 never called its own receive method, and that method inserted unauthenticated UDP JSON straight into the database. Frames are now HMAC-SHA256 authenticated, AES-GCM encrypted, replay-protected and schema-validated, with a dedicated receiver thread.
- **Circling detection that can trigger (fixed)** – v6 only ran the detector after an aircraft moved **more than** 500 m, while circling requires a hull diameter **at most** 500 m: mutually exclusive. Every position now feeds the tracker; the dedupe test only gates the database write.
- **Snooper rule rebuilt** – Persistence alone no longer flags a device. SnoopR now requires corroboration that it was **close** at **separated** places. See *Understanding snooper detection* below.
- **Stored XSS fixed** – Map popups were built with template literals, so an SSID like `<img src=x onerror=…>` executed in the operator's browser. The dashboard now builds every cell and popup with `textContent`; KML is XML-escaped.
- **OpenSky OAuth2** – Basic authentication was retired upstream on 2026-03-18; `opensky_username`/`password` no longer work at all. SnoopR implements the client-credentials flow with token caching, plus an offline CSV fallback and negative caching for unknown ICAOs.
- **No lock held during analysis** – v6 held the database lock across the entire per-device analysis including the optimiser, blocking every scan write and web request. Locks are now per-operation.
- **Paginated JSON API** – The old page embedded every device and trail into the HTML and ran an N+1 query per row. There is now a single windowed query plus a batched trail query behind `data.json`, with server-side search, sort, filter and pagination.
- **Bounded memory** – Aircraft tracks, Kalman filters, the aircraft cache, WiGLE results and the rate-limiter table are all LRU/TTL-evicted. v6 leaked all of them on long runs.
- **Image compatibility (v7.0.1)** – `bluetooth_device` is finally passed to bleak, `aircraft_file` is probed across the locations recent images actually use, `base_dir` falls back when `/root` isn't writable, and the missing-dependency warning names the interpreter pwnagotchi is running from.

## Features
- **Multi-source detection**: Wi-Fi APs + clients, Bluetooth/BLE (with manufacturer data), ADS-B aircraft.
- **Geofencing**: Circle and polygon zones with real-time breach detection, map overlays and KML output.
- **Persistence scoring**: Recent-activity windows plus a bonus for close-range zones (distant GPS cells no longer inflate it).
- **Evidence-based snooper flagging**: Close-range presence across separated locations, or persistence corroborated by multiple zones and sessions. Every flag records a human-readable reason.
- **RSSI trilateration**: Position estimate plus a meaningful MSE in m², SciPy-accelerated when available.
- **Spatial clustering**: O(n) ~100 m grid bucketing (v6 was O(n²) over every detection).
- **Vendor & classification**: Wireshark `manuf` + IEEE `oui.txt` + Bluetooth company IDs + heuristics.
- **Randomised MAC awareness**: Locally-administered addresses are detected, labelled and excluded from persistence-only flagging.
- **Advanced aircraft tracking**: OpenSky metadata, behavioural anomaly detection (circling, squawks, vertical rate, speed, sharp turns), dump1090/readsb/tar1090 field support.
- **Modern BLE scanning**: Async bleak scanner with real adapter selection.
- **Authenticated mesh**: Encrypted, replay-protected, validated peer sharing.
- **WiGLE fallback**: SSID geolocation with caching and rate-limit backoff.
- **Kalman-smoothed RSSI**: Written to the database and used for distance estimates.
- **Rich web interface**: Trails, heatmap, anomalies column, geofence overlays, KML export, dark mode, live counts + threat alerts, search, sorting, filters, pagination.
- **Pwnagotchi UI counters**: Wi-Fi, BT, Aircraft, Snoopers, High Persistence — configurable position, updated off a background thread.
- **Whitelisting**: SSID/MAC (case-insensitive, and now actually matching for Wi-Fi).
- **Automatic pruning**: Background maintenance thread with periodic VACUUM.
- **Robust logging & error handling**.

## Requirements & Dependencies
### Core Requirements
- **GPS** via Bettercap (gps plugin recommended).
- **Bluetooth** enabled (`sudo hciconfig hci0 up` or your interface).
- **Internet on viewing device** for map tiles/Leaflet and OpenSky lookups.
- **aircraft.json** file (for ADS-B feed — optional; everything else works without it).

### Python Dependencies (Recommended for Full Features)

**Install into the interpreter pwnagotchi actually uses.** Recent images (2.9.5.4+, Trixie base) run from a virtualenv under PEP 668, so a plain `sudo pip3 install` lands in the system Python and the plugin will still report the packages as missing. Find the right interpreter first:

```bash
systemctl cat pwnagotchi | grep -i exec        # or: head -1 $(command -v pwnagotchi)
sudo /path/to/that/python -m pip install bleak cryptography scipy
```

On images with the venv at `/home/pi/.pwn`:

```bash
sudo bash
source /home/pi/.pwn/bin/activate
pip3 install bleak cryptography scipy
```

SnoopR logs the exact interpreter path next to the missing-package warning, so the log tells you where the install has to go.

- `bleak`: Modern BLE scanning.
- `cryptography`: Mesh encryption (required for mesh unless `mesh_allow_plaintext` is set).
- `scipy`: Faster Nelder-Mead trilateration (optional — pure Python fallback included).

### Vendor Databases
SnoopR downloads the Bluetooth company identifiers database in the background on first run if missing (v6 blocked boot for up to 30 seconds doing this). For Wi-Fi vendor lookup, the Wireshark OUI database is preferred.

**Recommended (automatic OUI via package):**
```bash
sudo apt update && sudo apt install wireshark-common
```

**Manual Download Options** (use if `apt` is unavailable or for offline setup):
- **Bluetooth Company Identifiers** (manually download to the configured path, default `<base_dir>/company_identifiers.json`):
  ```bash
  sudo mkdir -p /root/snoopr
  sudo wget -O /root/snoopr/company_identifiers.json https://raw.githubusercontent.com/NordicSemiconductor/bluetooth-numbers-database/master/v1/company_ids.json
  ```
- **Wireshark OUI Database** (manually download if wireshark-common not installed):
  ```bash
  sudo wget -O /usr/share/wireshark/manuf https://www.wireshark.org/download/automated/data/manuf
  ```
- **ADS-B feed** (required for aircraft): Tool outputting valid `aircraft.json`. dump1090/readsb/tar1090 wrappers (`{"now":…,"aircraft":[…]}`) and legacy list/dict formats are all accepted.
- **WiGLE API keys** (optional): For fallback geolocation.
- **OpenSky API client** (optional, for aircraft registration/type/owner): Create one on your account page at opensky-network.org and use `opensky_client_id` / `opensky_client_secret`. Username/password authentication was retired upstream on 2026-03-18 and no longer works.
- **Local aircraft CSV** (optional, fully offline metadata): point `aircraft_db_csv` at a crowd-sourced aircraft database export. It takes priority over the network lookup.

## Installation Instructions
Manual installation recommended (advanced dependencies):

```bash
cd /etc/pwnagotchi/custom-plugins/
sudo wget https://raw.githubusercontent.com/AlienMajik/pwnagotchi_plugins/main/snoopr.py
```

Or clone:

```bash
sudo git clone https://github.com/AlienMajik/pwnagotchi_plugins.git /tmp/pwnplugins
sudo cp /tmp/pwnplugins/snoopr.py /etc/pwnagotchi/custom-plugins/
sudo rm -rf /tmp/pwnplugins
```

Install dependencies (see the venv note above), then restart:

```bash
sudo apt install wireshark-common
sudo systemctl restart pwnagotchi
```

Verify the start:

```bash
sudo tail -f /etc/pwnagotchi/log/pwnagotchi.log | grep SnoopR
```

A healthy start logs a **non-zero OUI count** (this is the tell for the broken v6 parser), a Bluetooth company ID count, the aircraft feed path in use, the geofence count and a session ID.

## Configuration
`main.plugins.snoopr.key = value` and `[main.plugins.snoopr]` are the *same thing* in TOML — they parse to an identical table. Use whichever style you prefer; there is no image-specific requirement, and both have always worked. Restart after changes.

Every v6 key is still accepted. Nothing below is mandatory.

### Full Configuration Reference
```toml
[main.plugins.snoopr]
enabled = true

# --- storage & inputs ---
base_dir = "/root/snoopr"                 # falls back to /home/pi/snoopr if unwritable
aircraft_file = "/home/pi/handshakes/skyhigh_aircraft.json"  # auto-probed if unset/missing
aircraft_db_csv = ""                      # optional offline aircraft metadata CSV
oui_db_path = "/usr/share/wireshark/manuf"

# --- scanning ---
scan_interval = 10
scan_duration = 5
bluetooth_enabled = true
bluetooth_device = "hci0"                 # now actually passed to bleak
log_without_gps = false
gps_max_age = 60                          # seconds before a GPS fix is considered stale

# --- retention ---
prune_days = 30
prune_interval_hours = 6                  # pruning runs in the background, not at shutdown

# --- analysis ---
persistence_threshold = 0.85
persistence_window_minutes = 5
persistence_windows = 4
analysis_days = 7
analysis_row_limit = 4000
update_interval = 300
movement_threshold = 0.8                  # miles of separation for "this followed me"
time_threshold_minutes = 20
min_rssi_for_movement = -70               # signal floor for "it was actually near me"
max_plausible_velocity_mph = 200          # rejects GPS jumps
require_movement_for_snooper = true       # false = v6 persistence-only behaviour
flag_randomized_snoopers = false

# --- trilateration ---
triangulation_min_points = 8
mse_threshold_m2 = 2500                   # real mean-square error in m^2 (50 m RMS)
tx_power_wifi = -20
tx_power_bt = -20
path_loss_n_wifi = 2.7
path_loss_n_bt = 2.7

# --- aircraft ---
aircraft_interval = 15                    # feed poll seconds
aircraft_move_threshold = 300             # metres of movement before a new row is written
aircraft_low_altitude_threshold = 3000    # renamed from aircraft_high_altitude_threshold
aircraft_circling_radius = 1500
aircraft_circling_time = 120
aircraft_rapid_descent_threshold = 3000
aircraft_rapid_climb_threshold = 3000
aircraft_max_speed_knots = 600
aircraft_min_speed_knots = 50
aircraft_enable_squawk_alerts = true
opensky_client_id = ""
opensky_client_secret = ""

# --- mesh (mesh_key is mandatory when enabled) ---
mesh_enabled = false
mesh_host = "0.0.0.0"
mesh_port = 8888
mesh_peers = []
mesh_key = ""
mesh_allow_plaintext = false              # only needed if cryptography is unavailable

# --- WiGLE fallback ---
wigle_enabled = false
wigle_api_name = ""
wigle_api_token = ""

# --- filtering ---
whitelist_ssids = ["MyHomeWiFi", "MyPhone"]
whitelist_macs = []

# --- alerts & web ---
alert_on = ["squawk", "geofence", "circling", "rapid", "snooper"]
sse_enabled = true                        # false = dashboard polls instead
max_sse_clients = 2
max_path_points = 300
rate_limit_per_minute = 120

# --- pwnagotchi display ---
ui_enabled = true
ui_x = 0
ui_y = 90
ui_line_height = 10
ui_elements = ["wifi", "bt", "aircraft", "snoopers", "persistence"]

# Example geofences (list of tables)
[[main.plugins.snoopr.geofences]]
name = "Home Zone"
type = "circle"
lat = 37.7749
lon = -122.4194
radius = 500

[[main.plugins.snoopr.geofences]]
name = "Restricted Area"
type = "polygon"
points = [[37.77, -122.42], [37.78, -122.41], [37.79, -122.43], [37.77, -122.42]]
```

### Renamed Keys (old names still read)
| Old | New | Why |
|---|---|---|
| `opensky_username` / `opensky_password` | `opensky_client_id` / `opensky_client_secret` | Basic auth retired upstream 2026-03-18 |
| `mse_threshold` | `mse_threshold_m2` | Now a real error in m²; legacy values under 500 are ignored with a warning |
| `aircraft_high_altitude_threshold` | `aircraft_low_altitude_threshold` | The test was always for *low* altitude |

## Understanding snooper detection
This is the biggest behavioural change from v6 and worth reading before you tune anything.

The coordinates SnoopR logs are the **receiver's** position, not the device's. In v6 that meant driving made every stationary access point look fast (the velocity trigger was 1.5 m/s — walking pace), and sitting anywhere for twenty minutes maxed out the persistence score for everything in range. Everything was a snooper, so nothing was.

v7 requires corroboration that a device was **close** at **separated** places:

- **`followed`** — strong signal (≥ `min_rssi_for_movement`) at points at least `movement_threshold` miles apart, spanning at least five minutes; or
- **persistence ≥ threshold** *and* at least two close-range zones *and* at least two sessions.

Zone bonuses count only close-range fixes, so a slow drive-by no longer inflates the score. Aircraft are excluded from snooper analysis entirely. Randomised (locally-administered) MACs are not flagged on persistence alone, because modern phones rotate them roughly every fifteen minutes. Every flag stores a `snooper_reason` shown in the table and popups.

**A stationary unit cannot distinguish a tail from a neighbour.** That is a limit of one receiver in one place, not a tuning problem. For fixed counter-surveillance installs, set `require_movement_for_snooper = false` to restore the v6 persistence-only trigger.

## Database Schema Updates
On startup SnoopR migrates the schema automatically, adding missing columns (`channel`, `auth_mode`, `triangulated_lat`, `last_seen`, `anomalies`, plus new `is_randomized`, `snooper_reason`, `best_rssi`, `first_seen`) with ALTER TABLE. A `meta` table tracks the schema version, `first_seen`/`last_seen` are backfilled for pre-v7 rows, a unique index is enforced on `(mac, device_type)`, and inserts use `ON CONFLICT … DO UPDATE`. The `aircraft_info` table gains a `status` column for negative caching. Indexes cover `(network_id, timestamp)`, `session_id`, `mac`, `device_type` and `last_seen`.

## Usage
Runs automatically on boot.
- Wi-Fi/BLE/aircraft logged with full details, filtered RSSI and anomalies.
- Background threads handle aircraft processing, periodic analysis, maintenance/pruning, UI counts and buffered writes — none of them block the scan path or the display.
- Web UI: `http://<pwnagotchi_ip>:8080/plugins/snoopr/`

| Route | Purpose |
|---|---|
| `/plugins/snoopr/` | Dashboard |
| `/plugins/snoopr/data.json` | Paginated device data (`filter_by`, `sort_by`, `search`, `limit`, `offset`) |
| `/plugins/snoopr/export.kml` | KML export, honours the active filter |
| `/plugins/snoopr/events` | Live counts + threat alerts (`stream` and `alerts` are aliases) |

Filters: all, snoopers, high persistence, anomalies, Wi-Fi, clients, Bluetooth, aircraft, randomised.

## Notes
- Database: `<base_dir>/snoopr.db`.
- Triangulated positions are prioritised on the map; popups say which kind of fix you're looking at, and `triangulated_mse` lets you judge it.
- All timestamps are stored in UTC and displayed in local time.
- Velocity is reported in mph.
- High Persistence uses `persistence_threshold` everywhere (v6 hardcoded 0.7 in two places).
- Bluetooth company DB is downloaded in the background if missing.
- OUI database is read from the Wireshark path if available; both `manuf` and `oui.txt` formats are supported.
- If live updates are disabled or the stream drops three times, the dashboard falls back to polling automatically.
- Geofences and aircraft anomalies appear in real time as floating alerts.

## Known limitations
- Stationary detection is unsolvable with a single receiver (see *Understanding snooper detection*).
- BLE MAC randomisation defeats per-MAC tracking for phones; such devices are labelled rather than tracked.
- Path-loss trilateration assumes free space; indoors, expect tens of metres of error.
- The OpenSky metadata endpoint is not formally part of their documented REST surface; if it disappears, use `aircraft_db_csv`.

## Community and Contributions
Community-driven and evolving fast. Issues/PRs welcome on GitHub!

## Disclaimer
For educational and security testing only. Respect privacy and local laws. Use responsibly!

✅ What’s New in v7.0.0 / v7.0.1
1. UTC handling throughout — persistence scoring, recent-device selection and pruning work in every timezone.
2. Chronological analysis rows — velocity and movement detection actually compute.
3. Trilateration solved in a local metre plane instead of mixing degrees and metres.
4. OUI parser that understands the Wireshark `manuf` format (v6 loaded zero entries, which made every device look rogue).
5. Threat alerts generated and delivered over a working relative SSE endpoint.
6. Mesh receive loop, with HMAC authentication, AES-GCM encryption, replay protection and schema validation.
7. Circling detection freed from the mutually-exclusive gate that made it impossible.
8. Snooper rule rebuilt around close-range evidence across separated locations, with recorded reasons.
9. Stored XSS in map popups fixed; KML XML-escaped.
10. OpenSky OAuth2 client-credentials flow, negative caching, and an offline CSV fallback.
11. Filtered RSSI and aircraft metadata wired up instead of written and ignored.
12. Database lock no longer held during analysis; O(n) clustering; no N+1 queries; paginated JSON API.
13. Bounded memory for tracks, filters and caches; single flusher thread; background pruning.
14. dump1090/readsb field names, `"ground"` altitudes and integer squawks handled.
15. Aircraft excluded from snooper analysis; randomised MACs detected and labelled.
16. Configurable UI element positions; counts pushed from a background thread.
17. **7.0.1** — `bluetooth_device` passed to bleak (both modern and legacy kwargs), aircraft feed path auto-probed for relocated handshakes, `base_dir` fallback, venv-aware dependency warning, `sse_enabled` toggle with automatic polling fallback.

# SkyHigh Plugin
## Overview
SkyHigh is a custom plugin for Pwnagotchi that tracks nearby aircraft using the OpenSky Network API. It displays the number of detected aircraft on your Pwnagotchi's screen and provides an interactive map view via a webhook, featuring detailed aircraft types (helicopters, commercial jets, small planes, drones, gliders, military) with distinct icons. A pruning feature keeps the data clean by removing outdated aircraft, and the web interface now offers powerful filtering and export options.

## What’s New in Version 2.0.0
The updated SkyHigh plugin (version 2.0.0) brings significant refinements focused on stability, usability, performance, and configurability. This release incorporates community enhancements and addresses real-world usage feedback. Below is a detailed breakdown of what’s new and how it improves on previous versions:

- **Type-Based Filtering in the Web Interface:** A new dropdown filter lets users instantly show only specific aircraft types (Military, Helicopter, Commercial Jet, Small Plane/GA, Drone, Glider, or Other) alongside existing callsign, model, and altitude filters.
- **Synchronized Map and Table Filtering:** When filters are applied, matching aircraft are now hidden from **both** the table **and** the map markers, keeping the view clean and focused.
- **Configurable Map Tiles:** Added `map_tile_url` option (default: OpenStreetMap) allowing users to switch to alternative tile providers (e.g., satellite, dark mode) directly from config.
- **Metadata Cache Expiry:** Cache entries now automatically expire after a configurable period (`metadata_cache_expiry_days`, default 7 days), ensuring stale model/registration data is refreshed over time.
- **Option to Disable Metadata Fetching:** New `disable_metadata` config flag completely skips metadata API calls when enabled—ideal for anonymous use or when rate limits are a concern.
- **Improved Type Detection:** Centralized pattern matching using a maintainable `TYPE_PATTERNS` dictionary that checks manufacturer, model, and typecode for more accurate and extensible categorization.
- **More Reliable Pruning:** Pruning now uses precise OpenSky `last_contact` timestamps instead of local strings, ensuring accurate removal of stale aircraft.
- **Enhanced Thread Safety and Code Structure:** Switched to reentrant locks (`RLock`) and added better separation of concerns for metadata and data handling, reducing risk of race conditions.
- **Robust Metadata Fallbacks:** If fresh metadata fails, the plugin falls back to any cached entry (even expired) before using defaults, minimizing "Unknown" entries during network issues.
- **Export Improvements:** CSV and KML exports now skip aircraft with invalid coordinates for cleaner output.

## How It’s Better Overall
- **Superior Web Interface:** Synchronized type filtering and map marker hiding make it far easier to focus on specific traffic (e.g., "show only military" or "hide low-altitude GA"). The UI is now genuinely interactive and practical for real-time monitoring.
- **Increased Reliability and Performance:** Expiring cache, disable-metadata option, and smarter fallbacks reduce API strain and errors, while improved pruning and threading keep everything smooth even under heavy load.
- **Greater Configurability:** New options for map tiles and metadata behavior give users fine-grained control without touching code.
- **More Maintainable and Community-Friendly:** Cleaner architecture, centralized patterns, and modular design make it easier for others to contribute or customize.
- **Future-Ready:** Historical position tracking remains in place (up to 10 points per aircraft) as groundwork for upcoming flight path visualization.

## How It Works
- **Data Fetching:** Queries the OpenSky API every 60 seconds (configurable) to retrieve aircraft data within the specified radius, supporting both anonymous and authenticated requests.
- **Metadata Enrichment:** Optionally fetches detailed metadata (model, registration, DB flags, type categorization) for each aircraft using its ICAO24 code, with caching, expiry, and robust fallbacks.
- **Historical Position Tracking:** Stores up to 10 recent positions per aircraft locally—foundation for future flight path features.
- **Pruning:** Aircraft not seen within the `prune_minutes` interval are removed using accurate OpenSky timestamps.
- **UI Display:** The Pwnagotchi screen shows the current aircraft count, last update time, and any error messages.
- **Webhook Map:** The webhook (`/plugins/skyhigh/`) renders a responsive table and interactive Leaflet map with type-specific icons. Filters instantly hide/show matching entries on both the table and map.

## Installation and Usage
### Prerequisites
- A Pwnagotchi device with internet access.
- GPS Adapter (Optional): For dynamic tracking, connect a GPS adapter and enable the built-in gps plugin. The plugin will use real-time coordinates if available, falling back to static ones.

### Step-by-Step Installation
You can install SkyHigh in two ways: the easy way (recommended) or the manual way.

#### Easy Way (Recommended)
1. **Update Your Config File**  
   Edit `/etc/pwnagotchi/config.toml` and ensure custom plugin repositories are enabled (include the AlienMajik repo if not already present):
   ```toml
   main.confd = "/etc/pwnagotchi/conf.d/"
   main.custom_plugin_repos = [
     "https://github.com/jayofelony/pwnagotchi-torch-plugins/archive/master.zip",
     "https://github.com/Sniffleupagus/pwnagotchi_plugins/archive/master.zip",
     "https://github.com/NeonLightning/pwny/archive/master.zip",
     "https://github.com/marbasec/UPSLite_Plugin_1_3/archive/master.zip",
     "https://github.com/wpa-2/Pwnagotchi-Plugins/archive/master.zip",
     "https://github.com/cyberartemio/wardriver-pwnagotchi-plugin/archive/main.zip",
     "https://github.com/AlienMajik/pwnagotchi_plugins/archive/refs/heads/main.zip"
   ]
   main.custom_plugins = "/etc/pwnagotchi/custom-plugins/"
   ```

2. **Install the Plugin**
   ```bash
   sudo pwnagotchi update plugins
   sudo pwnagotchi plugins install skyhigh
   ```

#### Manual Way (Alternative)
1. **Clone the Repository**
   ```bash
   sudo git clone https://github.com/AlienMajik/pwnagotchi_plugins.git
   cd pwnagotchi_plugins
   ```
2. **Copy the Plugin File**
   ```bash
   sudo cp skyhigh.py /etc/pwnagotchi/custom-plugins/
   ```
   Or via SCP from another machine:
   ```bash
   scp skyhigh.py root@<pwnagotchi_ip>:/etc/pwnagotchi/custom-plugins/
   ```

### Configure the Plugin
Edit `/etc/pwnagotchi/config.toml` and add/enable the SkyHigh section:
```toml
main.plugins.skyhigh.enabled = true
main.plugins.skyhigh.timer = 60                  # Fetch interval in seconds
main.plugins.skyhigh.aircraft_file = "/root/handshakes/skyhigh_aircraft.json"
main.plugins.skyhigh.adsb_x_coord = 160          # Screen position X
main.plugins.skyhigh.adsb_y_coord = 80           # Screen position Y
main.plugins.skyhigh.latitude = -66.273334       # Default latitude
main.plugins.skyhigh.longitude = 100.984166      # Default longitude
main.plugins.skyhigh.radius = 50                 # Search radius in miles
main.plugins.skyhigh.prune_minutes = 5           # Prune after X minutes (0 to disable)
main.plugins.skyhigh.blocklist = []              # ICAO24 codes to exclude
main.plugins.skyhigh.allowlist = []              # ICAO24 codes to include only
main.plugins.skyhigh.opensky_username = "your_username"   # Optional
main.plugins.skyhigh.opensky_password = "your_password"   # Optional
main.plugins.skyhigh.metadata_cache_expiry_days = 7        # New
main.plugins.skyhigh.disable_metadata = false             # New
main.plugins.skyhigh.map_tile_url = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"  # New
```
For newer Pwnagotchi images (such as jayofelony 2.9.5.4 and later), use the modern bracketed TOML table format:

```toml
[main.plugins.skyhigh]
enabled = true
timer = 60                  # Fetch interval in seconds
aircraft_file = "/root/handshakes/skyhigh_aircraft.json"
adsb_x_coord = 120          # Screen position X
adsb_y_coord = 50           # Screen position Y
latitude = 37.717683        # Default latitude (fallback if no GPS)
longitude = -122.439393     # Default longitude (fallback if no GPS)
radius = 150                # Search radius in miles
prune_minutes = 10          # Prune after X minutes (0 to disable)
blocklist = []              # ICAO24 codes to exclude
allowlist = []              # ICAO24 codes to include only
opensky_username = ""       # Optional
opensky_password = ""       # Optional
metadata_cache_expiry_days = 7
disable_metadata = false
map_tile_url = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
```

Older images still support the legacy flat format, but the bracketed style is recommended for compatibility with current and future versions.

### Enable GPS (Optional)
```toml
main.plugins.gps.enabled = true
main.plugins.gps.device = "/dev/ttyUSB0"   # Adjust as needed
```

### Restart Pwnagotchi
```bash
pwnkill
```
or
```bash
sudo systemctl restart pwnagotchi
```

## Usage
### On-Screen Display
The Pwnagotchi screen shows the current aircraft count, last update time, and any error messages.

### Webhook Access
1. Browse to `http://<pwnagotchi-ip>/plugins/skyhigh/`  
2. Or click the plugin link from the main Pwnagotchi plugins page.

The map uses distinct icons: helicopters (red), commercial jets (blue), small planes (yellow), drones (purple), gliders (orange), military (green). Use the filter form to narrow by callsign, model, altitude, or type—matching markers automatically hide/show on the map.

## Configuration Options
- **timer:** Fetch interval in seconds (default: 60)
- **aircraft_file:** Path for persistent aircraft data
- **adsb_x_coord / adsb_y_coord:** On-screen position
- **latitude / longitude:** Static fallback coordinates
- **radius:** Search radius in miles
- **prune_minutes:** Remove aircraft unseen for X minutes (default: 5, 0 disables)
- **blocklist / allowlist:** Filter by ICAO24 codes
- **opensky_username / opensky_password:** For authenticated API access
- **metadata_cache_expiry_days:** Refresh cache after X days (default: 7)
- **disable_metadata:** Skip metadata fetches entirely
- **map_tile_url:** Custom Leaflet tile provider

## Known Issues and Solutions
### Transient Network Errors
Temporary API or connectivity issues may cause brief errors, but the background thread recovers automatically on the next cycle. Persistent issues usually indicate network problems.

## Why You'll Love It
- **Real-Time Situational Awareness:** Track nearby aircraft with accurate type categorization and a clean, filterable interface.
- **Highly Customizable:** Fine-tune everything from map appearance to metadata behavior.
- **Robust and Efficient:** Smarter caching, fallbacks, and pruning mean fewer errors and lower resource use.
- **Community-Enhanced:** Cleaner code and extensible patterns make it ready for future contributions.
- **Powerful Web UI:** Synchronized filtering turns the map into a practical monitoring tool.

Take your Pwnagotchi to the skies with SkyHigh! ✈️

This plugin fetches nearby aircraft data using the OpenSky Network API.  
**Acknowledgment:** Aircraft data provided by the OpenSky Network.  
**Disclaimer:** This plugin is not affiliated with OpenSky Network. Data is used in accordance with their API terms.

# MadHatter Plugin
**Version:** 1.3.4  
**Author:** AlienMajik (with community enhancements)

## Description
A fully universal and highly accurate UPS plugin for Pwnagotchi, delivering precise battery monitoring, real-time current-based estimates (where supported), dynamic runtime and charge-time prediction, persistent health tracking, robust error resilience, and graceful auto-shutdown.

Supports a wide range of popular UPS HATs with reliable auto-detection:
- Geekworm X1200 / UPS Lite (MAX170xx fuel gauge)
- Waveshare UPS, Seengreat, SB Components, EP-0136, and all other INA219-based boards (addresses 0x40–0x43)
- PiSugar series
- Geekworm X750 (IP5310)

The plugin provides smoother SOC curves, current-based charging detection, dynamic time-to-full estimates, low-battery icons, persistent cycle counting across reboots, on-screen error alerts, and extensive bug fixes — all in a clean, customizable UI.

## Key Stats
The plugin displays essential battery information directly on the Pwnagotchi screen:

### Battery Capacity (🔋 % or 🪫 %)
- Accurate state-of-charge from fuel gauge chips (MAX170xx, PiSugar) or advanced linear-interpolated voltage table (INA219).
- Automatically switches to low-battery icon 🪫 when capacity drops below 20%.

### Voltage (V)
- Real-time battery voltage shown to two decimal places (e.g., 4.20V).
- Optional via `show_voltage`.

### Charging Status (+ / - / ⚡)
- '+' with ⚡ icon when charging, '-' when discharging.
- Detected via GPIO (MAX170xx boards), real current direction (INA219), or dedicated registers (PiSugar/X750).

### Estimated Time
- Dynamic runtime on battery: `~Xm` minutes remaining.
- Dynamic time-to-full when charging (INA219 boards): `↑Xm` minutes to 100%.
- Uses real measured current when available (INA219); falls back to configured `avg_current_ma` for other boards.

### Battery Health & Diagnostics (debug mode)
- Persistent charge cycle count saved to `/root/.mad_hatter_cycle_count` (survives reboots/shutdowns).
- I2C read error counter.
- Current draw in mA when significant.

## New Enhancements in v1.3.4 
Compared to v1.2.2, the 1.3.4 series introduces major accuracy, usability, and reliability improvements:

## V1.3.4: Fixed by adding the exact same byte swap (struct.unpack("<H", struct.pack(">H", read))[0]) to:

- INA219 bus voltage reading → now shows real ~4.xxV (matches your INA219.py script).
- INA219 current reading → more accurate charging detection and dynamic time estimates.
  
- **Faster & More Reliable Detection:**
  - Scans only known I2C addresses for quicker startup.
  - Expanded INA219 support to addresses 0x40–0x43 (adds full compatibility with Seengreat and other variants).
  - Unified "ina219_generic" type for all INA219 boards with current-based charging detection (no GPIO required).

- **Superior INA219 SOC Estimation:**
  - Upgraded from lookup table to linear interpolation between finer voltage points for smoother, more accurate percentage changes.

- **Dynamic Time Estimation Using Real Current:**
  - INA219 boards now use actual measured current for highly accurate `~Xm` (runtime) and new `↑Xm` (time-to-full when charging > ~30mA).
  - Falls back gracefully to configured average for non-INA219 boards.

- **Visual UI Improvements:**
  - Low-battery icon 🪫 below 20%.
  - Voltage displayed to two decimal places.
  - On-screen "UPS ERR" alert after excessive read failures (>10).

- **Persistent Cycle Counting:**
  - Cycle count now saved to file on unload and loaded on startup — survives reboots and crashes (previously in-memory only).

- **Enhanced Error Resilience & Bug Fixes:**
  - Fixed quick-start initialization for MAX170xx boards.
  - Resolved UnboundLocalError crashes during UI updates.
  - Safer GPIO handling and cleanup.
  - Improved retry logic and last-value caching.

- **Cleaner Code & Default Behaviors:**
  - Reduced duplication and better structure.
  - Automatic default GPIO fallback for MAX170xx boards if not configured.
  - Robust `charging_gpio = null` handling (required for INA219 boards).

- **Retained & Refined Features from v1.2.2:**
  - All previous enhancements (lookup table SOC, extended cycle counting, optimized shutdown, improved detection, etc.) are preserved and built upon.

## Features
- **Universal HAT Support:** Auto-detects and optimally configures MAX170xx, INA219 (all variants), PiSugar, and IP5310-based HATs.
- **Accurate Monitoring:** Direct fuel-gauge reads where available, interpolated voltage SOC for INA219, real-time voltage.
- **Smart Charging Detection:** Current-based (INA219), GPIO-based (MAX170xx), or register-based (PiSugar/X750).
- **Dynamic Runtime Prediction:** Real current when possible, configurable fallback.
- **UI Integration:** Clean display with icons (🔋/🪫/⚡), optional voltage, time estimates, and debug info.
- **Auto-Shutdown Mechanism:** Immediate shutdown below 2%, grace-based below threshold, resets on charging/recovery.
- **Warning System:** Logs low-battery and warning-threshold alerts.
- **Health Tracking:** Persistent cycle counting, chip alerts (MAX170xx), error monitoring.
- **Efficient Polling:** Configurable interval with retries and caching for reliability.
- **Customizable Everything:** Thresholds, positions, icons, debug mode, and manual override.
- **Debug Tools:** Verbose logging, on-screen errors/cycles/current.

## Installation Instructions
### Copy the Plugin File
Place `mad_hatter.py` in `/etc/pwnagotchi/custom-plugins/`.
Or use SCP:
```bash
sudo scp mad_hatter.py root@<pwnagotchi_ip>:/etc/pwnagotchi/custom-plugins/
```

### Config Example (`config.toml`) Use the **bracketed config.toml format** below (required on newer image 2.9.5.4):
```toml
[main.plugins.mad_hatter]
enabled = true
show_voltage = true # Shows voltage like "4.20V 95%⚡"
shutdown_enabled = false
shutdown_threshold = 5
warning_threshold = 15
shutdown_grace = 3
shutdown_grace_period = 30
poll_interval = 10
ui_position_x = 150 # Adjust to your preference
ui_position_y = 0
show_icon = true
battery_mah = 7000 # Good if you have a larger pack; adjust to your actual capacity
avg_current_ma = 400 # Reasonable average draw for pwnagotchi + display
debug_mode = false # Set to true temporarily if you want extra log info
charging_gpio = null # ← IMPORTANT: null (no quotes) for INA219 boards
alert_threshold = 10
ups_type = "auto" # Will correctly detect your Seengreat board at 0x43
```

### Update config.toml
Add (or update) in `/etc/pwnagotchi/config.toml` (flat style shown; nested sections also work):
```toml
main.plugins.mad_hatter.enabled = true
main.plugins.mad_hatter.show_voltage = false
main.plugins.mad_hatter.shutdown_enabled = false
main.plugins.mad_hatter.shutdown_threshold = 5
main.plugins.mad_hatter.warning_threshold = 15
main.plugins.mad_hatter.shutdown_grace = 3
main.plugins.mad_hatter.shutdown_grace_period = 30
main.plugins.mad_hatter.poll_interval = 10
main.plugins.mad_hatter.ui_position_x = null
main.plugins.mad_hatter.ui_position_y = 0
main.plugins.mad_hatter.show_icon = true
main.plugins.mad_hatter.battery_mah = 2000
main.plugins.mad_hatter.avg_current_ma = 200
main.plugins.mad_hatter.debug_mode = false
main.plugins.mad_hatter.charging_gpio = null
main.plugins.mad_hatter.alert_threshold = 10
main.plugins.mad_hatter.ups_type = "auto"
```

### MadHatter Plugin Configuration Options
## main.plugins.mad_hatter.show_voltage = false
Shows battery voltage to two decimals (e.g., "4.20V") in the UI. (Default: false)

## main.plugins.mad_hatter.shutdown_enabled = false
Enables safe auto-shutdown on low battery. (Default: false)

## main.plugins.mad_hatter.shutdown_threshold = 5
Critical capacity % for shutdown trigger (when discharging). (Default: 5)

## main.plugins.mad_hatter.warning_threshold = 15
Capacity % for logged low-battery warnings. (Default: 15)

## main.plugins.mad_hatter.shutdown_grace = 3
Consecutive low readings required before shutdown. (Default: 3)

## main.plugins.mad_hatter.shutdown_grace_period = 30
Minimum seconds low condition must persist after grace count. (Default: 30)

## main.plugins.mad_hatter.poll_interval = 10
Seconds between hardware polls (cached values used in between). (Default: 10)

## main.plugins.mad_hatter.ui_position_x = null
X position (null = auto right-aligned). (Default: null)

## main.plugins.mad_hatter.ui_position_y = 0
Y position (0 = top). (Default: 0)

## main.plugins.mad_hatter.show_icon = true
Shows 🔋/🪫 and ⚡ icons. (Default: true)

## main.plugins.mad_hatter.battery_mah = 2000
Battery capacity in mAh for time estimates. (Default: 2000)

## main.plugins.mad_hatter.avg_current_ma = 200
Fallback average draw in mA (used when real current unavailable). (Default: 200)

## main.plugins.mad_hatter.debug_mode = false
Appends error count, cycle count, and current (mA) to UI. (Default: false)

## main.plugins.mad_hatter.charging_gpio = null
GPIO pin for charging detection (null = auto/current-based for INA219). (Default: null)

## main.plugins.mad_hatter.alert_threshold = 10
Low-battery alert threshold for MAX170xx chips. (Default: 10)

## main.plugins.mad_hatter.ups_type = "auto"
HAT type ("auto" recommended). (Default: "auto")

### Restart Pwnagotchi
```bash
sudo systemctl restart pwnagotchi
```

## Usage
- **Monitor Battery:** Watch capacity, voltage, charging, and dynamic time estimates on screen.
- **Auto-Shutdown:** Enable for protection against deep discharge.
- **Customize UI:** Tweak position, icons, voltage display, and debug info.
- **Health Tracking:** Enable debug_mode to view persistent cycles and errors.
- **Accurate Estimates:** Set correct `battery_mah`; INA219 users get real-current precision automatically.
- **Troubleshooting:** Check logs for [MadHatter]/[MadHatterUPS] entries.

## Logs and Data
- **System Logs:** Detailed events, detection, polls, warnings, and errors prefixed [MadHatter] / [MadHatterUPS] (view via `journalctl -u pwnagotchi`).
- **Persistent Data:** Cycle count saved to `/root/.mad_hatter_cycle_count`; all other stats read live with in-memory caching.
---

# TheyLive — advanced GPS plugin for Pwnagotchi

**v2.2.2** — rich real-time GPS on the display, per-handshake location tagging, continuous track
logging, GPX/GeoJSON export, and Bettercap integration. Originally based on `gpsd-easy` by
discord@rai68, enhanced by AlienMajik.

---

## Verified against Pwnagotchi 2.9.5.8

Checked line-by-line against the [v2.9.5.8](https://github.com/jayofelony/pwnagotchi/releases/tag/v2.9.5.8)
source. Four things in the 2.1.0 plugin are wrong on this image and are fixed in 2.2.1:

| Issue on 2.9.5.8 | Fix |
| --- | --- |
| **Handshakes are `.pcapng`, not `.pcap`.** `filename.replace(".pcap", ".gps.json")` produced `foo.pcapng.gps.json`; `webgpsmap` strips `.pcapng` and looks for `foo.gps.json`, so **every tagged position was invisible on the map**. | Both `.pcapng` and `.pcap` suffixes are stripped correctly. |
| **`on_loaded` runs on its own thread**, while every other callback is serialised on the plugin's `PluginEventQueue`. The old `while not self.loaded: sleep(0.1)` at the top of `on_ui_setup` therefore parked the plugin's *entire* event queue for the whole gpsd install — no `on_ready`, no `on_handshake` tagging, for up to 10 minutes. | Option parsing is idempotent and lock-guarded, called from `on_loaded`, `on_ui_setup` and `on_ready`; nothing waits on anything. |
| **`View.add_element` flips non-zero colours when `ui.invert` is set**, and `BLACK` is `0xFF` on this image (the module global is rewritten to `0x00` on invert). Second-guessing that from `config['ui']['invert']` is fragile. | Colour is read live from `pwnagotchi.ui.view.BLACK` at element-creation time — exactly what the core widgets do. |
| **`agent.session()` is an HTTP GET returning a fresh dict.** The PwnDroid backend wrote `agent.session()['gps'] = …` on every WebSocket message: a Bettercap round-trip per message, mutating a throwaway object. | Removed entirely. Position still reaches captures through `.gps.json` files. |

Also matched to core: `LabeledValue.draw()` places the value at
`x + label_spacing + 5 * len(label)` regardless of font metrics, so labels are shifted by that
exact amount — every value now starts precisely on `topleft_x` (verified: all 10 fields land on
x=130). `View.has_element()` is not used, because in 2.9.5.8 it is missing its `return` and
always yields `None`.

## Troubleshooting: "gpsd installation failed"

If the log shows `gpsd installation failed` followed by endless
`connect to 127.0.0.1:2947 failed: [Errno 111] Connection refused`, 2.2.2 now tells you why
instead of looping silently. Three causes, in order of likelihood:

1. **gpsd is already installed but wasn't detected.** `shutil.which("gpsd")` misses it when
   `/usr/sbin` isn't on the launcher's PATH. 2.2.2 also checks `/usr/sbin/gpsd`,
   `/usr/local/sbin/gpsd`, `/usr/bin/gpsd` and `dpkg-query`, and logs the path it settles on
   (`Using gpsd at /usr/sbin/gpsd`).
2. **No usable internet for apt.** The unit can be tethered enough to pass a connectivity probe
   while the Debian mirrors are unreachable. The real apt error is now logged, and the install is
   retried automatically via `on_internet_available` once the unit is properly online.
3. **apt/dpkg lock held** by the boot-time updater. Again, now visible in the log; just retry.

To fix it by hand:

```bash
sudo apt-get update && sudo apt-get install -y gpsd gpsd-clients
sudo systemctl restart pwnagotchi
```

After three failed connects the plugin logs a single actionable summary — whether gpsd is
installed, whether the service is active, the last lines of its journal, and whether your
configured `device` exists (listing the `/dev/tty*` candidates it can see if it doesn't).

## What's new in 2.2.2

### Bugs fixed

| Fix | Why it mattered |
| --- | --- |
| **gpsd reader no longer busy-loops on EOF** | When gpsd died or the USB GPS was unplugged, `readline()` returned `''` forever and the old loop spun a core at 100%, draining the battery and starving the UI thread. |
| **Automatic gpsd reconnection** | Previously, if gpsd wasn't up during the 5 initial attempts (very common right after `systemctl restart gpsd`), the plugin gave up permanently until a reboot. Now it reconnects with exponential backoff, forever. |
| **Stale fixes are no longer served as live data** | The last TPV was cached indefinitely, so after signal loss the screen kept showing the old position — and worse, that ghost position was written into handshake `.gps.json` files and the track log. Fixes older than `max_fix_age` are now discarded. |
| **`NameError` in PwnDroid reconnect path** | `asyncio` was imported inside `_start_fetch_loop`, so `await asyncio.sleep(5)` in the error handler of `_fetch_loop` raised `NameError` and killed the retry loop on the first disconnect. `asyncio` is now imported at module scope. |
| **`websockets` is imported lazily** | A missing `websockets` package broke the whole plugin at import time, even in server/peer mode where it isn't used. |
| **Old gpsd releases supported** | Altitude now falls back `altMSL` → `alt` → `altHAE`; gpsd < 3.20 only reports `alt`, so altitude silently read as 0. |
| **Invalid systemd unit** | `/etc/default/gpsd` contained `/bin/stty ...` and `/bin/setserial ...` lines, which systemd rejects in an `EnvironmentFile` (it only accepts `KEY=VALUE`). Those calls moved to `ExecStartPre=-`. |
| **No more event-queue stall on `apt-get install`** | `setup()` ran inline in `on_loaded()`, and `on_ui_setup`/`on_ready` blocked waiting for it — freezing this plugin's event queue (and handshake tagging) for the whole install. Setup now runs in a background thread. |
| **`mode: 1` is "no fix", not a fix** | gpsd mode 1 means *no fix*; the old code displayed it as "Fix". |
| **Handshake filename rewriting** | `filename.replace(".pcap", ...)` corrupted paths containing `.pcap` elsewhere; only the suffix is replaced now. |
| **UI element name collisions** | Every element is namespaced `theylive_*`, so `lat`, `sat`, `fix`, `mode` etc. can never clash with core Pwnagotchi elements or another plugin's. |
| **`agent.session()` hammering** | The PwnDroid backend wrote to `agent.session()` on *every* WebSocket message — each call is an HTTP round-trip to Bettercap. Now throttled to once per 30s. |
| **bettercap GPS is retried, not attempted once** | `on_ready` fires before gpsd finishes starting, so `set gps.device` got `connection refused` and GPS tagging stayed off for the entire session. It is now retried from the worker until gpsd is genuinely reachable. |
| **gpsd install failures are non-fatal and explained** | A failed `apt-get` aborted setup with no reason logged and no retry. The apt error is logged, configuration continues if the binary exists, and the install is retried when the unit comes online. |
| **gpsd no longer stopped on unload by default** | Stopping `gpsd.service` when the plugin unloaded broke every other GPS consumer. Opt back in with `stop_gpsd_on_unload`. |
| **Config validation** | Bad `mode`, `speedUnit`, `distanceUnit`, `fields`, or non-numeric ports now log a warning and fall back instead of raising mid-loop. |
| **Idempotent setup** | gpsd config files are only rewritten (and gpsd only restarted) when the contents actually change. |
| **Pillow 10 compatibility** | Label width measurement uses `getlength()` with a `getsize()` fallback. |
| **Track file rotation** | The NDJSON log grew without limit; it now rotates at `track_max_mb`. |

### New features

- **`dist` field** — session odometer (km or miles) computed from the track.
- **`pdop` / `vdop` fields** in addition to `hdop`.
- **Smarter status line** — `Starting`, `No gpsd` / `No link` when the backend is down, `Acq 4/9`
  while acquiring, `Good 3D`, `3D (1.4)`, `3D ±8m` (PwnDroid accuracy), `2D fix`, `No fix`.
- **Distance-based track logging** — points are only written when you've actually moved
  `track_min_distance` metres, with a heartbeat every `track_max_gap` seconds. A parked
  Pwnagotchi no longer writes 8,640 identical points a day.
- **Handshakes in the track log** (`track_handshakes`) with SSID/BSSID/channel, so a single file
  contains both your route and your captures.
- **Web UI + exports** at `http://<pwnagotchi>:8080/plugins/theylive/`:
  live status page, `…/gpx` (GPX 1.1) and `…/geojson` (route LineString + handshake points) —
  drop straight into Google Earth, gpx.studio, QGIS or geojson.io.
- **True value alignment** — labels are measured in pixels and right-aligned so all values line up.
- **Richer handshake JSON** — adds `Accuracy`, `Fix`, `Satellites`, `Updated`
  (webgpsmap/WiGLE-friendly).
- **gpsd binds to localhost by default** — set `gpsd_listen_all = true` to expose 2947 on the LAN.

---

## Requirements

- A GPS source: USB/serial GPS (optional PPS), a remote gpsd, or an Android phone running
  PwnDroid/ShareGPS.
- Internet on first run if you want `auto = true` to install gpsd.
- `websockets` (PwnDroid mode only): `sudo pip3 install websockets`.

## Installation

**Plugin repo (recommended)**

```toml
main.custom_plugin_repos = [
    "https://github.com/AlienMajik/pwnagotchi_plugins/archive/refs/heads/main.zip",
]
main.custom_plugins = "/etc/pwnagotchi/custom-plugins/"
```

```bash
sudo pwnagotchi plugins update
sudo pwnagotchi plugins install theylive
```

**Manual**

```bash
scp theylive.py root@<pwnagotchi_ip>:/etc/pwnagotchi/custom-plugins/theylive.py
sudo systemctl restart pwnagotchi
```

## Configuration

```toml
[main.plugins.theylive]
enabled = true

# --- core ---------------------------------------------------------------
mode = "server"                # "server" | "peer" | "pwndroid"
device = "/dev/ttyACM0"        # serial device (server mode)
baud = 9600
auto = true                    # install/configure gpsd automatically

# --- display ------------------------------------------------------------
fields = ["gpsstat", "fix", "sat", "hdop", "lat", "lon", "alt", "spd", "trk"]
speedUnit = "kn"               # ms | kph | mph | kn
distanceUnit = "m"             # m | ft
topleft_x = 130
topleft_y = 47
spacing = 12
precision = 5                  # decimals for lat/lon (3-8)
align_values = true
min_track_speed = 1.0          # m/s below which heading is hidden

# --- bettercap ----------------------------------------------------------
bettercap = true               # ignored (forced off) in pwndroid mode

# --- gpsd / peer --------------------------------------------------------
host = "127.0.0.1"
port = 2947
max_fix_age = 10.0             # seconds before a fix counts as stale
gpsd_listen_all = false        # true = expose gpsd on 0.0.0.0:2947
stop_gpsd_on_unload = false

# --- pwndroid -----------------------------------------------------------
pwndroid_host = "192.168.44.1"
pwndroid_port = 8080

# --- track logging ------------------------------------------------------
track_log = true
track_interval = 10            # sampling interval, seconds
track_min_distance = 3.0       # metres of movement required to log a point
track_max_gap = 300            # log anyway after this many seconds
track_file = "/root/pwnagotchi_gps_track.ndjson"
track_max_mb = 32              # rotate to .1 above this size
track_handshakes = true        # also record handshakes in the track
```

On 2.9.5.3-style configs the flat form works too
(`main.plugins.theylive.mode = "server"`, …). Restart afterwards:

```bash
sudo systemctl restart pwnagotchi
```

### Available fields

| Field | Shows |
| --- | --- |
| `gpsstat` | smart fix status (`Good 3D`, `3D (1.4)`, `Acq 4/9`, `No gpsd`, …) |
| `fix` | `-` / `NF` / `2D` / `3D` |
| `sat` | used/visible satellites, e.g. `8/12` |
| `hdop`, `pdop`, `vdop` | dilution of precision |
| `lat`, `lon` | position |
| `alt` | altitude (m or ft) |
| `spd` | speed in the chosen unit |
| `trk` | heading in degrees, only while moving |
| `dist` | distance travelled this session |

### Mode notes

- **server** — local hardware. Set `device` and `baud`; auto-setup handles gpsd.
- **peer** — remote gpsd: set `host` to that machine's IP and `auto = false`
  (the remote host needs `gpsd_listen_all = true` or an equivalent gpsd config).
- **pwndroid** — set `mode = "pwndroid"` and the phone's IP/port. Bettercap GPS is
  disabled automatically; location still lands in `.gps.json` files and the track log.

## Usage

- GPS data appears at `topleft_x/topleft_y` once a fix is acquired.
- Each capture gets a sibling `<handshake>.gps.json`.
- The route accumulates as NDJSON at `track_file`.
- Status page and downloads: `http://<pwnagotchi>:8080/plugins/theylive/`
- Logs: `sudo tail -f /var/log/pwnagotchi.log | grep TheyLive`

Finding your GPS port:

```bash
ls /dev/tty*    # with the GPS unplugged
ls /dev/tty*    # plug it in, spot the new device
```

Quick sanity check of the GPS itself:

```bash
sudo systemctl status gpsd
gpsmon              # or: cgps -s
```

## Upgrading from 2.1.x

- UI element names changed to `theylive_*`. Nothing to do unless another plugin or a custom
  layout referenced them by name.
- `status` as a field name is still accepted and silently mapped to `gpsstat`.
- gpsd is no longer stopped when the plugin unloads — set `stop_gpsd_on_unload = true` for the
  old behaviour.
- gpsd now listens on localhost only; set `gpsd_listen_all = true` if another device consumed
  your Pwnagotchi's gpsd over the network.

## Credits

Original `gpsd-easy` by discord@rai68. Enhancements and maintenance by AlienMajik.
Issues and PRs welcome on GitHub.



