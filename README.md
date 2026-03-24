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
**Version:** 4.0.0

## Description
A deeply immersive, narrative-driven plugin that transforms your Pwnagotchi into a living cyber-legend. Features prestige rebirth cycles, rich lore messages, cheeky themed quotes (Evil Dead + Monty Python vibes), animated progress, expanded random events with real risk/reward, smarter personality evolution, handshake milestones, and a dedicated status display — all while keeping the UI clean and engaging.

## Key Stats
The plugin tracks core statistics that reflect your Pwnagotchi's epic journey:

### Age (♥ Age)
- Tracks the number of epochs your Pwnagotchi has lived through.
- Earns flavorful titles like "Baby Steps" (100 epochs), "Neon Spawn" (1,000 epochs), "Data Raider" (10,000 epochs), up to "Intergalactic" (111,111 epochs), and more.
- Titles gain "Reborn" prefix after prestige cycles.

### Strength (Str)
- Reflects training progress (now properly accelerated by Time Warp events).
- Titles include "Sparring Novice" (100 train epochs), "Deauth King" (2,000 epochs), "Rev-9" (55,555 epochs), "Kuato" (111,111 epochs), and beyond.
- Also prefixed with "Reborn" after prestige.

### Network Points (★ Pts)
- Earn points by capturing handshakes, scaled by encryption strength and prestige multiplier:
  - WPA3: +10 base
  - WPA2: +5 base
  - WEP/WPA: +2 base
  - Open/Unknown: +1 base
- Points decay during long inactivity periods to encourage regular use.
- Lifetime total handshakes tracked separately (survives rebirth).

### Personality
- Evolves dynamically based on playstyle:
  - **Aggro**: +1 per handshake captured.
  - **Scholar**: +1 every 10 epochs.
  - **Stealth**: +1 every epoch with **no** handshake (rewards patient, low-visibility sessions).
- Dominant trait displayed on UI if enabled.

## New Enhancements in v4.0.0
- **Prestige / Rebirth System** — Reach max age **and** max strength titles → trigger rebirth: reset core stats, gain permanent +10% point multiplier per prestige level (1.1×, 1.2×, …). **Why better**: Adds true end-game progression, replayability, and power fantasy — late-game feels exponentially more rewarding instead of plateauing.
- **Rich Narrative Lore Messages** — Poetic, atmospheric blurbs for nearly every age/strength title and event (cyberpunk + mythic tone). **Why better**: Turns dry stat gains into memorable story beats — your Pwnagotchi feels alive.
- **Themed Quote Library** — Categorized quotes (Ash one-liners for wins, Monty Python absurdity for warnings, insults for failures, ready lines for rebirth). Randomly combined with lore/status. **Why better**: Injects huge personality, humor, and immersion — status messages are now fun and quotable.
- **Dedicated AgeStatus UI Element** — New separate line (~y=140) for longer lore/quote/event messages. **Why better**: Prevents clutter and overwriting of main bettercap status; allows richer storytelling without sacrificing readability.
- **Expanded & Balanced Random Events** (every ~100 epochs, configurable chance):
  - New: Overclock (3× points, 3 handshakes), Hacker's Block (0 points, 3 handshakes), Windfall (+50 instant points), Time Warp (+10% train speed for 100 epochs), Ghost (swap aggro ↔ stealth).
  - Existing Lucky Break & Signal Noise kept.
  - Events now pull lore + quotes.
  - **Why better**: Much more variety, introduces meaningful risk/reward tension, supports different playstyles (aggressive vs patient), and helps toward rebirth.
- **Animated Progress Bar Polish** — Switches to `>` + `~` symbols when >80% to next title (visual "almost there" cue). **Why better**: Subtle but satisfying feedback that progression is nearing a milestone.
- **Smarter Personality Evolution** — Stealth now grows on quiet epochs (no handshake). **Why better**: Rewards stealthy / low-activity sessions instead of being dead weight; personality feels truly responsive.
- **Handshake Milestone Achievements** — Unlock bonuses at 1, 10, 100, 1,000 handshakes (+50 pts each). **Why better**: Extra dopamine hits and rewards for consistent capturing.
- **Time Warp Persistence & Expiry** — Saved/loaded correctly; expires cleanly. **Why better**: No lost progress on reboots; feels reliable.
- **Total Lifetime Handshakes** — Survives rebirth (separate from current-cycle count). **Why better**: Preserves your overall legacy.
- **Prestige-Aware Titles & Points Display** — Multiplier applied to UI points; "Reborn" prefix. **Why better**: Instantly shows your ascended status.
- **Improved Event & Achievement Messaging** — Uses new AgeStatus + quotes/lore. **Why better**: More immersive announcements.

(Kept & refined from v3.1.0: frequent titles, context-aware dynamic messages, progress bar, streaks (20% bonus at 5+), secret achievements (Night Owl, Crypto King), decay, logging, thread-safe persistence, UI optimization.)

## Features
- **Persistent Stats** — Age, Strength, Points, Personality, Prestige, Achievements, Events survive reboots.
- **UI Integration** — Clean stats, animated progress, personality (optional), dedicated AgeStatus line.
- **Points Logging** — `/root/network_points.log` (timestamp, ESSID, encryption, points).
- **Decay Mechanism** — Encourages daily/regular use with inactivity penalties.
- **Dynamic & Themed Messages** — Lore, quotes, face reactions for titles, events, decay, rebirth.
- **Prestige Cycles** — Reset + permanent multiplier for endless progression.
- **Random Events** — Spice up gameplay with buffs, debuffs, instant rewards, time acceleration, personality swaps.
- **Handshake Streaks & Milestones** — Consecutive & total-count bonuses.
- **Personality Evolution** — Action-based growth; dominant trait shown optionally.
- **Secret & Milestone Achievements** — Hidden goals + visible count-based unlocks for bonus points.

## Installation Instructions
### Copy the Plugin File
Place `age.py` in `/usr/local/share/pwnagotchi/custom-plugins/`.
Or use SCP:
```bash
sudo scp age.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/
```

### Update config.toml
Add to `/etc/pwnagotchi/config.toml`:
```toml
main.plugins.age.enabled = true
main.plugins.age.age_x_coord = 10
main.plugins.age.age_y_coord = 40
main.plugins.age.strength_x_coord = 80
main.plugins.age.strength_y_coord = 40
main.plugins.age.points_x_coord = 10
main.plugins.age.points_y_coord = 60
main.plugins.age.progress_x_coord = 10
main.plugins.age.progress_y_coord = 80
main.plugins.age.personality_x_coord = 10
main.plugins.age.personality_y_coord = 100
main.plugins.age.age_status_x_coord = 10
main.plugins.age.age_status_y_coord = 140          # new
main.plugins.age.show_personality = true
main.plugins.age.decay_interval = 50
main.plugins.age.decay_amount = 10
main.plugins.age.random_event_chance = 0.05        # new, adjustable
```

### Confi.toml bracketed format for Jayofelony image 2.9.5.4:
Add to `/etc/pwnagotchi/config.toml`:
```toml
[main.plugins.age]
age_x_coord = 101
age_y_coord = 80
strength_x_coord = 160
strength_y_coord = 80
points_x_coord = 10
points_y_coord = 60
progress_x_coord = 10
progress_y_coord = 100
personality_x_coord = 10
personality_y_coord = 120
age_status_x_coord = 10
age_status_y_coord = 140
decay_interval = 50
decay_amount = 5
show_personality = false
enabled = true
```

### Restart Pwnagotchi
Apply changes with:
```bash
sudo systemctl restart pwnagotchi
```

## Usage
- **Monitor Stats** — Watch Age, Strength, Points (with prestige multiplier), and progress evolve.
- **Capture Handshakes** — Build streaks, unlock milestones, earn bonus points.
- **Track Progress** — Animated bar shows closeness to next title.
- **Experience Events** — Enjoy (or suffer) random windfalls, overclocks, blocks, time warps, ghosts.
- **Develop Personality** — Play aggressive or stealthy — trait shifts accordingly.
- **Unlock Achievements** — Discover secrets and hit count milestones.
- **Trigger Rebirth** — Max out → transcend, gain permanent power boost.
- **Avoid Decay** — Stay active to keep points safe.
- **Enjoy the Lore** — Read narrative blurbs and cheeky quotes on every milestone.

## Logs and Data
- **Stats Data:** `/root/age_strength.json`  
  Stores epochs, train_epochs, points, handshakes (current + lifetime), prestige, personality, achievements, active events, etc.
- **Points Log:** `/root/network_points.log`  
  Records each handshake with timestamp, ESSID, encryption, points earned.

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

``` 
# SnoopR Plugin

Welcome to **SnoopR**, the most advanced surveillance-detection and wardriving plugin for **Pwnagotchi**! SnoopR turns your pocket-sized AI companion into a powerful multi-modal sensor that logs Wi-Fi, Bluetooth/BLE, and even overhead aircraft, while intelligently identifying potential tails or persistent trackers through movement, velocity, spatial clustering, and RSSI-based positioning.

This release (**v6.0.0**) is a complete architectural overhaul and major feature upgrade from v5.1.0. It adds full geofencing, advanced aircraft behavioral anomaly detection with OpenSky metadata integration, real-time threat alerts via SSE, SciPy-accelerated trilateration, efficient recent-device-only analysis, richer web UI with anomalies column and map overlays, and dozens of stability/performance improvements. These changes transform SnoopR from a smart logger into a true real-time surveillance detection platform.

Key enhancements and fixes over previous versions (and why they’re better):
- **Full geofencing system (new)** – Supports configurable circle and polygon zones. Aircraft are automatically checked against all zones; breaches appear as anomalies in logs, UI, and KML. Visualized directly on the Leaflet map. Turns SnoopR into a true geofenced alarm system — impossible in v5.1.0.
- **Advanced aircraft anomaly detection (new)** – Real-time behavioral analysis including low altitude, circling/loitering (convex-hull diameter), rapid climb/descent, speed anomalies, emergency squawk codes (7500/7600/7700), and sharp turns. Uses per-aircraft track history. Far more powerful than the simple position logging in v5.1.0.
- **OpenSky Network integration (new)** – Automatic async lookup of aircraft registration, typecode, and owner with 30-day SQLite cache. Rich metadata instead of just “UNKNOWN”.
- **Real-time threat alerts via SSE (new)** – Dedicated `/alerts` endpoint with floating red alert box that auto-dismisses after 5 seconds. Live pop-up notifications for squawks, geofence breaches, circling, etc.
- **SciPy-accelerated trilateration (new)** – Uses `scipy.optimize.minimize` (Nelder-Mead) when available, with pure-Python fallback. Faster and more robust position estimates.
- **Efficient recent-device analysis** – PersistenceAnalyzer now only processes devices seen in the last `analysis_days` (default 7). Combined with new `last_seen` column and index, dramatically reduces CPU and DB load on long runs.
- **Enhanced web UI** – New “Anomalies” column, purple markers for anomalous aircraft, geofence overlays on map, improved KML export that includes anomalies.
- **Improved geometry engine** – Added `haversine_miles`, `convex_hull`, `polygon_diameter`, and `point_in_polygon` helpers for accurate circling and clustering.
- **Better KalmanFilter** – Explicit `initialize()` on first measurement for more accurate early RSSI smoothing.
- **MeshNetwork improvements** – Cleaner constructor, better crypto warnings, and more robust error handling.
- **Database enhancements** – New `aircraft_info` table, `last_seen` column + index, `update_anomalies()` method, CTE-based `get_all_networks` for faster latest-position queries.
- **Config warnings** – Automatic logging when plaintext mesh keys or WiGLE credentials are used (security nudge).
- **Robustness everywhere** – More specific exception handling, OUI fallback path, aircraft file existence warning, and protected cursor usage in all analysis paths.
- **Config compatibility** – Still supports both legacy flat keys and modern nested tables (especially for jayofelony custom images).

## Features
- **Multi-source detection**: Wi-Fi APs + clients, Bluetooth/BLE (with manufacturer data), ADS-B aircraft.
- **Geofencing**: Circle and polygon zones with real-time breach detection and map visualization.
- **Intelligent persistence scoring**: Recent activity windows, cluster bonuses, configurable threshold.
- **Hybrid snooper flagging**: Persistence + movement + velocity.
- **RSSI triangulation**: Estimated position + MSE for Wi-Fi/BLE (now SciPy-accelerated when available).
- **Spatial clustering**: ~100m zone counting to detect repeated locations.
- **Vendor & classification**: OUI + Bluetooth company IDs + heuristics.
- **Advanced aircraft tracking**: OpenSky metadata, behavioral anomaly detection (circling, squawks, vertical speed, etc.), smart caching.
- **Modern BLE scanning**: Configurable async Bleak scanner.
- **Encrypted mesh**: Optional real-time sharing.
- **WiGLE fallback**: SSID geolocation.
- **Kalman-smoothed RSSI**: Cleaner distance estimates.
- **Rich web interface**: Trails, heatmap, anomalies column, geofence overlays, KML export, dark mode, live SSE counts + threat alerts, search, sorting, filters.
- **Pwnagotchi UI counters**: Wi-Fi, BT, Aircraft, Snoopers, High Persistence.
- **Whitelisting**: SSID/MAC.
- **Automatic pruning**: With VACUUM.
- **Robust logging & error handling**.

## Requirements & Dependencies
### Core Requirements
- **GPS** via Bettercap (gps plugin recommended).
- **Bluetooth** enabled (`sudo hciconfig hci0 up` or your interface).
- **Internet on viewing device** for map tiles/Leaflet and OpenSky lookups.
- **aircraft.json** file (for ADS-B feed — still required).

### Python Dependencies (Recommended for Full Features)
```bash
sudo pip3 install bleak cryptography scipy
```
or use system packages if pip fails:
```bash
sudo apt install python3-bleak python3-cryptography python3-scipy
```
- `bleak`: Modern BLE scanning.
- `cryptography`: Mesh encryption.
- `scipy`: Faster Nelder-Mead trilateration (optional — pure Python fallback included).

### Vendor Databases
SnoopR automatically downloads the Bluetooth company identifiers database on first run if missing. For Wi-Fi vendor lookup, the Wireshark OUI database is preferred.

**Recommended (automatic OUI via package):**
```bash
sudo apt update && sudo apt install wireshark-common
```

**Manual Download Options** (use if `apt` is unavailable or for offline setup):
- **Bluetooth Company Identifiers** (manually download to the configured path, default `/root/snoopr/company_identifiers.json`):
  ```bash
  sudo mkdir -p /root/snoopr
  sudo wget -O /root/snoopr/company_identifiers.json https://raw.githubusercontent.com/NordicSemiconductor/bluetooth-numbers-database/master/v1/company_ids.json
  ```
- **Wireshark OUI Database** (manually download if wireshark-common not installed):
  ```bash
  sudo wget -O /usr/share/wireshark/manuf https://www.wireshark.org/download/automated/data/manuf
  ```
- **ADS-B feed** (required for aircraft): Tool outputting valid `aircraft.json`.
- **WiGLE API keys** (optional): For fallback geolocation.
- **OpenSky credentials** (optional but recommended for rich aircraft metadata): Free account at opensky-network.org.

## Installation Instructions
Manual installation recommended (advanced dependencies):

```bash
cd /usr/local/share/pwnagotchi/custom-plugins/
sudo wget https://raw.githubusercontent.com/AlienMajik/pwnagotchi_plugins/main/snoopr.py
```

Or clone:

```bash
sudo git clone https://github.com/AlienMajik/pwnagotchi_plugins.git /tmp/pwnplugins
sudo cp /tmp/pwnplugins/snoopr.py /usr/local/share/pwnagotchi/custom-plugins/
sudo rm -rf /tmp/pwnplugins
```

Install dependencies:

```bash
sudo pip3 install bleak cryptography scipy
sudo apt install wireshark-common
```

Restart:

```bash
sudo systemctl restart pwnagotchi
```

## Configuration
SnoopR supports both legacy flat config keys (for standard Pwnagotchi) and modern nested tables (optimized for jayofelony custom images like 2.9.5.4).

### Legacy Flat Format (Standard Pwnagotchi Compatibility)
```toml
main.plugins.snoopr.enabled = true
main.plugins.snoopr.base_dir = "/root/snoopr"
main.plugins.snoopr.aircraft_file = "/root/aircraft.json"
main.plugins.snoopr.scan_interval = 10
main.plugins.snoopr.scan_duration = 5
main.plugins.snoopr.bluetooth_enabled = true
main.plugins.snoopr.log_without_gps = false
main.plugins.snoopr.whitelist_ssids = ["MyHomeWiFi", "MyPhone"]
main.plugins.snoopr.whitelist_macs = []
main.plugins.snoopr.prune_days = 30
main.plugins.snoopr.ui_enabled = true
main.plugins.snoopr.mesh_enabled = false
main.plugins.snoopr.movement_threshold = 0.8
main.plugins.snoopr.time_threshold_minutes = 20
main.plugins.snoopr.persistence_threshold = 0.85
main.plugins.snoopr.triangulation_min_points = 8
main.plugins.snoopr.mse_threshold = 75
main.plugins.snoopr.update_interval = 300
main.plugins.snoopr.analysis_days = 7
main.plugins.snoopr.aircraft_high_altitude_threshold = 300
main.plugins.snoopr.aircraft_circling_radius = 500
main.plugins.snoopr.aircraft_circling_time = 120
main.plugins.snoopr.aircraft_rapid_descent_threshold = 3000
main.plugins.snoopr.aircraft_rapid_climb_threshold = 3000
main.plugins.snoopr.aircraft_max_speed_knots = 600
main.plugins.snoopr.aircraft_min_speed_knots = 50
main.plugins.snoopr.aircraft_enable_squawk_alerts = true
main.plugins.snoopr.opensky_username = ""
main.plugins.snoopr.opensky_password = ""
```

### Modern Nested Format (jayofelony 2.9.5.4 Image & Newer)
```toml
[main.plugins.snoopr]
enabled = true
base_dir = "/root/snoopr"
aircraft_file = "/root/handshakes/skyhigh_aircraft.json"
scan_interval = 10
scan_duration = 5
bluetooth_enabled = true
bluetooth_device = "hci1"
log_without_gps = false
whitelist_ssids = ["MyHomeWiFi", "MyPhone"]
whitelist_macs = []
prune_days = 7
mesh_enabled = false
mesh_host = "0.0.0.0"
mesh_port = 8888
mesh_peers = []
mesh_key = ""
ui_enabled = true
tx_power_wifi = -20
tx_power_bt = -20
path_loss_n_wifi = 2.7
path_loss_n_bt = 2.7
mse_threshold = 75
triangulation_min_points = 8
persistence_threshold = 0.85
movement_threshold = 0.8
time_threshold_minutes = 20
update_interval = 300
analysis_days = 7
aircraft_high_altitude_threshold = 300
aircraft_circling_radius = 500
aircraft_circling_time = 120
aircraft_rapid_descent_threshold = 3000
aircraft_rapid_climb_threshold = 3000
aircraft_max_speed_knots = 600
aircraft_min_speed_knots = 50
aircraft_enable_squawk_alerts = true
opensky_username = ""
opensky_password = ""

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

Both formats work — use the one matching your image. Restart after changes.

## Database Schema Updates
On startup, SnoopR checks and migrates the database schema automatically, adding any missing columns (e.g., `channel`, `auth_mode`, `triangulated_lat`, `last_seen`, `anomalies`) with ALTER TABLE. New `aircraft_info` table is created for OpenSky metadata. Indexes are created for faster queries on `network_id`, `mac`, `timestamp`, and `last_seen`.

## Usage
Runs automatically on boot.
- Wi-Fi/BLE/aircraft logged with full details and anomalies.
- Background analysis updates persistence, velocity, clusters, triangulation, snooper flags, and aircraft-specific behavior.
- Web UI: `http://<pwnagotchi_ip>:8080/plugins/snoopr/` — trails, heatmap, anomalies column, geofence overlays, live counts + threat alerts, KML export.

## Notes
- Database: `<base_dir>/snoopr.db`.
- Triangulated positions prioritized on map.
- High Persistence uses `persistence_threshold`.
- Bluetooth company DB auto-downloaded if missing (or manually as above).
- OUI database loaded from Wireshark path if available (or manually downloaded).
- SSE live updates and threat alerts visible in browser console.
- Geofences and aircraft anomalies appear in real time.

## Community and Contributions
Community-driven and evolving fast. Issues/PRs welcome on GitHub!

## Disclaimer
For educational and security testing only. Respect privacy and local laws. Use responsibly!

✅ What’s New in v6.0.0
1. Complete geofencing engine with circle/polygon support, map visualization, and automatic anomaly logging.
2. Advanced aircraft behavioral anomaly detection (circling via convex hull, squawk emergencies, rapid vertical maneuvers, speed/heading anomalies).
3. OpenSky Network metadata integration with 30-day caching for registration, type, and owner.
4. Real-time SSE threat alert system with floating red pop-up box.
5. SciPy-accelerated trilateration with pure-Python fallback.
6. Efficient recent-device-only analysis (last 7 days by default) + new `last_seen` indexing.
7. New “Anomalies” column and purple aircraft markers in web UI.
8. Geofence overlays rendered directly on the Leaflet map.
9. KML export now includes anomaly descriptions.
10. Improved KalmanFilter, geometry helpers, MeshNetwork constructor, and error handling throughout.
11. Version bumped to 6.0.0 to reflect the major feature expansion and performance overhaul.
```

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
   main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins/"
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
   sudo cp skyhigh.py /usr/local/share/pwnagotchi/custom-plugins/
   ```
   Or via SCP from another machine:
   ```bash
   scp skyhigh.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/
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
Place `mad_hatter.py` in `/usr/local/share/pwnagotchi/custom-plugins/`.
Or use SCP:
```bash
sudo scp mad_hatter.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/
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

# TheyLive Plugin

Welcome to TheyLive, the most advanced and robust GPS plugin for Pwnagotchi! Originally created by rai68 and significantly enhanced by AlienMajik, TheyLive transforms your Pwnagotchi into a powerful wardriving tool with rich real-time GPS data on the display, precise per-handshake location logging, continuous track logging for full route mapping, and seamless Bettercap integration.

**Version 2.1.0** delivers major enhancements: a conflict-free smart GPS status line (`gpsstat` with text like "Good 3D" or "3D (1.4)"), HDOP accuracy reporting, used/visible satellite counts, heading/track display (only when moving), knots speed unit, continuous NDJSON track logging (enabled by default), E-ink-friendly updates (only refresh changed values), precise unit conversions, heading in handshake logs, and permanent resolution of the core status line conflict. It’s fully compatible with the latest jayofelony Pwnagotchi images, with robust auto-setup, PPS support, and excellent reliability across USB/serial GPS, remote sharing, and mobile modes.

## Features

TheyLive provides a comprehensive GPS integration suite. Here’s what it delivers:

- **Rich Real-Time GPS Display**: Fully customizable fields including:
  - `gpsstat` – Smart fix status ("Good 3D" if HDOP < 2.0, "3D (hdop)", "2D fix", "No fix", etc.) with short "stat:" label
  - `fix` – Dimensional fix type (2D/3D)
  - `sat` – Used/visible satellites (e.g., "8/12")
  - `hdop` – Horizontal dilution of precision (accuracy indicator)
  - `lat` / `lon` – Latitude and longitude
  - `alt` – Altitude
  - `spd` – Speed
  - `trk` – Heading/track in degrees (shown only when speed > 1 m/s)
- **Unit Support**: Speed in m/s, kph, mph, **or knots**; altitude in m or ft (with precise conversions).
- **Per-Handshake Logging**: Saves `.gps.json` files alongside each `.pcap` with latitude, longitude, altitude, speed, **and heading/track**.
- **Continuous Track Logging** (New & Enabled by Default): Logs full movement tracks every 10 seconds (configurable) to `/root/pwnagotchi_gps_track.ndjson` – NDJSON format with timestamp, lat, lon, alt, speed, track, and hdop. Ideal for wardriving and route mapping.
- **E-Ink Optimizations**: Only updates changed values, reducing flicker and extending display lifespan.
- **Bettercap Integration**: Enables GPS tagging in captures (server/peer modes; disabled in PwnDroid).
- **Multi-Mode Support**:
  - **Server**: Local USB/serial GPS hardware
  - **Peer**: Remote gpsd sharing from another device
  - **PwnDroid**: Android GPS via WebSocket over Bluetooth tether (with keep-alive pings)
- **Robust Auto-Setup**: Installs/configures gpsd with multi-endpoint internet checks, baud rate, device, and PPS support.
- **No Core UI Conflicts**: `gpsstat` field uses a unique element name – preserves Pwnagotchi’s bottom status line (e.g., "Ready.", AI messages).
- **Enhanced Reliability**: Thread-safe data access, detailed error logging, graceful reconnects, and comprehensive fallbacks.

## Requirements

- GPS source: USB/serial GPS (optional PPS), remote gpsd server, or Android phone with GPS-sharing app (PwnDroid/ShareGPS).
- Initial internet access recommended for gpsd auto-install.
- Tested on latest jayofelony Pwnagotchi images.

## Installation Instructions

### Easy Way (Recommended)

1. Add the repository to `/etc/pwnagotchi/config.toml` (if not present):

```toml
main.custom_plugin_repos = [
    "https://github.com/AlienMajik/pwnagotchi_plugins/archive/refs/heads/main.zip",
    # ... your other repositories ...
]
main.custom_plugins = "/usr/local/share/pwnagotchi/custom-plugins/"
```

2. Install:

```bash
sudo pwnagotchi plugins update
sudo pwnagotchi plugins install theylive
```

### Manual Way

```bash
sudo scp theylive.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/available-plugins/theylive.py
sudo pwnagotchi plugins install theylive
```

## Configuration

Enable and customize in `/etc/pwnagotchi/config.toml`:

```toml
# Config Example 2.9.5.3 image config.toml format:

main.plugins.theylive.enabled = true

# Core settings
main.plugins.theylive.mode = "server"          # "server", "peer", or "pwndroid"
main.plugins.theylive.device = "/dev/ttyACM0"  # Serial device (server mode)
main.plugins.theylive.baud = 9600              # Baud rate
main.plugins.theylive.auto = true              # Auto-install/configure gpsd

main.plugins.theylive.fields = [
    "gpsstat",  # Smart fix status – safe, no core conflict
    "fix",
    "sat",
    "hdop",
    "lat",
    "lon",
    "alt",
    "spd",
    "trk"
]
main.plugins.theylive.speedUnit = "kn"         # ms, kph, mph, kn
main.plugins.theylive.distanceUnit = "m"       # m, ft
main.plugins.theylive.topleft_x = 130
main.plugins.theylive.topleft_y = 47

# Bettercap
main.plugins.theylive.bettercap = true         # false in pwndroid mode

# Mode-specific
main.plugins.theylive.host = "127.0.0.1"
main.plugins.theylive.port = 2947
main.plugins.theylive.pwndroid_host = "192.168.44.1"
main.plugins.theylive.pwndroid_port = 8080

# Continuous track logging
main.plugins.theylive.track_log = true
main.plugins.theylive.track_interval = 10      # seconds
main.plugins.theylive.track_file = "/root/pwnagotchi_gps_track.ndjson"

### Config Example (`config.toml`) Use the **bracketed config.toml format** below (required on newer image 2.9.5.4):

[main.plugins.theylive]
enabled = true
device = "/dev/ttyACM0"
baud = 115200
fields = ["gpsstat", "fix", "sat", "hdop", "lat", "lon", "alt", "spd", "trk"]
speedUnit = "mph"
distanceUnit = "m"
bettercap = true
auto = true
mode = "server"
topleft_x = 130
topleft_y = 47
track_log = true
track_interval = 10
track_file = "/root/pwnagotchi_gps_track.ndjson"
```

Restart after changes:

```bash
sudo systemctl restart pwnagotchi
```

### Mode-Specific Notes

- **Server**: Local hardware – set `device`, `baud`. Auto-setup runs if needed.
- **Peer**: Remote gpsd – set `host` to server IP, `auto = false`.
- **PwnDroid**: Android sharing – `mode = "pwndroid"`, `bettercap = false`, correct phone IP/port.

## Usage

- GPS data appears in the configured position once a fix is acquired.
- Per-handshake `.gps.json` files are saved with captures.
- Continuous track log (if enabled) accumulates in `/root/` as NDJSON – perfect for importing into mapping tools.
- Detailed activity in `/var/log/pwnagotchi.log`.

## Notes

- First boot with `auto = true` in server mode may take 5–10 minutes to install gpsd (requires internet).
- To find your GPS device port:

```bash
ls /dev/tty*   # unplug GPS, run this
# plug GPS in
ls /dev/tty*   # note the new device
```

- The previous `status` field conflict is fully resolved with `gpstat`.

## Community and Contributions

Originally based on gpsd-easy by rai68. Major enhancements and maintenance by AlienMajik.

- Report issues, suggest features, or submit PRs on the GitHub repository.
- Join the Pwnagotchi community for support and ideas.

Enjoy precise, rich GPS wardriving with TheyLive!

```



