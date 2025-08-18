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
- **How It Works:** Shows mode, next MAC change time, TX power, and channel, with customizable positions.
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
   main.plugins.neurolyzer.mode_label_x = 101
   main.plugins.neurolyzer.mode_label_y = 50
   main.plugins.neurolyzer.next_mac_change_label_x = 101
   main.plugins.neurolyzer.next_mac_change_label_y = 60
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

**Version:** 1.5.0

## Overview
The ProbeNpwn Plugin is an aggressively enhanced evolution of the original Instattack by Sniffleupagus, now supercharged for maximum Wi-Fi handshake captures! This updated version (1.5.0) introduces a suite of cutting-edge features, including dual operational modes (Tactical and Maniac), client scoring, ML-inspired channel hopping, intelligent retries, handshake deduplication, dynamic concurrency, continuous mobility detection with GPS integration for a mobility score (0-1), multi-band support (2.4GHz and 5GHz), min/max parameter scaling for stability, PMKID capture emphasis, and more. If you've used Instattack, you'll love ProbeNpwn - it combines deauthentication and association attacks into one powerful, adaptable tool designed to capture handshakes faster and smarter than ever before.

## Key Features

- **Efficient Deauthentication & Association Attacks:**
  Launch both simultaneously to force devices to reconnect quickly, maximizing handshake captures, with added focus on PMKID leaks via targeted associations.
  
- **Concurrent Attack Threads:**
  Handle multiple networks and clients at once with multi-threading for efficient, parallel attacks.
  
- **Customizable Settings:**
  Fine-tune attack behavior, enable/disable features (including 5GHz support), set min/max scaling ranges, and whitelist networks or clients via config.toml.
  
- **Capture More Handshakes:**
  Aggressive methods ensure rapid device reconnections, boosting handshake capture rates, including PMKIDs from client-less APs.
  
- **Comprehensive Logging:**
  Track every attack and capture with detailed logs for performance insights.
  
- **Lightweight and Seamless Integration:**
  Fully compatible with Pwnagotchi for easy setup and operation.
  
- **Continuous Mobility Detection:**
   Automatically calculates a mobility score (0 for stationary to 1 for high mobility) using Bettercap GPS data or AP discovery rates, dynamically scaling autotune/personality parameters for optimal performance.
  
- **Multi-Band Support:**
   Intelligent channel hopping across 2.4GHz and optional 5GHz bands for broader Wi-Fi coverage, with weights favoring PMKID-potential channels.
  
- **Enhanced Stability Measures:**
  LRU caches, heap-based data cleanup, delay caching, psutil fallback for monitoring, watchdog with restart backoff, pycache clearing, channel locks, and client caps per AP to prevent crashes.
  
## What's New in ProbeNpwn v1.5.0?
This release builds on v1.4.0 with major enhancements focused on smoother mobility adaptations, PMKID capture, and stability, making ProbeNpwn even more versatile for any setup—from stationary to high-speed movement. Key additions include:

### 1. Dual Operational Modes: Tactical and Maniac 🧠💥

**What's New:**
Choose between two modes (unchanged from v1.4.0, but now integrated with continuous mobility scaling for better performance).

- **Tactical Mode:** Strategic and efficient, focusing on high-value targets.
- 
- **Maniac Mode:** Unrestricted and aggressive, attacking all targets rapidly.
 
**How It Works:**
- Configurable via config.toml (`main.plugins.probenpwn.mode`).
- Tactical Mode: Prioritizes targets with high client scores and respects cooldowns/whitelists.
- Maniac Mode: Bypasses restrictions, using minimal delays (0.05s) for maximum attack frequency.

**Why It's Better:**
- Flexibility: Tailor the plugin to your needs—precision or brute force.
- Control: Switch modes based on the environment or your goals.
  
### 2. Client Scoring System 🎯

**What's New:**
Clients are scored based on signal strength and activity to prioritize high-value targets (now with decay for updated scores, LRU caching for efficiency, and caps on clients per AP to prevent memory issues).

**How It Works:**
- Scores calculated as (signal + 100) * activity, with exponential decay on updates.
- In Tactical Mode, only clients with scores ≥50 are attacked.
 
**Why It's Better:**
- Efficiency: Focuses attacks on clients most likely to yield handshakes.
- Resource Optimization: Reduces wasted effort on low-value targets and prevents data bloat.
 
### 3. ML-Inspired Channel Hopping 📡

**What's New:**
Intelligent channel selection based on historical success and activity (now with PMKID weighting for channels with many APs/few clients, integer channel keys for consistency, and multi-band support).

**How It Works:**
- Tracks APs, clients, and handshake successes per channel.
- Uses weighted random selection with cumulative weights to favor active, successful, and PMKID-friendly channels (boosted 1.5x if APs > clients and APs >3).
 
**Why It's Better:**
- Optimized Focus: Spends more time on productive channels, including those ideal for PMKID captures.
- Adaptability: Adjusts dynamically to the Wi-Fi environment, including 5GHz if enabled.
  
### 4. Intelligent Retry Mechanism with Exponential Backoff 🔄

**What's New:**
Retries failed attempts with increasing delays (now with configurable max_retries, failure-based retries in epochs, and unbounded priority queue with heap-based scheduling).

**How It Works:**
- Uses exponential backoff (starting at 1s, capping at 60s) for retries, limited by max_retries (default 3).
- Scheduled retries are managed via a priority queue, processed during epochs; auto-retries failing APs if attempts > successes +2.
  
**Why It's Better:**
- Persistence: Keeps trying tough targets without overwhelming the system.
- Resource Management: Prevents rapid, repeated attempts that could cause issues, with configurable limits.
  
### 5. Handshake Deduplication

**What's New:**
Ensures only unique handshakes are processed (now with simplified hash using MACs only for faster deduplication).

**How It Works:**
- Deduplicates handshakes using a hash-based system combining AP MAC and client MAC.
  
**Why It's Better:**
- Accuracy: Avoids redundant processing.
- Reliability: Speeds up handshake handling without validation overhead.
 
### 6. Dynamic Concurrency Based on System Resources 🛡️

**What's New:**
Adjusts the number of concurrent attack threads based on CPU and memory usage (now with psutil fallback using loadavg and cpu_count, dynamic in-watchdog adjustments, and channel locks for thread safety).

**How It Works:**
- Monitors system load (psutil preferred; falls back to os/multiprocessing).
- Scales threads (e.g., from base of cpu_count*5 down to 10) if load exceeds thresholds.
 
**Why It's Better:**
- Stability: Prevents crashes or slowdowns, especially in Maniac Mode.
- Adaptability: Works across different hardware or load conditions, even without psutil.
 
**Note:** psutil is a cross-platform library for retrieving system information. It's recommended for precise monitoring but optional—ProbeNpwn falls back to built-in tools if unavailable. If desired, install with:
```bash
sudo apt-get install python3-psutil
```
### 7. Additional Attack Vector: Fake Authentication Flood 💣

**What's New:**
Supplements deauthentication with a reduced 20% chance of a fake authentication flood (now scaled by assoc_prob for PMKID emphasis).

**How It Works:**
- Randomly triggers association attacks with a 0.05s delay; forces assoc if random < scaled assoc_prob to leak PMKIDs.
 
**Why It's Better:**
- Diversity: Captures handshakes (including PMKIDs) from APs resistant to deauthentication.
- Aggression: Boosts attack frequency, especially in Maniac Mode.
 
### 8. Enhanced UI with Handshake Count 📊

**What's New:**
The UI now displays the total number of captured handshakes (plus mobility score as a percentage, with batched updates for efficiency).

**How It Works:**
- Added to the Pwnagotchi screen at configurable coordinates; updates every 5s to reduce overhead (e.g., "Mobility: 50%").
  
**Why It's Better:**
- Visibility: Real-time feedback on handshake captures and current mobility score.
- Motivation: See your success and adaptations instantly.
 
### 9. Continuous Mobility Detection 🚀

**What's New:**
Calculates a continuous mobility score (0-1) and auto-scales parameters (replaces discrete environments and profiles from v1.4.0).

**How It Works:**
- Uses Bettercap GPS for speed calculation (Haversine formula, buffered history with configurable size, ignores extreme speeds >200 km/h) or fallback to new APs per epoch.
- Score combines normalized GPS speed (capped at 50 km/h) and AP rate; checks every configurable interval (default 10 epochs).
  
**Why It's Better:**
- Mobility: Optimizes for any speed (aggressive scans when low score, conservative when high to avoid crashes).
- Integration: Ties into Pwnagotchi's personality params like recon_time, deauth_prob, and throttles with smoother transitions.
  
### 10. Min/Max Parameter Scaling ⚙️

**What's New:**
Configurable min/max ranges for linear scaling based on mobility score (e.g., lowered RSSI thresholds, increased attack probabilities).

**How It Works:**
- Scales params like recon_time (max at low mobility, min at high), probabilities (high at low mobility), RSSI/throttles (higher at high mobility).
- Applied dynamically on score updates or config loads.
  
**Why It's Better:**
- Crash Prevention: Reduces nexmon issues during rapid movement with tailored aggression.
- Efficiency: Fine-tunes performance to your exact scenario, with user-customizable ranges.
  
### Multi-Band Support (2.4GHz + 5GHz) 🌐

**What's New:**
Optional 5GHz channel hopping for broader coverage (now with caps on clients per AP for scalability).

**How It Works:**
- Enabled via config.toml (enable_5ghz); adds channels 36-165 to hopping pool.

**Why It's Better:**
- Scalability: Prevents memory bloat on long runs with data caps.
- Reliability: Minimizes interface failures and reboots.
  
## Why You'll Love It

ProbeNpwn v1.5.0 is your handshake-capturing Swiss Army knife:

- **Smart & Aggressive:** Tactical for strategy, Maniac for mayhem, now with continuous mobility-aware scaling and PMKID focus.
- **Efficient:** Scoring, concurrency, and caching optimize every attack.
- **Relentless:** Retries and floods leave no handshake behind, across more bands.
- **Stable:** Keeps your Pwnagotchi happy under pressure, even at high speeds.
Big props to Sniffleupagus for the original Instattack—this builds on that legacy! 🙏

## How to Get Started

### Install the Plugin:

Copy `probenpwn.py` to your Pwnagotchi's plugins folder.
### Install psutil (if not already installed):

Run:
```bash
sudo apt-get install python3-psutil
```
Why: psutil enables precise dynamic thread scaling based on system resources, keeping your Pwnagotchi stable during intense operations. If not installed, ProbeNpwn falls back to built-in monitoring.

### Edit config.toml:
```toml
main.plugins.probenpwn.enabled = true
main.plugins.probenpwn.mode = "tactical" # or "maniac"
main.plugins.probenpwn.attacks_x_coord = 110
main.plugins.probenpwn.attacks_y_coord = 20
main.plugins.probenpwn.success_x_coord = 110
main.plugins.probenpwn.success_y_coord = 30
main.plugins.probenpwn.handshakes_x_coord = 110
main.plugins.probenpwn.handshakes_y_coord = 40
main.plugins.probenpwn.verbose = true # For detailed logs
main.plugins.probenpwn.enable_5ghz = false # Set to true for 5GHz support (requires compatible hardware)
main.plugins.probenpwn.max_retries = 3 # Max retries per target
main.plugins.probenpwn.gps_history_size = 5 # GPS buffer size for speed calc
main.plugins.probenpwn.env_check_interval = 10 # Epochs between mobility checks
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
### Whitelist (Optional):
Add safe networks/MACs to `/etc/pwnagotchi/config.toml` under `main.whitelist`.
### Restart & Monitor:
```bash
sudo systemctl restart pwnagotchi
```
## Pro Tip 💡
Use Tactical Mode for efficiency and enable continuous mobility detection for automatic scaling on the go. Switch to Maniac Mode in crowded areas for a handshake bonanza, and turn on 5GHz in modern Wi-Fi zones—just keep an eye on your device's temperature!

## Disclaimer
This software is provided for educational and research purposes only. Use of this plugin on networks or devices that you do not own or have explicit permission to test is strictly prohibited. The author(s) and contributors are not responsible for any misuse, damages, or legal consequences that may result from unauthorized or improper usage. By using this plugin, you agree to assume all risks and take full responsibility for ensuring that all applicable laws and regulations are followed.

---

# SnoopR Plugin

Welcome to SnoopR, a powerful plugin for Pwnagotchi, the pocket-sized Wi-Fi security testing tool! SnoopR supercharges your Pwnagotchi by detecting and logging Wi-Fi and Bluetooth devices, identifying potential snoopers based on movement patterns, and presenting everything on an interactive, real-time map. Whether you're a security enthusiast, a tinkerer, or just curious about the wireless world around you, SnoopR has something to offer.

This updated version (2.0.0) brings a host of new features, including richer data collection, smarter snooper detection, whitelisting, automatic data pruning, and an improved web interface. It's actively developed, community-driven, and packed with capabilities to help you explore and secure your wireless environment. Let's dive into what SnoopR can do and how you can get started!

## Features

SnoopR is loaded with capabilities to make your wireless adventures both fun and insightful. Here's what it brings to the table:

- **Enhanced Device Detection**: Captures Wi-Fi and Bluetooth devices with additional details like Wi-Fi channel and authentication mode, alongside GPS coordinates for precise location tracking. The SQLite database now includes new columns—channel (INTEGER) for Wi-Fi channel (e.g., 1, 6, 11) and auth_mode (TEXT) for authentication mode (e.g., WPA2, WEP)—offering deeper insights into network configurations for security testing and auditing.

- **Improved Snooper Identification**: Spots potential snoopers with more accurate detection logic—devices that move beyond a customizable threshold (default: 0.1 miles) or exhibit a velocity greater than 1.5 meters per second across at least three detections within a time window (default: 5 minutes) are flagged, reducing false positives. Uses the Haversine formula (Earth’s radius = 3958.8 miles) to calculate movement and velocity.

- **Whitelisting**: Exclude specific networks (e.g., your home Wi-Fi or personal devices) from being logged or flagged to keep your data focused. Configurable via the whitelist option (e.g., ["MyHomeWiFi", "MyPhone"]).

- **Automatic Data Pruning**: Deletes detection records older than a configurable number of days (default: 30) to manage database size and keep it efficient. Runs on startup with a DELETE query based on a cutoff date.

- **Interactive Map**: Displays all detected devices on a dynamic map with sorting (by device type or snooper status), filtering (all, snoopers, or Bluetooth), and the ability to pan to a network's location by clicking on it in the table. Markers are blue for regular devices and red for snoopers.

- **Real-Time Monitoring**: Shows live counts of detected networks, snoopers, and the last Bluetooth scan time (e.g., "Last Scan: 14:30:00") directly on the Pwnagotchi UI at position (7, 135).

- **Customizable Detection**: Fine-tune movement and time thresholds to define what qualifies as a snooper, tailored to your needs.

- **Reliable Bluetooth Scanning**: Includes a retry mechanism (up to three attempts with 1-second delays) for more consistent device name retrieval via hcitool name, ensuring better accuracy. Detects devices with hcitool inq --flush.

- **Threaded Scans**: Bluetooth scans run in a separate thread every 45 seconds (configurable), ensuring smooth performance without interrupting other operations.

- **Better Logging and Error Handling**: Improved logging for GPS warnings (e.g., unavailable coordinates) and Bluetooth errors (e.g., hcitool failures), making it easier to debug and maintain.

- **Performance Optimizations:** Database indexes on detections.network_id, networks.mac, and detections.timestamp for faster queries. Batch insertions for Wi-Fi detections to reduce database overhead.

- **Better Logging and Error Handling:** Improved logging for GPS warnings (e.g., unavailable coordinates), Bluetooth errors (e.g., hcitool failures), and mesh operations, making it easier to debug and maintain.

## Requirements

Before installing SnoopR, ensure you have the following:

- **GPS Adapter**: Connected via bettercap (easily done with the gps plugin). GPS is essential for logging device locations.
    
- **Bluetooth Enabled**: Required for Bluetooth scanning. Ensure Bluetooth is activated on your Pwnagotchi (`sudo hciconfig hci0 up`).
    
- **Internet Access (for Viewing)**: The device you use to view the web interface (e.g., your phone or computer) needs internet to load map tiles and Leaflet.js. The Pwnagotchi itself doesn't require an internet connection.


## Installation Instructions

You can install SnoopR in two ways: the easy way (recommended) or the manual way. Here's how:

### Easy Way (Recommended)

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
   Run these commands to update the plugin list and install SnoopR:

   ```bash
   sudo pwnagotchi plugins update
   sudo pwnagotchi plugins install snoopr
   ```

That's it! You're ready to configure SnoopR.

### Manual Way (Alternative)

If you prefer a hands-on approach:

1. **Clone the SnoopR plugin repo from GitHub**:

   ```bash
   sudo git clone https://github.com/AlienMajik/pwnagotchi_plugins.git
   cd pwnagotchi_plugins
   ```

2. **Copy the Plugin File**  
   Move snoopr.py to your Pwnagotchi's custom plugins directory:

   ```bash
   sudo cp snoopr.py /usr/local/share/pwnagotchi/custom-plugins/
   ```

   Alternatively, if you're working from a computer, use SCP:

   ```bash
   sudo scp snoopr.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/
   ```

## Configuration

To enable and customize SnoopR, edit `/etc/pwnagotchi/config.toml` and add the following under the `[main.plugins.snoopr]` section:

```toml
main.plugins.snoopr.enabled = true
main.plugins.snoopr.path = "/root/snoopr"                  # Directory for the database
main.plugins.snoopr.ui.enabled = true                     # Show stats on the Pwnagotchi UI
main.plugins.snoopr.gps.method = "bettercap"              # GPS source
main.plugins.snoopr.movement_threshold = 0.2              # Distance (miles) for snooper detection
main.plugins.snoopr.time_threshold_minutes = 5            # Time (minutes) between detections
main.plugins.snoopr.bluetooth_enabled = true              # Enable Bluetooth scanning
main.plugins.snoopr.timer = 45                            # Bluetooth scan interval (seconds)
main.plugins.snoopr.whitelist = ["MyHomeWiFi", "MyPhone"] # Networks to exclude
main.plugins.snoopr.prune_days = 30                       # Days before pruning old data
```

### Available Options

- **enabled**: Set to true to activate the plugin. Default: false
    
- **path**: Directory for the SQLite database (e.g., /root/snoopr/snoopr.db). Default: /root/snoopr
    
- **ui.enabled**: Show stats on the Pwnagotchi UI. Default: true
    
- **gps.method**: GPS data source (only "bettercap" supported). Default: "bettercap"
    
- **movement_threshold**: Minimum distance (miles) a device must move to be flagged as a snooper. Default: 0.1
    
- **time_threshold_minutes**: Time interval (minutes) between detections for snooper checks. Default: 5
    
- **bluetooth_enabled**: Enable Bluetooth scanning. Default: true
    
- **timer**: Interval (seconds) between Bluetooth scans. Default: 45
    
- **whitelist**: List of network names (SSIDs or Bluetooth device names) to exclude from logging. Default: []
    
- **prune_days**: Number of days to retain detection records before pruning. Default: 30


After editing the config, restart your Pwnagotchi to apply the changes:

```bash
sudo systemctl restart pwnagotchi
```

## Database Schema Updates

On startup, SnoopR checks the detections table for channel and auth_mode columns using PRAGMA table_info. If missing, it adds them with ALTER TABLE commands, logging the updates (e.g., [SnoopR] Added "channel" column to detections table) for seamless compatibility. The database also includes indexes on detections.network_id, networks.mac, and detections.timestamp for faster queries.

## Usage

Once installed and configured, SnoopR runs automatically when you power up your Pwnagotchi. Here's how it works:

- **Wi-Fi Logging**: Logs Wi-Fi access points with details like MAC, SSID, channel, authentication mode, encryption, signal strength, and location. Skips whitelisted SSIDs during on_unfiltered_ap_list.
    
- **Bluetooth Scanning**: If enabled, scans for Bluetooth devices every timer seconds using hcitool inq --flush, logging their details and locations. Retries name retrieval up to three times with hcitool name.
    
- **Snooper Detection**: Flags devices as snoopers if they move beyond movement_threshold across at least three detections within time_threshold_minutes. Updates the is_snooper flag in the networks table.
    
- **Whitelisting**: Excludes specified networks from being logged or flagged during Wi-Fi and Bluetooth scans.
    
- **Data Pruning**: Automatically deletes old detection records from the detections table on startup if older than prune_days.

### Monitoring the UI

Your Pwnagotchi's display will show real-time stats (if ui.enabled is true):

- Number of detected Wi-Fi networks and snoopers
- Number of detected Bluetooth devices and snoopers (if enabled)
- Time of the last Bluetooth scan (e.g., "Last Scan: 14:30:00")

### Viewing Logged Networks

To see detailed logs and the interactive map, access the web interface:

1. **Connect to Your Pwnagotchi's Network**  
   - Via USB: Typically 10.0.0.2
   - Via Bluetooth tethering: Typically 172.20.10.2

2. **Open the Web Interface**  
   In a browser on a device with internet access:
   - USB: http://10.0.0.2:8080/plugins/snoopr/
   - Bluetooth: http://172.20.10.2:8080/plugins/snoopr/

3. **Explore the Interface**  
   - **Table**: Lists all detected networks with sorting (by “Device Type” or “Snooper”) and filtering (“All,” “Snoopers,” “Bluetooth,” or “Aircraft”).
   - **Map**: hows device locations—click a network in the table to pan the Leaflet.js map to its marker (blue for regular, red for snoopers, green for aircraft, gray for no coordinates) with popups showing details.
   - **Scroll Buttons**: "Scroll to Top" and "Scroll to Bottom" for easy navigation of long lists.






##Notes

- **Database**: All data is stored in snoopr.db in the directory specified by path.
- **Data Pruning**: Detection records older than prune_days are automatically deleted to manage database size.
- **GPS Dependency**: Logging requires GPS data. If unavailable (latitude/longitude = "-"), a warning is logged, and Bluetooth scans are skipped.
- **Web Interface Requirements**: The viewing device needs internet to load Leaflet.js and OpenStreetMap tiles.
- **Bluetooth Troubleshooting**: If scanning fails, ensure hcitool is installed and Bluetooth is enabled (`sudo hciconfig hci0 up`).
- **Logging**: Improved logging for GPS and Bluetooth issues (e.g., [SnoopR] Error running hcitool: <error>), aiding in debugging.

## Community and Contributions

SnoopR thrives thanks to its community! We're always improving the plugin with new features and fixes. Want to get involved? Here's how:

- **Contribute**: Submit pull requests with enhancements or bug fixes.
- **Report Issues**: Found a bug? Let us know on the GitHub Issues page.
- **Suggest Features**: Have an idea? Share it with us!

Join the fun and help make SnoopR even better.

## Disclaimer

SnoopR is built for educational and security testing purposes only. Always respect privacy and adhere to local laws when using this plugin. Use responsibly!

---

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

**Version:** 1.0.0

## Description
A universal enhanced plugin for various UPS HATs, providing battery indicators, voltage monitoring, auto-shutdown, customizable polling, UI optimization, error diagnostics, battery health tracking, and auto-detection of HAT types. Supports popular HATs like Pimoroni X1200, UPS Lite, Waveshare UPS C, PiSugar, SB Components UPS, Geekworm X750, and EP-0136, ensuring a seamless and reliable power management experience without cluttering the UI.

## Key Stats
The plugin tracks essential battery and system statistics to keep you informed about your Pwnagotchi's power status:

### Battery Capacity (🔋 %)
- Displays the current state-of-charge (SOC) as a percentage.
- Read from fuel gauge chips like MAX170xx or approximated from voltage for INA219-based HATs.

### Voltage (V)
- Shows the real-time battery voltage.
- Helps identify low-power conditions or charging efficiency.

### Charging Status (+/-)
- Indicates if the battery is charging ('+') or discharging ('-').
- Detected via GPIO pins, current direction, or custom registers depending on the HAT.

### Estimated Runtime (~m)
- Calculates remaining battery life in minutes based on capacity, battery mAh, and average current draw.
- Configurable via battery_mah and avg_current_ma settings.

### Battery Health
- Tracks charge cycles (for supported HATs like MAX170xx).
- Monitors error counts during reads for diagnostics (visible in debug mode).

## New Enhancements in v1.2.0
- **Auto-Detection of UPS Types:** Scans the I2C bus to automatically identify the connected HAT, with fallback to manual selection.
- **Battery Health Monitoring:** Tracks charge cycles and sets low-battery alerts on the fuel gauge chip.
- **Error Diagnostics:** Retry mechanisms for reads, error counting, and debug display for troubleshooting.
- **UI Customization:** Optional icons (🔋/⚡), voltage display, runtime estimates, and position adjustments to keep the screen clean.
- **Polling Optimization:** Configurable intervals to reduce hardware overhead while maintaining fresh data.
- **Auto-Shutdown Grace Periods:** Consecutive low-battery checks and time-based persistence to prevent false shutdowns.
- **Runtime Estimates:** Dynamic calculations for remaining time based on user-defined battery specs.
- **Debug Mode:** Exposes error counts and cycle info in the UI for advanced users.
- **Enhanced Charging Detection:** Supports GPIO, current-based, or register-based methods across HATs.
- **Thread Safety and Persistence:** Reliable caching of last known values to handle failures gracefully.
- **Improved Logging:** Detailed prefixed logs ([MadHatter]/[MadHatterUPS]) for monitoring and debugging.

## Features
- **Universal HAT Support:** Auto-detects and configures for MAX170xx, INA219, PiSugar/IP5310-based HATs.
- **Persistent Monitoring:** Caches voltage, capacity, and charging status across polls.
- **UI Integration:** Customizable labeled display for stats, icons, and estimates without overwhelming the screen.
- **Auto-Shutdown Mechanism:** Triggers safe shutdown on critically low battery after grace periods.
- **Warning System:** Logs alerts for low battery or warnings thresholds.
- **Health Tracking:** Cycle counting and chip-level alerts for long-term battery maintenance.
- **Efficient Polling:** Interval-based reads with retries to minimize I2C/GPIO usage.
- **Customizable Alerts:** Set thresholds for shutdown, warnings, and chip alerts.
- **Debug Tools:** Optional UI elements for errors and cycles.

## Installation Instructions

### Copy the Plugin File
Place `mad_hatter.py` in `/usr/local/share/pwnagotchi/custom-plugins/`.
Or use SCP:
```bash
sudo scp mad_hatter.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/
```

### Update config.toml
Add to `/etc/pwnagotchi/config.toml`:
```toml
main.plugins.mad_hatter.enabled = true
main.plugins.mad_hatter.show_voltage = false
main.plugins.mad_hatter.shutdown_enabled = false
main.plugins.mad_hatter.shutdown_threshold = 5
main.plugins.mad_hatter.warning_threshold = 15
main.plugins.mad_hatter.shutdown_grace = 3
main.plugins.mad_hatter.shutdown_grace_period = 30
main.plugins.mad_hatter.poll_interval = 10
main.plugins.mad_hatter.ui_position_x = 150
main.plugins.mad_hatter.ui_position_y = 0
main.plugins.mad_hatter.show_icon = true
main.plugins.mad_hatter.battery_mah = 2000
main.plugins.mad_hatter.avg_current_ma = 200
main.plugins.mad_hatter.debug_mode = false
main.plugins.mad_hatter.charging_gpio = 16
main.plugins.mad_hatter.alert_threshold = 10
main.plugins.mad_hatter.ups_type = 'auto'
```

### MadHatter Plugin Configuration Options

## main.plugins.mad_hatter.show_voltage = false

Controls whether the battery voltage (in volts, e.g., "4.1V") is displayed in the UI string alongside capacity and charging status. If true, voltage is included; if false, it's omitted to keep the UI cleaner. (Default: False)

## main.plugins.mad_hatter.shutdown_enabled = false

Enables or disables the auto-shutdown feature. When true, the plugin monitors battery capacity and triggers a safe shutdown (pwnagotchi.shutdown()) if it falls below the shutdown threshold for a sustained period (based on grace settings). If false, no shutdown checks occur. (Default: False)

## main.plugins.mad_hatter.shutdown_threshold = 5

Sets the battery capacity percentage (%) below which the plugin considers initiating a shutdown (if shutdown_enabled is true and the battery is discharging). This is the critical low-battery trigger point. (Default: 5)

## main.plugins.mad_hatter.warning_threshold = 15

Sets the battery capacity percentage (%) below which the plugin logs a warning message (e.g., "Battery low (X%) - Consider charging!") if the battery is discharging. This acts as an early alert before shutdown. (Default: 15)

## main.plugins.mad_hatter.shutdown_grace = 3

Defines the number of consecutive low-battery readings (below shutdown_threshold) required before triggering a shutdown. This helps prevent false positives from temporary dips. The counter resets if the battery recovers or starts charging. (Default: 3)

## main.plugins.mad_hatter.shutdown_grace_period = 30

Specifies the minimum duration (in seconds) that the low-battery condition must persist (after the grace count is met) before shutdown is triggered. This adds an extra layer of persistence checking. (Default: 30)

## main.plugins.mad_hatter.poll_interval = 10

Sets the interval (in seconds) between hardware reads (e.g., voltage, capacity, charging status) from the UPS HAT. Lower values provide fresher data but increase overhead; higher values reduce I2C/GPIO usage. Between polls, cached values are used. (Default: 10)

## main.plugins.mad_hatter.ui_position_x = null

Sets the x-coordinate (horizontal position) for the UI display element on the Pwnagotchi screen. If set to null (or None in code), it defaults to a calculated position (screen width / 2 + 15, typically top-right). Use an integer for custom placement. (Default: None)

## main.plugins.mad_hatter.ui_position_y = 0

Sets the y-coordinate (vertical position) for the UI display element. A value of 0 places it at the top of the screen. Adjust for custom layouts. (Default: 0)

## main.plugins.mad_hatter.show_icon = true

Controls whether Unicode icons are included in the UI display string: "🔋" for battery and "⚡" for charging (if active). If true, icons are shown; if false, only text (e.g., capacity and charging symbol) is displayed. (Default: True)

## main.plugins.mad_hatter.battery_mah = 2000

Specifies the battery capacity in milliamp-hours (mAh) used to estimate remaining runtime. This value is plugged into the formula: (capacity / 100) * battery_mah / avg_current_ma * 60 to calculate minutes left, shown in the UI as "(~Xm)". Adjust based on your actual battery specs. (Default: 2000)

## main.plugins.mad_hatter.avg_current_ma = 200

Sets the assumed average current draw in milliamps (mA) for runtime estimates. This represents the typical power consumption of your Pwnagotchi setup and is used in the runtime calculation formula. Tune it based on measurements for accuracy. (Default: 200)

## main.plugins.mad_hatter.debug_mode = false

Enables or disables debug information in the UI display string. If true, it appends error counts (from failed reads) and battery cycle counts (e.g., "Err:X Cyc:Y"). Useful for troubleshooting; if false, this info is hidden. (Default: False)

## main.plugins.mad_hatter.charging_gpio = 16

Specifies the GPIO pin (in BCM mode) used for charging detection on supported HATs (e.g., X1200 or UPS Lite). If the pin reads LOW, it's considered charging ('+'). Set to null (or None) if not applicable or if using I2C-based detection. (Default: None, but often set per HAT like 16 for X1200)

## main.plugins.mad_hatter.alert_threshold = 10

Sets the low-battery alert threshold percentage (%) for the fuel gauge chip (primarily MAX170xx-based HATs). This configures the chip's internal alert register to trigger at (32 - threshold), notifying the system of low power. Ignored for non-supported HATs. (Default: 10)

## main.plugins.mad_hatter.ups_type = 'x1200'

Specifies the type of UPS HAT connected. Set to 'auto' for automatic I2C scanning and detection. Other values include 'x1200', 'ups_lite', 'waveshare_c', 'pisugar', 'sb_ups', 'x750', or 'ep0136'. This overrides auto-detection and selects type-specific reading methods. (Default: 'auto')

### Restart Pwnagotchi

Apply changes with:
```bash
sudo systemctl restart pwnagotchi
```
## Usage
- **Monitor Battery Stats:** View capacity, charging status, voltage (optional), and runtime on the UI.
- **Enable Auto-Shutdown:** Set shutdown_enabled to true for safe power-off on low battery.
- **Customize UI:** Adjust positions, icons, and debug info to fit your display preferences.
- **Track Health:** Use debug_mode to see cycle counts and errors; monitor logs for warnings.
- **Optimize Polling:** Tune poll_interval for balance between freshness and efficiency.
- **Detect HATs Automatically:** Leave ups_type as 'auto' for plug-and-play; override if needed.
- **Avoid Low Battery Issues:** Respond to warnings and ensure regular charging to prevent shutdowns.
  
## Logs and Data
- **System Logs:** Events and errors are logged with prefixes like [MadHatter] or [MadHatterUPS] in the Pwnagotchi system logs (viewable via journalctl or /var/log/pwnagotchi.log).
  Includes detection info, poll results, warnings, and shutdown triggers.
- **No Persistent Data Files:** Stats are read live from hardware; caches are in-memory for the session.

---

# TheyLive Plugin

Welcome to TheyLive, a robust GPS plugin for Pwnagotchi, the pocket-sized Wi-Fi security testing tool! TheyLive enhances your Pwnagotchi by leveraging gpsd to display real-time GPS coordinates on the screen, log locations with captured handshakes, and integrate seamlessly with Bettercap for precise packet capture tagging. Whether you're a security researcher, a mobile auditor, or just exploring wireless environments, TheyLive provides accurate location awareness to make your sessions more insightful.

This updated version (1.3.5) includes compatibility fixes for the latest jayofelony Pwnagotchi images, improved auto-setup for gpsd (with PPS support for high-precision timing), customizable UI fields and units, and enhanced error handling for reliable operation. It's actively refined, community-inspired, and designed to work out-of-the-box with USB or serial GPS devices. Let's explore what TheyLive offers and how to get started!

## Features

TheyLive is packed with tools to integrate GPS into your Pwnagotchi workflow. Here's what it delivers:

- **Real-Time GPS Display**: Shows customizable fields like fix type (e.g., 2D/3D), latitude, longitude, altitude, and speed on the Pwnagotchi UI, with support for units like kph/mph for speed and m/ft for distance.
- **Handshake Location Logging**: Automatically saves GPS coordinates (latitude/longitude) to a .gps.json file alongside each captured .pcap handshake, enabling geospatial analysis of networks.
- **Bettercap Integration**: Configures Bettercap's GPS module for tagged captures, with options to enable/disable reporting.
- **Auto-Setup for gpsd**: Installs and configures gpsd if missing (with internet check), including baud rate, device port, and PPS for sub-microsecond accuracy on compatible hardware.
- **Peer Mode Support**: Allows sharing GPS data from a "server" Pwnagotchi to "peer" units, ideal for multi-device setups with a single GPS source.
- **Customizable UI**: Adjust fields order, position (topleft_x/y), and spacing for optimal display on various screens.
- **Error-Resilient Polling**: Handles gpsd response issues (e.g., empty/malformed JSON) with logging and graceful fallbacks to prevent crashes.
- **PPS Time Syncing**: Placeholder for high-precision timing setup (requires non-USB GPS with PPS pin; documentation forthcoming).
- **Better Logging**: Detailed logs for setup, connections, and errors, making troubleshooting straightforward.

## Requirements

Before installing TheyLive, ensure you have the following:

- **GPS Hardware**: A USB or serial GPS adapter (e.g., connected to /dev/ttyACM0 or /dev/ttyS0). PPS-enabled devices for advanced timing.
   
- **Internet Access (Initial Setup)**: Required for auto-installing gpsd if not present; offline mode skips this.
   
- **Pwnagotchi Compatibility**: Works with jayofelony images (tested up to 2.9.5.3); Bettercap for integration.

## Installation Instructions

You can install TheyLive in two ways: the easy way (recommended) or the manual way. Here's how:

### Easy Way (Recommended)

1. **Update Your Config File**
   Edit `/etc/pwnagotchi/config.toml` and add the following lines to enable custom plugin repositories (if not already present):
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
   Run these commands to update the plugin list and install TheyLive:
   ```bash
   sudo pwnagotchi plugins update
   sudo pwnagotchi plugins install theylive
   ```
That's it! You're ready to configure TheyLive.

### Manual Way (Alternative)

if you're working from a computer, use SCP:
   ```bash
   sudo scp theylive.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/
   ```

## Configuration

To enable and customize TheyLive, edit `/etc/pwnagotchi/config.toml` and add the following under the `[main.plugins.TheyLive]` section:
```toml
main.plugins.TheyLive.enabled = true
main.plugins.TheyLive.device = "/dev/ttyACM0"
main.plugins.TheyLive.baud = 115200
main.plugins.TheyLive.fields = [
 "fix",
 "lat",
 "lon",
 "alt",
 "spd"
]
main.plugins.TheyLive.speedUnit = "mph"
main.plugins.TheyLive.distanceUnit = "m"
main.plugins.TheyLive.bettercap = true
main.plugins.TheyLive.auto = true
main.plugins.TheyLive.mode = "server"
main.plugins.TheyLive.topleft_x = 130
main.plugins.TheyLive.topleft_y = 47
```
### Available Options

- **enabled**: Set to true to activate the plugin. Default: false
   
- **device**: Serial port for GPS hardware (e.g., /dev/ttyACM0). Default: ''
   
- **baud**: Baud rate for GPS communication. Default: 9600
   
- **fields**: Array of GPS fields to display (e.g., ['fix', 'lat', 'lon']). Default: ['fix', 'lat', 'lon', 'alt', 'spd']
   
- **speedUnit**: Speed unit (kph, mph, ms). Default: ms
   
- **distanceUnit**: Altitude unit (m, ft). Default: m
   
- **bettercap**: Enable Bettercap GPS integration. Default: true
   
- **auto**: Auto-install/configure gpsd. Default: true
   
- **mode**: 'server' for direct GPS, 'peer' for sharing. Default: server
   
- **topleft_x / topleft_y**: UI position for display elements. Default: 130 / 47
   
After editing the config, restart your Pwnagotchi to apply the changes:
```bash
sudo systemctl restart pwnagotchi
```

## Usage

Once installed and configured, TheyLive runs automatically when you power up your Pwnagotchi. Here's how it works:
- **GPS Display**: Shows selected fields on the UI once a fix is acquired.
   
- **Handshake Logging**: Adds .gps.json files with lat/long to captured .pcap files.
   
- **Bettercap Tagging**: Enables GPS in Bettercap for location-aware captures.
   
- **Auto-Setup**: Installs gpsd and configures services on first run (if auto=true).
- 
### Monitoring the UI

Your Pwnagotchi's display will show GPS details in real-time (e.g., "lat: 37.7749 ", "lon: -122.4194 ").

### Viewing Logged Networks

Logged data is in /home/pi/handshakes/ as .gps.json files—open them for coordinates or use tools like Wireshark for analysis.

##Notes
- **GPS Dependency**: Requires valid GPS hardware; logs warnings if no fix.
- **Internet for Setup**: Needed initially for gpsd install; skips if offline.
- **Bettercap Troubleshooting**: If integration fails, check Bettercap status.
- **Logging**: Detailed logs in /var/log/pwnagotchi.log for setup and errors.
## Community and Contributions
TheyLive thrives thanks to its community! We're always improving the plugin with new features and fixes. Want to get involved? Here's how:
- **Contribute**: Submit pull requests with enhancements or bug fixes.
- **Report Issues**: Found a bug? Let us know on the GitHub Issues page.
- **Suggest Features**: Have an idea? Share it with us!
  
## Notes on Modifications

TheyLive is a modified version of the original "gpsdeasy" plugin. https://github.com/rai68/gpsd-easy.

Join the fun and help make TheyLive even better.


