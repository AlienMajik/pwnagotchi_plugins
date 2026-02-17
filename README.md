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

**Version:** 3.1.0

## Description

An enhanced plugin with frequent titles, dynamic quotes, progress bars, random events, handshake streaks, personality evolution, and secret achievements. The UI is optimized to avoid clutter, ensuring a clean and engaging experience.

## Key Stats

The plugin tracks four primary statistics that reflect your Pwnagotchi's journey:

### Age (♥ Age)
- Tracks the number of epochs your Pwnagotchi has lived.  
- Earns frequent titles like "Baby Steps" (100 epochs), "Getting the Hang of It" (500 epochs), "Neon Spawn" (1,000 epochs), and more.

### Strength (Str)
- Reflects training progress, increasing by 1 every 10 epochs.  
- Titles include "Sparring Novice" (100 train epochs), "Gear Tickler" (300 train epochs), "Fleshbag" (500 train epochs), and beyond.

### Network Points (★ Pts)
- Earn points by capturing handshakes, with values based on encryption strength:  
  - WPA3: +10 points  
  - WPA2: +5 points  
  - WEP/WPA: +2 points  
  - Open/Unknown: +1 point
- Points decay if the Pwnagotchi is inactive for too long.

### Personality
- Develops based on actions:
  - Aggro: Increases with each handshake.  
  - Scholar: Increases every 10 epochs.  
  - Stealth: Reserved for future use.
- Displayed on the UI if enabled.

## New Enhancements in v3.1.0

- **More Frequent Titles:** Age and strength titles are awarded more often, making progression feel rewarding at every stage. 
- **Context-Aware Dynamic Quotes:** Motivational messages respond to your actions, like capturing handshakes or recovering from decay. 
- **Progress Bars:** A visual bar shows how close you are to the next age title (e.g., [===  ] for 60% progress).  
- **Random Events:** Every 100 epochs, there's a 5% chance of events like "Lucky Break" (double points) or "Signal Noise" (half points).  
- **Handshake Streaks:** Capture 5+ consecutive handshakes for a 20% point bonus per handshake.  
- **Personality Evolution:** Your Pwnagotchi's dominant trait (Aggro, Scholar, Stealth) evolves based on its actions.  
- **Secret Achievements:** Unlock hidden goals like "Night Owl" (10 handshakes between 2-4 AM) or "Crypto King" (capture all encryption types) for bonus points. 
- **UI Optimization:** Streamlined to avoid clutter; personality display is optional.  
- **Enhanced Data Persistence:** Saves streak, personality, and achievement progress.  
- **Thread Safety:** Ensures reliable data saving.  
- **Improved Logging:** Detailed logs for better tracking and debugging.

## Features

- **Persistent Stats:** Age, Strength, Points, and Personality survive reboots.  
- **UI Integration:** Stats, progress bars, and messages are displayed on the screen.  
- **Points Logging:** Handshake events are logged in `/root/network_points.log`.  
- **Decay Mechanism:** Points decay after inactivity to encourage regular use.  
- **Dynamic Status Messages:** Context-aware quotes and inactivity alerts.  
- **Personality Evolution:** Develops based on actions; display optional.  
- **Secret Achievements:** Hidden goals for bonus points.  
- **Random Events:** Periodic events that spice up gameplay. 
- **Handshake Streaks:** Bonus points for consecutive captures.

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
main.plugins.age.age_x = 10
main.plugins.age.age_y = 40
main.plugins.age.strength_x = 80
main.plugins.age.strength_y = 40
main.plugins.age.points_x = 10
main.plugins.age.points_y = 60
main.plugins.age.progress_x = 10
main.plugins.age.progress_y = 80
main.plugins.age.personality_x = 10
main.plugins.age.personality_y = 100
main.plugins.age.show_personality = true
main.plugins.age.decay_interval = 50
main.plugins.age.decay_amount = 10
```

### Restart Pwnagotchi  
Apply changes with:  
```bash
sudo systemctl restart pwnagotchi
```

## Usage

- **Monitor Stats:** Watch Age, Strength, and Points increase on the screen. 
- **Capture Handshakes:** Earn points and build streaks for bonuses.  
- **Track Progress:** See how close you are to the next age title with the progress bar. 
- **Experience Events:** Encounter random events that affect point earnings. 
- **Develop Personality:** Your Pwnagotchi's actions shape its dominant trait. 
- **Unlock Achievements:** Discover secret goals for extra points.  
- **Avoid Decay:** Stay active to prevent point loss from inactivity.

## Logs and Data

- **Stats Data:** `/root/age_strength.json`  
  Stores epochs, train_epochs, points, handshakes, personality, and more.
- **Points Log:** `/root/network_points.log`  
  Records each handshake with timestamp, ESSID, encryption, and points.

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

**Version:** 1.6.0

## Overview

The Neurolyzer plugin has evolved into a powerful tool for enhancing the stealth and privacy of your Pwnagotchi. Now at version 1.6.0, it goes beyond simple MAC address randomization to provide a comprehensive suite of features that minimize your device's detectability by network monitoring systems, Wireless Intrusion Detection/Prevention Systems (WIDS/WIPS), and other security measures. By reducing its digital footprint while scanning networks, Neurolyzer ensures your Pwnagotchi operates discreetly and efficiently. This update introduces adaptive stealth levels based on environmental factors (e.g., number of nearby APs), improved compatibility with Raspberry Pi 5 via Nexmon detection for monitor mode and potential packet injection, SSID whitelisting to avoid targeting trusted networks, deauthentication throttling for balanced aggression, and an expanded list of realistic OUIs for better blending.

## Key Features and Improvements

### 1. Advanced WIDS/WIPS Evasion
- **What's New:** A sophisticated system to detect and evade WIDS/WIPS.
- **How It Works:** Scans for known WIDS/WIPS SSIDs (e.g., "wids-guardian", "airdefense") and triggers evasion tactics like MAC address rotation, channel hopping, TX power adjustments, and random delays.
- **What's Better:** Proactively avoids detection in secured environments, making your Pwnagotchi stealthier than ever.

### 2. Hardware-Aware Adaptive Countermeasures
- **What's New:** Adapts to your device's hardware capabilities, now with explicit detection for Broadcom chipsets (e.g., Raspberry Pi 5's CYW43455) and Nexmon patches.
- **How It Works:** Detects support for TX power control, monitor mode, MAC spoofing, and packet injection at startup, tailoring operations accordingly. If Nexmon is detected on Broadcom hardware, enables monitor mode, 5GHz channels, and injection features.
- **What's Better:** Ensures compatibility and stability across diverse Pwnagotchi setups, including Raspberry Pi 5, avoiding errors from unsupported features and enabling advanced capabilities with patches.
  
### 3. Atomic MAC Rotation with Locking Mechanism
- **What's Improved:** MAC changes are now atomic, using an exclusive lock.
- **How It Works:** A lock file prevents conflicts during MAC updates, ensuring smooth execution.
- **What's Better:** Enhances reliability, especially on resource-constrained devices or with multiple plugins.

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

### 6. Robust Command Execution with Retries and FThis updated version (2.0.0) brings a host of new features, including richer data collection, smarter snooper detection, whitelisting, automatic data pruning, and an improved web interface. It's actively developed, community-driven, and packed with capabilities to help you explore and secure your wireless environment. Let's dive into what SnoopR can do and how you can get started!allbacks
- **What's Improved:** Enhanced reliability for system commands.
- **How It Works:** Retries failed commands and uses alternatives (e.g., iwconfig if iw fails).
- **What's Better:** Increases stability across varied setups, fixing issues from inconsistent command execution.

### 7. Traffic Throttling for Stealth
- **What's New:** Limits network traffic in noided mode.
- **How It Works:** Uses tc to shape packet rates, mimicking normal activity.
- **What's Better:** Avoids triggering rate-based WIDS/WIPS alarms, a leap beyond basic MAC randomization.

### 8. Probe Request Sanitization
- **What's New:** Filters sensitive probe requests.
- **How It Works:** Blacklists identifiable probes using tools like hcxdumptool.
- **What's Better:** Hides your device's identity, adding a privacy layer absent in earlier versions.

### 9. Enhanced UI Integration
- **What's Improved:** Displays detailed status on the Pwnagotchi UI.
- **How It Works:** Shows mode, next MAC change time, TX power, and channel. The positions for all these labels are fully customizable in `config.toml`.
- **What's Better:** Offers real-time monitoring, improving on the basic UI updates of past releases.

### 10. Improved Error Handling and Logging
- **What's Improved:** Better logging and adaptive error responses.
- **How It Works:** Logs detailed errors/warnings and adjusts to hardware limits.
- **What's Better:** Easier troubleshooting and more reliable operation than before.

### 11. Safe Channel Hopping
- **What's New:** Implements safe, regular channel switching.
- **How It Works:** Uses safe channels (e.g., 1, 6, 11) or dynamically detected ones.
- **What's Better:** Reduces detection risk by avoiding static channel use.

### 12. TX Power Adjustment
- **What's New:** Randomizes transmission power in noided mode.
- **How It Works:** Adjusts TX power within hardware limits using iw or iwconfig.
- **What's Better:** Mimics normal device behavior, enhancing stealth over static signal strength.

### 13. Comprehensive Cleanup on Unload
- **What's Improved:** Restores default settings when disabled.
- **How It Works:** Resets traffic shaping, monitor mode, and releases locks.
- **What's Better:** Leaves your device stable post-use, unlike earlier versions with minimal cleanup.

### 14. Adaptive Stealth Levels
- **What's New:** Dynamically adjusts stealth based on environment.
- **How It Works:** Levels 1-3: Aggressive (high TX/deauth in quiet areas) to passive (low TX/deauth in crowds), adapting MAC intervals, TX power, channel hops, and deauth throttle based on AP count.
- **What's Better:** Balances handshake farming with evasion, making operations smarter and less detectable.

### 15. SSID Whitelisting and Deauth Throttling
- **What's New:** Avoids targeting trusted networks and controls deauth rate.
- **How It Works:** Filters whitelisted SSIDs from deauth targets; throttles deauth (20-80% based on stealth) if packet injection supported (e.g., via Nexmon).
- **What's Better:** Prevents accidental disruption of home/office networks while reducing WIPS triggers from excessive deauths.

### 16. Nexmon Integration for Raspberry Pi 5
- **What's New:** Automatic detection and enablement for Broadcom chipsets.
- **How It Works:** Checks for Nexmon patches; enables monitor mode, packet injection (where supported), and 5GHz channels on compatible hardware like Pi 5's bcm43455c0.
- **What's Better:** Overcomes native limitations on Pi 5 for full evasion features, with fallback to passive mode if unpatched.
- 
## Legacy Improvements Retained and Enhanced

- **Initial MAC Randomization:** Randomizes the MAC address on load for immediate privacy.
- **Monitor Mode Handling:** Temporarily switches to managed mode for MAC changes, then back to monitor mode; enhanced with interface recreation for stability.
- **Time-Dependent Randomization:** Dynamically calculates MAC change schedules for unpredictability, now adaptive to stealth level.

## Other Features

- **Varied Operational Modes:** Choose normal, stealth, or noided to match your needs.
- **Wi-Fi Interface Customization:** Supports custom interface names for flexibility.
- **Comprehensive Logging:** Tracks events and errors for easy monitoring.
- **Seamless Activation/Deactivation:** Auto-starts when enabled, ensuring smooth transitions.

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
    main.plugins.neurolyzer.wifi_interface = "wlan0mon"  # Your wireless adapter
    main.plugins.neurolyzer.operation_mode = "noided"    # 'normal', 'stealth', or 'noided'
    main.plugins.neurolyzer.mac_change_interval = 3600   # Seconds
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
    main.plugins.neurolyzer.stealth_level = 2  # Optional: Initial stealth level (1=aggressive, 2=medium, 3=passive); still adapts dynamically

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
   [INFO] [Thread-24 (run_once)] : [Neurolyzer] Plugin loaded. Operating in noided mode.
   [INFO] [Thread-24 (run_once)] : [Neurolyzer] MAC address changed to xx:xx:xx:xx:xx:xx for wlan0mon via macchanger.
   ```

## Known Issues

- **Wi-Fi Adapter Compatibility:** Works best with external adapters. It now works for Raspberry Pi 5's built-in Broadcom CYW43455 chip, not sure if it works on other stock wifi chipset pi models. Please share feedback! If it works well on other Pi models.

## Summary

Neurolyzer 1.6.0 elevates Pwnagotchi's stealth and privacy with advanced WIDS/WIPS evasion, hardware-aware operations (including Pi 5 Nexmon support), realistic MAC generation, adaptive modes, and new features like dynamic stealth levels and whitelisting. Compared to 1.5.2, it offers smarter environmental adaptation, better reliability on modern hardware, deeper evasion (throttled deauth, 5GHz hopping), and enhanced usability (UI stealth display). Whether you're testing security or keeping a low profile, Neurolyzer 1.6.0 is a significant upgrade—more versatile, intelligent, and robust than ever.

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
**Version:** 1.9.1

### Recent Update (v1.9.1)
- **Reliable Scapy Installation**
  Enhanced auto-install logic: now prefers apt install python3-scapy (system package, safe on Bookworm/Trixie) before falling back to pip — eliminates PEP 668 issues on newer images.
- **Fixed status line position resets on restart**  
  Uses dedicated pnp_status element with configurable position — no more conflicts/resets with tweakview or other plugins (e.g., theylive).
  The new line is fully movable with tweakview and persists across reboots.  
  Configurable via:
  ```toml
  min_assoc_prob = 0.9
  main.plugins.probenpwn.pnp_status_x_coord = 130
  main.plugins.probenpwn.pnp_status_y_coord = 47

### Compatibility with jayofelony Image 2.9.5.4 (Debian Trixie)
ProbeNpwn v1.9.1 is fully compatible with the latest jayofelony image (2.9.5.4), which is based on Debian Trixie.  
Benefits on this image:
- Reliable Scapy installation (via `apt` — no PEP 668 issues)
- Improved monitor mode/injection stability for PMF bypass attacks
- Faster Python 3.12 performance

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
verbose = true
enable_5ghz = true
enable_6ghz = true
max_retries = 5
gps_history_size = 10
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
enable_bad_msg = true
enable_assoc_sleep = true
```


**Educational and Research Tool Only**  
This plugin is provided strictly for **Educational purposes, Security research, and Authorized penetration testing**. It must only be used on networks and devices you own or have explicit written permission to test. Unauthorized use is illegal under laws such as the Computer Fraud and Abuse Act (CFAA) in the United States and equivalent legislation worldwide. The author and contributors are not responsible for any misuse or legal consequences.

## Overview
ProbeNpwn is the ultimate aggressive handshake capture plugin for Pwnagotchi—an evolved powerhouse built on the legacy of Instattack, now supercharged with cutting-edge intelligence and PMF bypass capabilities! Version 1.9.1 delivers **Adaptive Mode** (auto-switches between tactical and maniac based on success/density), **UCB1 exploration/exploitation channel hopping**, **Full multi-band support** (2.4/5/6 GHz), **PMF bypass attacks** (Bad Msg & Association Sleep via Scapy), **Automatic Scapy installation**, **Persistent failure blacklist**, **JSON capture logging**, **smarter UI updates**, **RSSI-based delay caching**, and refined mobility scaling for maximum performance in any environment. With continuous mobility detection (GPS + AP rate → 0-1 score), dynamic personality/autotune scaling, intelligent retries, concurrency safety, and tweakview-compatible custom status line, ProbeNpwn captures handshakes faster, smarter, and more reliably than ever—especially on modern protected networks.

## Key Features
- **Triple Modes (Tactical, Maniac, Adaptive):**
  Tactical for smart efficiency, Maniac for unrestricted chaos, and new **Adaptive** that auto-switches based on success rate/density.
- **PMF Bypass Attacks (Bad Msg & Association Sleep):**
  Bypass 802.11w-protected networks with malformed EAPOL Msg1 and power-save spoofing—automatically preferred when PMF detected (requires Scapy, auto-installed).
- **UCB1 Intelligent Channel Hopping:**
  True exploration/exploitation balancing activity, success history, and bonuses for PMKID-potential channels.
- **Multi-Band Support (2.4/5/6 GHz):**
  Seamless hopping across bands (configurable), with unique channel lists for stability.
- **Dynamic Mobility Scaling:**
  Continuous 0-1 mobility score (GPS Haversine + AP discovery rate) scales recon_time, TTLs, probs, RSSI thresholds, and throttles—inverted for aggression when mobile.
- **Aggressive Deauth + Association:**
  Parallel attacks with conditional probabilities, forced assoc on client-less APs for PMKID focus, and dynamic throttles.
- **Concurrency & Stability:**
  Dynamic thread workers (CPU/load-based), executor locks, runtime error handling, persistent blacklist for failing APs, heap/LRU cleanup.
- **Smart UI & Logging:**
  Attacks/success/handshakes/mobility stats with change-threshold updates; configurable custom status line (tweakview-safe); JSON handshake logging.
- **Reliable Scapy Installation**
  Enhanced auto-install: prefers system package (apt install python3-scapy) then pip fallback; provides clear on-screen and log feedback
- **Comprehensive Safety:**
  Whitelist support, early RSSI filtering, retry queue, cooldowns, watchdog recovery, pycache clearing.

## What's New in ProbeNpwn v1.9.1?
This release pushes ProbeNpwn to new heights with **Adaptive Intelligence**, **PMF bypass superpowers**, **True ML-style hopping**, and user-friendly enhancements—making it unstoppable on modern Wi-Fi networks.

### 1. Adaptive Mode (Auto-Switch Tactical/Maniac)
**What's New:**
Third mode "adaptive" automatically ramps aggression based on real-time performance.
**How It Works:**
- Every 10 epochs, evaluates success rate and network density.
- Switches to Maniac if low success/high density; back to Tactical if improving/low density.
**Why It's Better:**
- Hands-free optimization: Starts smart, goes full beast mode only when needed—perfect for varying environments.

### 2. PMF Bypass Attacks (Bad Msg + Association Sleep)
**What's New:**
Two advanced DoS techniques to disconnect clients on 802.11w-protected networks.
**How It Works:**
- Auto-detects PMF-required APs (`mfpr=True`).
- Prefers bypass over standard deauth: Bad Msg (malformed EAPOL Msg1) + Assoc Sleep (power-save spoof).
- Falls back to deauth on non-PMF; always attempts PMKID assoc.
**Why It's Better:**
- Cracks modern protected networks where deauth fails—massive handshake boost on enterprise/modern home Wi-Fi.

### 3. UCB1 Channel Hopping (Exploration/Exploitation)
**What's New:**
Replaced weighted random with true UCB1 algorithm.
**How It Works:**
- Balances proven success (exploitation) with untried channels (exploration) + activity bonus.
**Why It's Better:**
- Smarter, faster convergence on best channels—especially in dense/multi-band areas.

### 4. Persistent Blacklist
**What's New:**
Configurable auto-blacklist for chronic failures.
**How It Works:**
- Blacklists APs with high attempts/low success for 1 hour.
**Why It's Better:**
- Prioritizes high-yield clients; avoids wasting time on stubborn APs.
  

### 5. 6GHz Support + Auto-Scapy Install
**What's New:**
Full 6GHz channel list + automatic Scapy installation on first load.
**How It Works:**
- Config flag for 6GHz; unique channel merging.
- Detects missing Scapy → pip installs → prompts restart.
**Why It's Better:**
- Future-proof for Wi-Fi 6E; zero manual setup for PMF attacks.

### 6. JSON Logging, Smarter UI, RSSI Delay Cache
**What's New:**
Per-handshake JSON logs; change-threshold UI updates; RSSI-adjusted delay TTL.
**How It Works:**
- Logs to `/root/handshakes/probenpwn_captures.jsonl`.
- UI only refreshes on meaningful changes.
- Delay cache TTL scales with signal strength.
**Why It's Better:**
- Easy post-analysis; less screen flicker; smarter pacing on weak signals.

### 7. Custom Configurable Status Line
**What's New:**
Overrides core status with own element + config coords.
**How It Works:**
- `status_x_coord` / `status_y_coord` for positioning.
- tweakview-safe (no resets on restarts).
**Why It's Better:**
- Full tweakview compatibility—move status freely without conflicts.

### 8. Reliable Scapy Installation
- Prioritizes apt for system package (avoids PEP 668 issues on Bookworm/Trixie), with pip fallback.

## Why You'll Love It
ProbeNpwn v1.9.1 is the smartest, most aggressive handshake plugin yet:
- **Adaptive Intelligence:** Auto-tunes aggression for any scenario.
- **PMF Slayer:** Bypasses modern protections others can't touch.
- **Future-Proof:** 6GHz, UCB1 hopping, vendor smarts.
- **User-Friendly:** Auto-Scapy, JSON logs, tweakview-safe UI.
- **Relentless & Stable:** Blacklists failures, dynamic everything, rock-solid concurrency.

Big thanks to the Pwnagotchi community and original Instattack creators—this evolution wouldn't be possible without you! 🙏

## How to Get Started
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
```toml
main.plugins.probenpwn.enabled = true
main.plugins.probenpwn.mode = "adaptive"           # tactical/maniac/adaptive
main.plugins.probenpwn.attacks_x_coord = 110
main.plugins.probenpwn.attacks_y_coord = 20
main.plugins.probenpwn.success_x_coord = 110
main.plugins.probenpwn.success_y_coord = 30
main.plugins.probenpwn.handshakes_x_coord = 110
main.plugins.probenpwn.handshakes_y_coord = 40
main.plugins.probenpwn.pnp_status_x_coord = 130   # Hotfix 1.7.1 changed from core status to its own
main.plugins.probenpwn.pnp_status_y_coord = 47    # Hotfix 1.7.1 changed from core status to its own
main.plugins.probenpwn.verbose = true
main.plugins.probenpwn.enable_5ghz = true
main.plugins.probenpwn.enable_6ghz = false         # Only if Wi-Fi 6E hardware
main.plugins.probenpwn.enable_bad_msg = true       # PMF bypass
main.plugins.probenpwn.enable_assoc_sleep = true   # PMF bypass
main.plugins.probenpwn.max_retries = 5
main.plugins.probenpwn.gps_history_size = 10
main.plugins.probenpwn.env_check_interval = 3
main.plugins.probenpwn.min_recon_time = 2
main.plugins.probenpwn.max_recon_time = 30
main.plugins.probenpwn.min_ap_ttl = 30
main.plugins.probenpwn.max_ap_ttl = 300
main.plugins.probenpwn.min_sta_ttl = 30
main.plugins.probenpwn.max_sta_ttl = 300
main.plugins.probenpwn.min_deauth_prob = 0.9
main.plugins.probenpwn.max_deauth_prob = 1.0
main.plugins.probenpwn.min_assoc_prob = 0.9
main.plugins.probenpwn.max_assoc_prob = 1.0
main.plugins.probenpwn.min_min_rssi = -85
main.plugins.probenpwn.max_min_rssi = -60
main.plugins.probenpwn.min_throttle_a = 0.1
main.plugins.probenpwn.max_throttle_a = 0.2
main.plugins.probenpwn.min_throttle_d = 0.1
main.plugins.probenpwn.max_throttle_d = 0.2
```

Restart: `sudo systemctl restart pwnagotchi`

## Pro Tip 💡
Start with **adaptive mode**—it handles everything automatically. Enable the PMF bypass attacks (Bad Msg & Association Sleep) to dominate modern 802.11w-protected networks—they're based on the brilliant research by Mathy Vanhoef in his WISEC 2022 paper (huge thanks for the groundbreaking techniques!). Keep 6GHz off unless you have compatible hardware(6E wifi adapters only!!). Watch the custom status line for Scapy install prompts!
https://papers.mathyvanhoef.com/wisec2022.pdf

## Disclaimer
## This software is provided for educational and research purposes only. Use of this plugin on networks or devices that you do not own or have explicit permission to test is strictly prohibited. The author(s) and contributors are not responsible for any misuse, damages, or legal consequences that may result from unauthorized or improper usage. By using this plugin, you agree to assume all risks and take full responsibility for ensuring that all applicable laws and regulations are followed.

# SnoopR Plugin

Welcome to **SnoopR**, the most advanced surveillance-detection and wardriving plugin for **Pwnagotchi**! SnoopR turns your pocket-sized AI companion into a powerful multi-modal sensor that logs Wi-Fi, Bluetooth/BLE, and even overhead aircraft, while intelligently identifying potential tails or persistent trackers through movement, velocity, spatial clustering, and RSSI-based positioning.

This major release (**v5.0.0**) represents a complete evolution from earlier versions. What started as a solid wardriving logger has become a professional-grade surveillance detection system with real persistence scoring, multilateration triangulation, aircraft awareness, encrypted mesh collaboration, modern BLE scanning, and a rich tactical web interface.

Key enhancements and fixes over previous versions (and why they’re better):
- **Fully implemented persistence scoring + spatial clustering** – Now actively computes a 0.0–1.0 score based on recent 5-minute activity windows, repeated presence, and distinct ~100m clusters. Far superior to old crude movement checks — catches slow, lingering followers with dramatically fewer false positives/negatives.
- **Hybrid snooper detection** – Combines high persistence, configurable movement threshold, and velocity >1.5 m/s. More accurate and tunable than earlier versions.
- **RSSI-based multilateration (triangulation)** – Uses Kalman-smoothed RSSI with configurable TX power/path-loss to estimate positions. Huge improvement for indoor/urban or hidden devices where GPS alone fails.
- **Aircraft (ADS-B) integration** – Polls `aircraft.json` for overhead traffic with smart caching. Adds aerial awareness missing from all prior versions.
- **Modern BLE scanning with Bleak** – Async, reliable scanning replaces deprecated `hcitool`. Fewer errors, better device/name detection on modern kernels.
- **Encrypted mesh networking** – AES-GCM UDP sharing between units. Enables real-time collaborative detection (new capability).
- **Server-Sent Events (SSE)** – Live count updates in web UI without reloads (smoother experience).
- **Enhanced web UI** KML Export with Colored Trails – Download your entire dataset as a KML file with persistence-colored markers (green/yellow/red) and full movement trails. Load directly into Google Earth or Google My Maps for offline analysis — massively better for post-session review than the old static map view.
- **Vendor lookup & classification** – Auto-downloads Bluetooth company IDs, uses OUI db, classifies devices (Apple, wearables, etc.).
- **WiGLE fallback** – Optional SSID-based geolocation when GPS unavailable.
- **Performance & stability** – Batch upserts, proper indexing, graceful dependency handling, robust background analysis thread.
- **Config compatibility** – Supports both legacy flat keys and modern nested tables (especially for jayofelony custom images).

## Features

- **Multi-source detection**: Wi-Fi APs + clients, Bluetooth/BLE (with manufacturer data), ADS-B aircraft.
- **Intelligent persistence scoring**: Recent activity windows, cluster bonuses, configurable threshold.
- **Hybrid snooper flagging**: Persistence + movement + velocity.
- **RSSI triangulation**: Estimated position + MSE for Wi-Fi/BLE.
- **Spatial clustering**: ~100m zone counting to detect repeated locations.
- **Vendor & classification**: OUI + Bluetooth company IDs + heuristics.
- **Aircraft tracking**: Smart caching, movement-aware logging. You need SkyHigh Plugin in order for it to work!
- **Modern BLE scanning**: Configurable async Bleak scanner.
- **Encrypted mesh**: Optional real-time sharing.
- **WiGLE fallback**: SSID geolocation.
- **Kalman-smoothed RSSI**: Cleaner distance estimates.
- **Rich web interface**: Trails, heatmap, KML export, dark mode, live SSE, search, sorting, filters.
- **Pwnagotchi UI counters**: Wi-Fi, BT, Aircraft, Snoopers, High Persistence.
- **Whitelisting**: SSID/MAC.
- **Automatic pruning**: With VACUUM.
- **Robust logging & error handling**.

## Requirements & Dependencies

### Core Requirements
- **GPS** via Bettercap (gps plugin recommended).
- **Bluetooth** enabled (`sudo hciconfig hci0 up` or your interface).
- **Internet on viewing device** for map tiles/Leaflet.

### Python Dependencies (Recommended for Full Features)
```bash
sudo pip3 install bleak cryptography
```
- `bleak`: Modern BLE scanning.
- `cryptography`: Mesh encryption.

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
  sudo wget -O /root/snoopr/company_identifiers.json https://github.com/NordicSemiconductor/bluetooth-numbers-database/blob/master/v1/company_ids.json
  ```

- **Wireshark OUI Database** (manually download if wireshark-common not installed):
  ```bash
  sudo wget -O /usr/share/wireshark/manuf https://www.wireshark.org/download/automated/data/manuf
  ```

- **ADS-B feed** (optional): Tool outputting valid `aircraft.json`.
- **WiGLE API keys** (optional): For fallback geolocation.

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
sudo pip3 install bleak cryptography
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
web_user = ""
web_pass = ""
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
auto_install_deps = true

[main.plugins.snoopr.wigle]
enabled = true
api_name = ""
api_token = ""
```

Both formats work — use the one matching your image. Restart after changes.

## Usage

Runs automatically on boot.

- Wi-Fi/BLE/aircraft logged with full details.
- Background analysis updates persistence, velocity, clusters, triangulation, snooper flags.
- Web UI: `http://<pwnagotchi_ip>:8080/plugins/snoopr/` — trails, heatmap, live updates, KML export.

## Notes

- Database: `<base_dir>/snoopr.db`.
- Triangulated positions prioritized on map.
- High Persistence uses `persistence_threshold`.
- Bluetooth company DB auto-downloaded if missing (or manually as above).
- OUI database loaded from Wireshark path if available (or manually downloaded).
- SSE live updates visible in browser console (expandable later).

## Community and Contributions

Community-driven and evolving fast. Issues/PRs welcome on GitHub!

## Disclaimer

For educational and security testing only. Respect privacy and local laws. Use responsibly!
# SkyHigh Plugin

## Overview

SkyHigh is a custom plugin for Pwnagotchi that tracks nearby aircraft using the OpenSky Network API. It displays the number of detected aircraft on your Pwnagotchi's screen and provides an interactive map view via a webhook, featuring detailed aircraft types (helicopters, commercial jets, small planes, drones, gliders, military), DB flags, and flight path visualization. Distinct icons enhance the map, and a pruning feature keeps the log clean by removing outdated aircraft data.

## What’s New in Version 1.1.1

- **The updated SkyHigh plugin (version 1.1.1) introduces a range of new features and improvements that enhance its functionality, usability, and performance. Below is a detailed breakdown of what’s new and how it makes the plugin better compared to its previous version:**

- **Filtering Options in the Web Interface:** Users can now filter aircraft displayed in the web interface by callsign, model, and altitude range (minimum and maximum) using a new filter form in the HTML template.

- **Export Capabilities (CSV and KML):** Users can download data for offline analysis or integration with tools like Google Earth (KML) or spreadsheet software (CSV), adding flexibility for processing or visualizing data outside the plugin.

- **Metadata Caching:** Aircraft metadata (e.g., model, registration) is now cached in a JSON file (skyhigh_metadata.json), loaded at startup, and saved when the plugin unloads. Caching reduces repeated API calls for previously seen aircraft, improving performance and reducing network load—especially beneficial for frequent users tracking recurring aircraft. 

- **Type-Specific Icons** New map icons for commercial jets (blue), small planes (yellow), drones (purple), gliders (orange), and military aircraft (green), alongside helicopters (red).

- **Background Data Fetching** Aircraft data is now fetched in a background thread using the _fetch_loop method, rather than in the main thread. This keeps the user interface responsive during data updates, preventing freezes or delays and enhancing the overall user experience.

- **Blocklist and Allowlist Support:** New configuration options let users specify a blocklist (aircraft to exclude) and an allowlist (aircraft to include) based on ICAO24 codes.

- **Improved Type Detection:** The get_aircraft_metadata method now uses enhanced logic to categorize aircraft types (e.g., helicopters, commercial jets, small planes, drones, gliders, military) based on manufacturer names, model prefixes (like "737" or "A320"), and typecodes.

-  **Enhanced Error Handling and Feedback** The plugin now handles more API error cases (e.g., missing data, authentication failures, rate limiting) and displays error messages and the last update time in the UI.

-  **Historical Position Tracking** The plugin stores up to 10 historical positions per aircraft in the historical_positions dictionary. While not yet fully utilized in the web interface, this sets the stage for future features like flight path visualization, offering potential for richer data analysis.


## How It’s Better Overall

- **User-Friendly Interface:** The simplified table, filtering options, and export links make the web interface cleaner and more intuitive, focusing on essential data and user interaction.

- **Performance Improvements:** Background fetching and metadata caching reduce resource usage and improve responsiveness, making the plugin more efficient.
  
- **Flexibility and Control:** Features like blocklist/allowlist, filtering, and export options empower users to customize their experience and use data in diverse ways.

- **Reliability:** Enhanced error handling and embedded icons ensure consistent operation, even under suboptimal conditions.

- **Future-Ready:** Historical position tracking and improved type detection pave the way for additional features, such as flight path mapping or advanced analytics.

## How It Works

- **Data Fetching:** Queries the OpenSky API every 60 seconds (configurable) to retrieve aircraft data within the specified radius, supporting both anonymous and authenticated requests.

- **Metadata Enrichment:** Fetches detailed metadata (model, registration, DB flags, type categorization) for each aircraft using its ICAO24 code, with robust handling for missing data.

- **Flight Path Fetching:** Retrieves recent flight paths (up to 4 hours) for aircraft, falling back to locally stored historical positions if flight track access is unavailable.

- **Pruning:** Aircraft not seen within the prune_minutes interval are removed from the log to maintain efficiency.

- **UI Display:** The Pwnagotchi screen shows the number of detected aircraft, refreshed periodically.

- **Webhook Map:** The webhook (/plugins/skyhigh/) renders a table with extended aircraft details (velocity, track, squawk, etc.) and an interactive map with type-specific icons and clickable flight path visualization.

## Installation and Usage

### Prerequisites

- A Pwnagotchi device with internet access.
- GPS Adapter: For dynamic tracking, simply connect a GPS adapter to your Pwnagotchi and configure it with BetterCAP. The plugin will use real-time coordinates if available, falling back to static ones otherwise.
- (Optional) A GPS module for dynamic coordinate tracking.

### Step-by-Step Installation

You can install SkyHigh in two ways: the easy way (recommended) or the manual way. Here's how:

#### Easy Way (Recommended)

1. **Update Your Config File**
   
   Edit `/etc/pwnagotchi/config.toml` and add the following lines to enable custom plugin repositories:
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
   
   Run these commands to update the plugin list and install SkyHigh:
   ```bash
   sudo pwnagotchi update plugins
   sudo pwnagotchi plugins install skyhigh
   ```

#### Manual Way (Alternative)

If you prefer a hands-on approach:

1. **Clone the SkyHigh plugin repo from GitHub:**
   ```bash
   sudo git clone https://github.com/AlienMajik/pwnagotchi_plugins.git
   cd pwnagotchi_plugins
   ```

2. **Copy the Plugin File**
   
   Move skyhigh.py to your Pwnagotchi's custom plugins directory:
   ```bash
   sudo cp skyhigh.py /usr/local/share/pwnagotchi/custom-plugins/
   ```

   Alternatively, if you're working from a computer, use SCP:
   ```bash
   sudo scp skyhigh.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/
   ```

### Configure the Plugin

Edit your config.toml file (typically located at `/etc/pwnagotchi/config.toml`) and add the following section:

```toml
main.plugins.skyhigh.enabled = true
main.plugins.skyhigh.timer = 60  # Fetch data every 60 seconds
main.plugins.skyhigh.aircraft_file = "/root/handshakes/skyhigh_aircraft.json"
main.plugins.skyhigh.adsb_x_coord = 160  # Screen X position
main.plugins.skyhigh.adsb_y_coord = 80   # Screen Y position
main.plugins.skyhigh.latitude = -66.273334  # Default latitude
main.plugins.skyhigh.longitude = 100.984166  # Default longitude
main.plugins.skyhigh.radius = 50  # Radius in miles
main.plugins.skyhigh.prune_minutes = 5  # Prune data older than 5 minutes
main.plugins.skyhigh.blocklist = []
main.plugins.skyhigh.allowlist = []
main.plugins.skyhigh.opensky_username = "your_username"  # Optional OpenSky username
main.plugins.skyhigh.opensky_password = "your_password"  # Optional OpenSky password
```

### Enable GPS (Optional)

If you have a GPS adapter, connect it to your Pwnagotchi with the gps plugin and configure it in config.toml with BetterCAP:

```toml
main.plugins.gps.enabled = true
main.plugins.gps.device = "/dev/ttyUSB0"  # Adjust to your GPS device path
```

### Restart Pwnagotchi

Restart with:
```bash
pwnkill
```
Or:
```bash
sudo systemctl restart pwnagotchi
```

## Usage

### On-Screen Display
The Pwnagotchi screen will show the number of detected aircraft, updating every minute (or as configured).

### Webhook Access
1. Open a browser and go to `http://<pwnagotchi-ip>/plugins/skyhigh/` to view a detailed map and table of aircraft data.
2. From the pwnagotchi plugins page, you can just click on the skyhigh plugin to open it as well.

The map uses distinct icons for helicopters (red), commercial jets (blue), small planes (yellow), drones (purple), gliders (orange), and military aircraft (green). Popups show callsign, model, registration, altitude, velocity, track, squawk, and DB flags. Clicking a marker toggles the aircraft’s flight path visualization, showing its recent trajectory.

## Configuration Options

- **timer:** Interval in seconds for fetching data (default: 60).
- **aircraft_file:** Path to store aircraft data (default: `/root/handshakes/skyhigh_aircraft.json`).
- **adsb_x_coord and adsb_y_coord:** Screen coordinates for the aircraft count display.
- **latitude and longitude:** Default coordinates if GPS is unavailable.
- **radius:** Search radius in miles for aircraft data.
- **prune_minutes:** Time in minutes after which old data is pruned (default: 10). Set to 0 to disable pruning.
- **opensky_username:** OpenSky username for authenticated API access (optional)
- **opensky_password:** OpenSky password for authenticated API access (optional).

## Known Issues and Solutions

### Transient Network Errors
The SkyHigh plugin may encounter a temporary error that causes it to stop working for 1–2 minutes before resuming automatically. This issue appears to be related to a network connectivity problem when fetching data from the OpenSky Network API.

- **Description:** The plugin logs an error like `[SkyHigh] Error fetching data from API: <error details>` but recovers on the next fetch cycle.
- **Solution:** No action is needed; the plugin is designed to handle these transient errors gracefully and resumes operation automatically. If persistent, check your internet connection.

## Why You'll Love It

- **Real-Time Awareness:** Track aircraft with detailed data (velocity, track, squawk, etc.) as it happens.
- **Flexible Configuration:** Customize radius, update interval, pruning, and API credentials to suit your needs.
- **Interactive Map:** Explore aircraft details with type-specific icons and toggle flight paths for a dynamic experience.
- **Enhanced Data:** Rich metadata and categorization provide deeper insights into nearby aircraft.
- **Real-time aircraft tracking with a responsive, customizable interface**
- **Flexible filtering, export options, and blocklist/allowlist support.**
- **Future-ready with historical tracking for enhanced features.**

Take your Pwnagotchi to the skies with SkyHigh! ✈️

This plugin fetches nearby aircraft data using the OpenSky Network API.

**Acknowledgment:** Aircraft data is provided by the OpenSky Network.

**Disclaimer:** This plugin is not affiliated with OpenSky Network. Data is used in accordance with their API terms.

---

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
main.plugins.theylive.enabled = true

# Core settings
main.plugins.theylive.mode = "server"          # "server", "peer", or "pwndroid"
main.plugins.theylive.device = "/dev/ttyACM0"  # Serial device (server mode)
main.plugins.theylive.baud = 9600              # Baud rate
main.plugins.theylive.auto = true              # Auto-install/configure gpsd

### Config Example (`config.toml`) Use the **bracketed config.toml format** below (required on newer image 2.9.5.4):
```toml
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

# Config Example 2.9.5.3 image config.toml format:
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



