Age.py Plugin for Pwnagotchi v3.1.0
Author: AlienMajik
Version: 3.1.0

Description: 
          
    An enhanced plugin with frequent titles, dynamic quotes, progress bars, random events, handshake streaks, personality evolution, and secret achievements. The UI is optimized to avoid clutter, ensuring a     clean and engaging experience.

Key Stats:

    The plugin tracks four primary statistics that reflect your Pwnagotchi’s journey:

Age (♥ Age):  

    Tracks the number of epochs your Pwnagotchi has lived.  
    Earns frequent titles like "Baby Steps" (100 epochs), "Getting the Hang of It" (500 epochs), "Neon Spawn" (1,000 epochs), and more.


Strength (Str):  

    Reflects training progress, increasing by 1 every 10 epochs.  
    Titles include "Sparring Novice" (100 train epochs), "Gear Tickler" (300 train epochs), "Fleshbag" (500 train epochs), and beyond.


Network Points (★ Pts):  

    Earn points by capturing handshakes, with values based on encryption strength:  
    WPA3: +10 points  
    WPA2: +5 points  
    WEP/WPA: +2 points  
    Open/Unknown: +1 point

    Points decay if the Pwnagotchi is inactive for too long.


Personality:  

    Develops based on actions:  
    
    Aggro: Increases with each handshake.  
    Scholar: Increases every 10 epochs.  
    Stealth: Reserved for future use.

    Displayed on the UI if enabled.




New Enhancements in v3.1.0

    More Frequent Titles: Age and strength titles are awarded more often, making progression feel rewarding at every stage. 

    Context-Aware Dynamic Quotes: Motivational messages respond to your actions, like capturing handshakes or recovering from decay. 

    Progress Bars: A visual bar shows how close you are to the next age title (e.g., [===  ] for 60% progress).  

    Random Events: Every 100 epochs, there's a 5% chance of events like "Lucky Break" (double points) or "Signal Noise" (half points).  

    Handshake Streaks: Capture 5+ consecutive handshakes for a 20% point bonus per handshake.  

    Personality Evolution: Your Pwnagotchi’s dominant trait (Aggro, Scholar, Stealth) evolves based on its actions.  

    Secret Achievements: Unlock hidden goals like "Night Owl" (10 handshakes between 2-4 AM) or "Crypto King" (capture all encryption types) for bonus points. 

    UI Optimization: Streamlined to avoid clutter; personality display is optional.  

    Enhanced Data Persistence: Saves streak, personality, and achievement progress.  

    Thread Safety: Ensures reliable data saving.  

    Improved Logging: Detailed logs for better tracking and debugging.


Features

    Persistent Stats: Age, Strength, Points, and Personality survive reboots.  

    UI Integration: Stats, progress bars, and messages are displayed on the screen.  

    Points Logging: Handshake events are logged in /root/network_points.log.  

    Decay Mechanism: Points decay after inactivity to encourage regular use.  

    Dynamic Status Messages: Context-aware quotes and inactivity alerts.  

    Personality Evolution: Develops based on actions; display optional.  

    Secret Achievements: Hidden goals for bonus points.  

    Random Events: Periodic events that spice up gameplay. 

    Handshake Streaks: Bonus points for consecutive captures.


Installation Instructions

Copy the Plugin File  

Place age.py in /usr/local/share/pwnagotchi/custom-plugins/. 

Or use SCP:  
      
    sudo scp age.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/




Update config.toml  

Add to /etc/pwnagotchi/config.toml: 

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




Restart Pwnagotchi  

Apply changes with:  

    sudo systemctl restart pwnagotchi






Usage

Monitor Stats: Watch Age, Strength, and Points increase on the screen. 

Capture Handshakes: Earn points and build streaks for bonuses.  

Track Progress: See how close you are to the next age title with the progress bar. 

Experience Events: Encounter random events that affect point earnings. 

Develop Personality: Your Pwnagotchi’s actions shape its dominant trait. 

Unlock Achievements: Discover secret goals for extra points.  

Avoid Decay: Stay active to prevent point loss from inactivity.


Logs and Data

Stats Data: /root/age_strength.json  
Stores epochs, train_epochs, points, handshakes, personality, and more.


Points Log: /root/network_points.log  
Records each handshake with timestamp, ESSID, encryption, and points.




Support & Contributions
Feel free to open issues or pull requests to improve this plugin or suggest new features. Enjoy leveling up your Pwnagotchi!


ADSBsniffer.py:
A plugin that captures ADS-B data from aircraft using RTL-SDR and logs it.
a RTL-SDR Dongle is required to run plugin

1. Connect the RTL-SDR Dongle

First, connect your RTL-SDR dongle to one of the USB ports on your Raspberry Pi (the hardware running Pwnagotchi). Ensure the dongle is properly seated and secure.
2. Access the Pwnagotchi Terminal

To configure the RTL-SDR and test rtl_adsb, you'll need to access the terminal on your Pwnagotchi. You can do this in several ways:

    Directly via Keyboard and Monitor: If you have a monitor and keyboard connected to your Raspberry Pi, you can access the terminal directly.
    SSH: If your Pwnagotchi is connected to your network, you can SSH into it. The default username is usually pi, and the password is raspberry, unless you've changed it. The IP address can be found on the Pwnagotchi screen or through your router's DHCP client list.

3. Install RTL-SDR Drivers and Utilities

Once you're in the terminal, you'll likely need to install the RTL-SDR drivers and the rtl_adsb utility. Pwnagotchi is based on Raspbian, so you can use apt-get to install these packages. Run the following commands:
     
    sudo apt-get update
    
    sudo apt-get install rtl-sdr

4. Verify RTL-SDR Dongle Recognition

After installation, verify that the RTL-SDR dongle is recognized by the system:

    rtl_test

This command checks if the RTL-SDR dongle is properly recognized. You should see output indicating the detection of the dongle. If there are errors or the dongle is not detected, ensure it's properly connected or try reconnecting it.

5. Run rtl_adsb

Now, try running rtl_adsb to see if you can receive ADS-B signals:

    rtl_adsb

This command starts the ADS-B reception. If your RTL-SDR is set up correctly and there are aircraft in range, you should see ADS-B messages appearing in the terminal.

Add adsbsniffer.py to /usr/local/share/pwnagotchi/installed-plugins and /usr/local/share/pwnagotchi/available-plugins

In /etc/pwnagotchi/config.toml file add: 

    main.plugins.adsbsniffer.enabled = true
    main.plugins.adsbsniffer.timer = 60
    main.plugins.adsbsniffer.aircraft_file = "/root/handshakes/adsb_aircraft.json"
    main.plugins.adsbsniffer.adsb_x_coord = 120
    main.plugins.adsbsniffer.adsb_y_coord = 50

**Disclaimer for ADSBSniffer Plugin**

The ADSBSniffer plugin ("the Plugin") is provided for educational and research purposes only. By using the Plugin, you agree to use it in a manner that is ethical, legal, and in compliance with all applicable local, state, federal, and international laws and regulations. The creators, contributors, and distributors of the Plugin are not responsible for any misuse, illegal activity, or damages that may arise from the use of the Plugin.

The Plugin is designed to capture ADS-B data from aircraft using RTL-SDR technology. It is important to understand that interfacing with ADS-B signals, aircraft communications, and related technologies may be regulated by governmental agencies. Users are solely responsible for ensuring their use of the Plugin complies with all relevant aviation and communications regulations.

The information provided by the Plugin is not guaranteed to be accurate, complete, or up-to-date. The Plugin should not be used for navigation, air traffic control, or any other activities where the accuracy and completeness of the information are critical.

The use of the Plugin to interfere with, disrupt, or intercept aircraft communications is strictly prohibited. Respect privacy and safety laws and regulations at all times when using the Plugin.

The creators of the Plugin make no warranties, express or implied, about the suitability, reliability, availability, or accuracy of the information, products, services, or related graphics contained within the Plugin for any purpose. Any reliance you place on such information is therefore strictly at your own risk.

By using the Plugin, you agree to indemnify and hold harmless the creators, contributors, and distributors of the Plugin from and against any and all claims, liabilities, damages, losses, or expenses, including legal fees and costs, arising out of or in any way connected with your access to or use of the Plugin.

This disclaimer is subject to changes and updates. Users are advised to review it periodically.
 




















Neurolyzer Plugin: Advanced Stealth and Privacy for Pwnagotchi

The Neurolyzer plugin has evolved into a powerful tool for enhancing the stealth and privacy of your Pwnagotchi. Now at version 1.5.2, it goes beyond simple MAC address randomization to provide a comprehensive suite of features that minimize your device’s detectability by network monitoring systems, Wireless Intrusion Detection/Prevention Systems (WIDS/WIPS), and other security measures. By reducing its digital footprint while scanning networks, Neurolyzer ensures your Pwnagotchi operates discreetly and efficiently.

Here’s a detailed look at the updates, what’s new, and how Neurolyzer 1.5.2 improves upon its predecessors.
Key Features and Improvements

1. Advanced WIDS/WIPS Evasion

       What’s New: A sophisticated system to detect and evade WIDS/WIPS.
       How It Works: Scans for known WIDS/WIPS SSIDs (e.g., "wids-guardian", "airdefense") and triggers evasion tactics like MAC address rotation, channel hopping, TX power adjustments, and random delays.
       What’s Better: Proactively avoids detection in secured environments, making your Pwnagotchi stealthier than ever.

2. Hardware-Aware Adaptive Countermeasures

       What’s New: Adapts to your device’s hardware capabilities.
       How It Works: Detects support for TX power control, monitor mode, and MAC spoofing at startup, tailoring operations accordingly.
       What’s Better: Ensures compatibility and stability across diverse Pwnagotchi setups, avoiding errors from unsupported features.

3. Atomic MAC Rotation with Locking Mechanism

       What’s Improved: MAC changes are now atomic, using an exclusive lock.
       How It Works: A lock file prevents conflicts during MAC updates, ensuring smooth execution.
       What’s Better: Enhances reliability, especially on resource-constrained devices or with multiple plugins.

4. Realistic MAC Address Generation with Common OUIs

       What’s Improved: Generates MAC addresses using OUIs from popular manufacturers (e.g., Raspberry Pi, Apple, Cisco).
       How It Works: In noided mode, it combines a real OUI with random bytes to mimic legitimate devices.
       What’s Better: Blends into network traffic, reducing suspicion compared to fully random MACs in earlier versions.

5. Flexible Operation Modes

    What’s New: Three modes: normal, stealth, and noided.

    How It Works:
   
        normal: No randomization or evasion.
        stealth: Periodic MAC randomization with flexible intervals (30 minutes to 2 hours).
        noided: Full evasion suite with MAC rotation, channel hopping, TX power tweaks, and traffic throttling.
   
    What’s Better: Offers customizable stealth levels, unlike the simpler normal and stealth modes in prior versions.

7. Robust Command Execution with Retries and Fallbacks

       What’s Improved: Enhanced reliability for system commands.
       How It Works: Retries failed commands and uses alternatives (e.g., iwconfig if iw fails).
       What’s Better: Increases stability across varied setups, fixing issues from inconsistent command execution.

8. Traffic Throttling for Stealth

       What’s New: Limits network traffic in noided mode.
       How It Works: Uses tc to shape packet rates, mimicking normal activity.
       What’s Better: Avoids triggering rate-based WIDS/WIPS alarms, a leap beyond basic MAC randomization.

9. Probe Request Sanitization

       What’s New: Filters sensitive probe requests.
       How It Works: Blacklists identifiable probes using tools like hcxdumptool.
       What’s Better: Hides your device’s identity, adding a privacy layer absent in earlier versions.

10. Enhanced UI Integration

        What’s Improved: Displays detailed status on the Pwnagotchi UI.
        How It Works: Shows mode, next MAC change time, TX power, and channel, with customizable positions.
        What’s Better: Offers real-time monitoring, improving on the basic UI updates of past releases.

11. Improved Error Handling and Logging

        What’s Improved: Better logging and adaptive error responses.
        How It Works: Logs detailed errors/warnings and adjusts to hardware limits.
        What’s Better: Easier troubleshooting and more reliable operation than before.

12. Safe Channel Hopping

        What’s New: Implements safe, regular channel switching.
        How It Works: Uses safe channels (e.g., 1, 6, 11) or dynamically detected ones.
        What’s Better: Reduces detection risk by avoiding static channel use.

13. TX Power Adjustment

        What’s New: Randomizes transmission power in noided mode.
        How It Works: Adjusts TX power within hardware limits using iw or iwconfig.
        What’s Better: Mimics normal device behavior, enhancing stealth over static signal strength.

14. Comprehensive Cleanup on Unload

        What’s Improved: Restores default settings when disabled.
        How It Works: Resets traffic shaping, monitor mode, and releases locks.
        What’s Better: Leaves your device stable post-use, unlike earlier versions with minimal cleanup.

Legacy Improvements Retained and Enhanced

    Initial MAC Randomization: Randomizes the MAC address on load for immediate privacy.
    Monitor Mode Handling: Temporarily switches to managed mode for MAC changes, then back to monitor mode.
    Time-Dependent Randomization: Dynamically calculates MAC change schedules for unpredictability.

Other Features

    Varied Operational Modes: Choose normal, stealth, or noided to match your needs.
    Wi-Fi Interface Customization: Supports custom interface names for flexibility.
    Comprehensive Logging: Tracks events and errors for easy monitoring.
    Seamless Activation/Deactivation: Auto-starts when enabled, ensuring smooth transitions.

Installation Instructions

Requirements

 macchanger: Install with:
   
    sudo apt install macchanger
        
Select "No" when asked about changing the MAC on startup.

Steps:

Clone the Plugin Repository:
Add to /etc/pwnagotchi/config.toml:
        

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

Update and install:


    sudo pwnagotchi update plugins
    sudo pwnagotchi plugins install neurolyzer 

Manual Installation (Alternative)

Clone the repo:
  
    sudo git clone https://github.com/AlienMajik/pwnagotchi_plugins.git
    
    cd pwnagotchi_plugins

Copy and make executable:

    sudo cp neurolyzer.py /usr/local/share/pwnagotchi/custom-plugins/
    sudo chmod +x /usr/local/share/pwnagotchi/custom-plugins/neurolyzer.py

Configure the Plugin:

Edit /etc/pwnagotchi/config.toml:

    main.plugins.neurolyzer.enabled = true
    main.plugins.neurolyzer.wifi_interface = "wlan0mon"  # Your wireless adapter
    main.plugins.neurolyzer.operation_mode = "noided"    # 'normal', 'stealth', or 'noided'
    main.plugins.neurolyzer.mac_change_interval = 3600   # Seconds
    main.plugins.neurolyzer.mode_label_x = 101
    main.plugins.neurolyzer.mode_label_y = 50
    main.plugins.neurolyzer.next_mac_change_label_x = 101
    main.plugins.neurolyzer.next_mac_change_label_y = 60

For maximum stealth:

    personality.advertise = false

Restart Pwnagotchi

Run:

    sudo systemctl restart pwnagotchi

Verify the Plugin

Check logs:
   

        [INFO] [Thread-24 (run_once)] : [Neurolyzer] Plugin loaded. Operating in noided mode.
        [INFO] [Thread-24 (run_once)] : [Neurolyzer] MAC address changed to xx:xx:xx:xx:xx:xx for wlan0mon via macchanger.

Known Issues

    Wi-Fi Adapter Compatibility: Works best with external adapters. Testing on the Raspberry Pi 5’s Broadcom chip showed issues with mode switching and interface control. It may work on other Pi models—please share feedback!

Summary

Neurolyzer 1.5.2 elevates Pwnagotchi’s stealth and privacy with advanced WIDS/WIPS evasion, hardware-aware operations, realistic MAC generation, and flexible modes. Compared to earlier versions, it offers superior reliability (via retries and error handling), deeper stealth (traffic throttling, probe sanitization), and better usability (enhanced UI and logging). Whether you’re testing security or keeping a low profile, Neurolyzer 1.5.2 is a significant upgrade—more versatile, stealthy, and robust than ever.
Neurolyzer Plugin Disclaimer

Please read this disclaimer carefully before using the Neurolyzer plugin ("Plugin") developed for the Pwnagotchi platform.

    General Use: The Neurolyzer Plugin is intended for educational and research purposes only. It is designed to enhance the privacy and stealth capabilities of the Pwnagotchi device during ethical hacking and network exploration activities. The user is solely responsible for ensuring that all activities conducted with the Plugin adhere to local, state, national, and international laws and regulations.

    No Illegal Use: The Plugin must not be used for illegal or unauthorized network access or data collection. The user must have explicit permission from the network owner before engaging in any activities that affect network operations or security.

    Liability: The developers of the Neurolyzer Plugin, the Pwnagotchi project, and any associated parties will not be liable for any misuse of the Plugin or for any direct, indirect, incidental, special, exemplary, or consequential damages (including, but not limited to, procurement of substitute goods or services; loss of use, data, or profits; or business interruption) however caused and on any theory of liability, whether in contract, strict liability, or tort (including negligence or otherwise) arising in any way out of the use of this Plugin, even if advised of the possibility of such damage.

    Network Impact: Users should be aware that randomizing MAC addresses and altering device behavior can impact network operations and other users. It is the user's responsibility to ensure that their activities do not disrupt or degrade network performance and security.

    Accuracy and Reliability: While efforts have been made to ensure the reliability and functionality of the Neurolyzer Plugin, the developers make no representations or warranties of any kind, express or implied, about the completeness, accuracy, reliability, suitability, or availability with respect to the Plugin or the information, products, services, or related graphics contained within the Plugin for any purpose. Any reliance placed on such information is therefore strictly at the user's own risk.

    Modification and Discontinuation: The developers reserve the right to modify, update, or discontinue the Plugin at any time without notice. Users are encouraged to periodically check for updates to ensure optimal performance and compliance with new regulations.

By using the Neurolyzer Plugin, you acknowledge and agree to this disclaimer. If you do not agree with these terms, you are advised not to use the Plugin.







ProbeNpwn Plugin v1.3.0

The ProbeNpwn Plugin is an aggressively enhanced evolution of the original Instattack by Sniffleupagus, now supercharged for maximum Wi-Fi handshake captures! This updated version (1.3.0) introduces a suite of cutting-edge features, including dual operational modes (Tactical and Maniac), client scoring, ML-inspired channel hopping, intelligent retries, handshake deduplication, dynamic concurrency, and more. If you’ve used Instattack, you’ll love ProbeNpwn it combines deauthentication and association attacks into one powerful, adaptable tool designed to capture handshakes faster and smarter than ever before.



Key Features:





    Efficient Deauthentication & Association Attacks:
    Launch both simultaneously to force devices to reconnect quickly, maximizing handshake captures.



    Concurrent Attack Threads:
    Handle multiple networks and clients at once with multi-threading for efficient, parallel attacks.



    Customizable Settings:
    Fine-tune attack behavior, enable/disable features, and whitelist networks or clients via config.toml.



    Capture More Handshakes:
    Aggressive methods ensure rapid device reconnections, boosting handshake capture rates.



    Comprehensive Logging:
    Track every attack and capture with detailed logs for performance insights.



    Lightweight and Seamless Integration:
    Fully compatible with Pwnagotchi for easy setup and operation.



What’s New in ProbeNpwn v1.3.0?

This release introduces eight major enhancements that make ProbeNpwn smarter, more adaptable, and relentless in capturing handshakes:

1. Dual Operational Modes: Tactical and Maniac 🧠💥





What’s New:
Choose between two modes:





    Tactical Mode: Strategic and efficient, focusing on high-value targets.



    Maniac Mode: Unrestricted and aggressive, attacking all targets rapidly.



How It Works:





Configurable via config.toml (main.plugins.probenpwn.mode).



Tactical Mode: Prioritizes targets with high client scores and respects cooldowns/whitelists.



Maniac Mode: Bypasses restrictions, using minimal delays (0.05s) for maximum attack frequency.



Why It’s Better:





Flexibility: Tailor the plugin to your needs—precision or brute force.



Control: Switch modes based on the environment or your goals.

2. Client Scoring System 🎯





What’s New:
Clients are scored based on signal strength and activity to prioritize high-value targets.



How It Works:





Scores calculated as (signal + 100) * activity.



In Tactical Mode, only clients with scores ≥50 are attacked.



Why It’s Better:





Efficiency: Focuses attacks on clients most likely to yield handshakes.



Resource Optimization: Reduces wasted effort on low-value targets.

3. ML-Inspired Channel Hopping 📡





What’s New:
Intelligent channel selection based on historical success and activity.



How It Works:





Tracks APs, clients, and handshake successes per channel.



Uses weighted random selection to favor active, successful channels.



Why It’s Better:





Optimized Focus: Spends more time on productive channels.



Adaptability: Adjusts dynamically to the Wi-Fi environment.

4. Intelligent Retry Mechanism with Exponential Backoff 🔄





What’s New:
Retries failed handshake attempts with increasing delays to balance persistence and efficiency.



How It Works:





Uses exponential backoff (starting at 1s, capping at 60s) for retries.



Scheduled retries are managed via a priority queue.



Why It’s Better:





Persistence: Keeps trying tough targets without overwhelming the system.



Resource Management: Prevents rapid, repeated attempts that could cause issues.

5. Handshake Deduplication and Quality Check ✅





What’s New:
Ensures only unique, valid handshakes are processed.



How It Works:





Deduplicates handshakes using a hash-based system.



Validates handshakes with aircrack-ng, requiring at least two EAPOL frames.



Why It’s Better:





Accuracy: Avoids redundant processing and false positives.



Reliability: Ensures only usable handshakes are counted.

6. Dynamic Concurrency Based on System Resources 🛡️





What’s New:
Adjusts the number of concurrent attack threads based on CPU and memory usage using psutil.



How It Works:





Monitors system load with psutil.cpu_percent() and psutil.virtual_memory().percent.



Scales threads (e.g., from 50 to 10) if usage exceeds thresholds (50% or 80%).



Why It’s Better:





Stability: Prevents crashes or slowdowns, especially in Maniac Mode.



Adaptability: Works across different hardware or load conditions.



Note: psutil is a cross-platform library for retrieving system information. It’s used here to monitor CPU and memory usage, allowing ProbeNpwn to dynamically adjust its concurrency and keep your Pwnagotchi stable during intense operations. If not already installed, you can add it with:


    sudo apt-get install python3-psutil



7. Additional Attack Vector: Fake Authentication Flood 💣





What’s New:
Supplements deauthentication with a 30% chance of a fake authentication flood.



How It Works:





Randomly triggers association attacks with a 0.05s delay.



Why It’s Better:





Diversity: Captures handshakes from APs resistant to deauthentication.



Aggression: Boosts attack frequency, especially in Maniac Mode.

8. Enhanced UI with Handshake Count 📊





What’s New:
The UI now displays the total number of captured handshakes.



How It Works:





Added to the Pwnagotchi screen at configurable coordinates.



Why It’s Better:





Visibility: Real-time feedback on handshake captures.



Motivation: See your success instantly.



Why You’ll Love It

ProbeNpwn v1.3.0 is your handshake-capturing Swiss Army knife:





Smart & Aggressive: Tactical for strategy, Maniac for mayhem.



Efficient: Scoring and concurrency optimize every attack.



Relentless: Retries and floods leave no handshake behind.



Stable: Keeps your Pwnagotchi happy under pressure.

Big props to Sniffleupagus for the original Instattack—this builds on that legacy! 🙏



How to Get Started





Install the Plugin:





Copy probenpwn.py to your Pwnagotchi’s plugins folder.



Install psutil (if not already installed):





Run:

    sudo apt-get install python3-psutil



Why: psutil enables dynamic thread scaling based on system resources, keeping your Pwnagotchi stable during intense operations.



Edit config.toml:

    main.plugins.probenpwn.enabled = true
    main.plugins.probenpwn.mode = "tactical"  # or "maniac"
    main.plugins.probenpwn.attacks_x_coord = 110
    main.plugins.probenpwn.attacks_y_coord = 20
    main.plugins.probenpwn.success_x_coord = 110
    main.plugins.probenpwn.success_y_coord = 30
    main.plugins.probenpwn.handshakes_x_coord = 110
    main.plugins.probenpwn.handshakes_y_coord = 40      
    main.plugins.probenpwn.verbose = true  # For detailed logs



Whitelist (Optional):





Add safe networks/MACs to /etc/pwnagotchi/config.toml under main.whitelist.



Restart & Monitor:



    sudo systemctl restart pwnagotchi





Pro Tip 💡





Use Tactical Mode for efficiency, but switch to Maniac Mode in crowded areas for a handshake bonanza. Just keep an eye on your device’s temperature!




DISCLAIMER

This software is provided for educational and research purposes only. Use of this plugin on networks or devices that you do not own or have explicit permission to test is strictly prohibited. The author(s) and contributors are not responsible for any misuse, damages, or legal consequences that may result from unauthorized or improper usage. By using this plugin, you agree to assume all risks and take full responsibility for ensuring that all applicable laws and regulations are followed.




SnoopR Plugin for Pwnagotchi (v2.0.0)

Welcome to SnoopR, a powerful plugin for Pwnagotchi, the pocket-sized Wi-Fi security testing tool! SnoopR supercharges your Pwnagotchi by detecting and logging Wi-Fi and Bluetooth devices, identifying potential snoopers based on movement patterns, and presenting everything on an interactive, real-time map. Whether you're a security enthusiast, a tinkerer, or just curious about the wireless world around you, SnoopR has something to offer.

    This updated version (2.0.0) brings a host of new features, including richer data collection, smarter snooper detection, whitelisting, automatic data pruning, and an improved web interface. It’s     
    actively developed, community-driven, and packed with capabilities to help you explore and secure your wireless environment. Let’s dive into what SnoopR can do and how you can get started!

Features:

SnoopR is loaded with capabilities to make your wireless adventures both fun and insightful. Here’s what it brings to the table:

    Enhanced Device Detection: Captures Wi-Fi and Bluetooth devices with additional details like Wi-Fi channel and authentication mode, alongside GPS coordinates for precise location tracking. The SQLite  
    database now includes new columns—channel (INTEGER) for Wi-Fi channel (e.g., 1, 6, 11) and auth_mode (TEXT) for authentication mode (e.g., WPA2, WEP)—offering deeper insights into network configurations 
    for security testing and auditing.

    Improved Snooper Identification: Spots potential snoopers with more accurate detection logic—devices that move beyond a customizable threshold (default: 0.1 miles) across at least three detections 
    within a time window (default: 5 minutes) are flagged, reducing false positives. Uses the Haversine formula (Earth’s radius = 3958.8 miles) to calculate movement.

    Whitelisting: Exclude specific networks (e.g., your home Wi-Fi or personal devices) from being logged or flagged to keep your data focused. Configurable via the whitelist option (e.g., ["MyHomeWiFi", 
    "MyPhone"]).

    Automatic Data Pruning: Deletes detection records older than a configurable number of days (default: 30) to manage database size and keep it efficient. Runs on startup with a DELETE query based on a 
    cutoff date.

    Interactive Map: Displays all detected devices on a dynamic map with sorting (by device type or snooper status), filtering (all, snoopers, or Bluetooth), and the ability to pan to a network’s location 
    by clicking on it in the table. Markers are blue for regular devices and red for snoopers.

    Real-Time Monitoring: Shows live counts of detected networks, snoopers, and the last Bluetooth scan time (e.g., "Last Scan: 14:30:00") directly on the Pwnagotchi UI at position (7, 135).

    Customizable Detection: Fine-tune movement and time thresholds to define what qualifies as a snooper, tailored to your needs.

    Reliable Bluetooth Scanning: Includes a retry mechanism (up to three attempts with 1-second delays) for more consistent device name retrieval via hcitool name, ensuring better accuracy. Detects devices 
    with hcitool inq --flush.

    Threaded Scans: Bluetooth scans run in a separate thread every 45 seconds (configurable), ensuring smooth performance without interrupting other operations.

    Better Logging and Error Handling: Improved logging for GPS warnings (e.g., unavailable coordinates) and Bluetooth errors (e.g., hcitool failures), making it easier to debug and maintain.


Requirements:

Before installing SnoopR, ensure you have the following:

    GPS Adapter: Connected via bettercap (easily done with the gps plugin). GPS is essential for logging device locations.
    
    Bluetooth Enabled: Required for Bluetooth scanning. Ensure Bluetooth is activated on your Pwnagotchi (sudo hciconfig hci0 up).
    
    Internet Access (for Viewing): The device you use to view the web interface (e.g., your phone or computer) needs internet to load map tiles and Leaflet.js. The Pwnagotchi itself doesn’t require an 
    internet connection.


Installation Instructions:

You can install SnoopR in two ways: the easy way (recommended) or the manual way. Here’s how:

Easy Way (Recommended)

Update Your Config FileEdit /etc/pwnagotchi/config.toml and add the following lines to enable custom plugin repositories:

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


Install the PluginRun these commands to update the plugin list and install SnoopR:

    sudo pwnagotchi update plugins
    
    sudo pwnagotchi plugins install snoopr



That’s it! You’re ready to configure SnoopR.

Manual Way (Alternative)
If you prefer a hands-on approach:

Clone the SnoopR plugin repo from GitHub:

    sudo git clone https://github.com/AlienMajik/pwnagotchi_plugins.git
    
    cd pwnagotchi_plugins


Copy the Plugin FileMove snoopr.py to your Pwnagotchi’s custom plugins directory:

    sudo cp snoopr.py /usr/local/share/pwnagotchi/custom-plugins/

Alternatively, if you’re working from a computer, use SCP:

    sudo scp snoopr.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/




Configuration:
To enable and customize SnoopR, edit /etc/pwnagotchi/config.toml and add the following under the [main.plugins.snoopr] section:

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

Available Options:

    enabled: Set to true to activate the plugin. Default: false
    
    path: Directory for the SQLite database (e.g., /root/snoopr/snoopr.db). Default: /root/snoopr
    
    ui.enabled: Show stats on the Pwnagotchi UI. Default: true
    
    gps.method: GPS data source (only "bettercap" supported). Default: "bettercap"
    
    movement_threshold: Minimum distance (miles) a device must move to be flagged as a snooper. Default: 0.1
    
    time_threshold_minutes: Time interval (minutes) between detections for snooper checks. Default: 5
    
    bluetooth_enabled: Enable Bluetooth scanning. Default: false
    
    timer: Interval (seconds) between Bluetooth scans. Default: 45
    
    whitelist: List of network names (SSIDs or Bluetooth device names) to exclude from logging. Default: []
    
    prune_days: Number of days to retain detection records before pruning. Default: 30

After editing the config, restart your Pwnagotchi to apply the changes:

    sudo systemctl restart pwnagotchi

Database Schema Updates:

On startup, SnoopR checks the detections table for channel and auth_mode columns using PRAGMA table_info. If missing, it adds them with ALTER TABLE commands, logging the updates (e.g., [SnoopR] Added "channel" column to detections table) for seamless compatibility.

Usage
Once installed and configured, SnoopR runs automatically when you power up your Pwnagotchi. Here’s how it works:

    Wi-Fi Logging: Logs Wi-Fi access points with details like MAC, SSID, channel, authentication mode, encryption, signal strength, and location. Skips whitelisted SSIDs during on_unfiltered_ap_list.
    
    Bluetooth Scanning: If enabled, scans for Bluetooth devices every timer seconds using hcitool inq --flush, logging their details and locations. Retries name retrieval up to three times with hcitool name.
    
    Snooper Detection: Flags devices as snoopers if they move beyond movement_threshold across at least three detections within time_threshold_minutes. Updates the is_snooper flag in the networks table.
    
    Whitelisting: Excludes specified networks from being logged or flagged during Wi-Fi and Bluetooth scans.
    
    Data Pruning: Automatically deletes old detection records from the detections table on startup if older than prune_days.

Monitoring the UI
Your Pwnagotchi’s display will show real-time stats (if ui.enabled is true):

Number of detected Wi-Fi networks and snoopers
Number of detected Bluetooth devices and snoopers (if enabled)
Time of the last Bluetooth scan (e.g., "Last Scan: 14:30:00")

Viewing Logged Networks
To see detailed logs and the interactive map, access the web interface:

Connect to Your Pwnagotchi’s Network  

Via USB: Typically 10.0.0.2
Via Bluetooth tethering: Typically 172.20.10.2


Open the Web InterfaceIn a browser on a device with internet access:

USB: http://10.0.0.2:8080/plugins/snoopr/
Bluetooth: http://172.20.10.2:8080/plugins/snoopr/


Explore the Interface  

Table: Lists all detected networks with sorting (by "Device Type" or "Snooper") and filtering ("All Networks," "Snoopers," or "Bluetooth Networks").

Map: Shows device locations—click a network in the table to pan the Leaflet.js map to its marker (blue for regular, red for snoopers) with popups showing details.
Scroll Buttons: "Scroll to Top" and "Scroll to Bottom" for easy navigation of long lists.




Notes

Database: All data is stored in snoopr.db in the directory specified by path.

Data Pruning: Detection records older than prune_days are automatically deleted to manage database size.

GPS Dependency: Logging requires GPS data. If unavailable (latitude/longitude = "-"), a warning is logged, and Bluetooth scans are skipped.

Web Interface Requirements: The viewing device needs internet to load Leaflet.js and OpenStreetMap tiles.

Bluetooth Troubleshooting: If scanning fails, ensure hcitool is installed and Bluetooth is enabled (sudo hciconfig hci0 up).

Logging: Improved logging for GPS and Bluetooth issues (e.g., [SnoopR] Error running hcitool: <error>), aiding in debugging.


Community and Contributions
SnoopR thrives thanks to its community! We’re always improving the plugin with new features and fixes. Want to get involved? Here’s how:

Contribute: Submit pull requests with enhancements or bug fixes.
Report Issues: Found a bug? Let us know on the GitHub Issues page.
Suggest Features: Have an idea? Share it with us!

Join the fun and help make SnoopR even better.

Disclaimer
SnoopR is built for educational and security testing purposes only. Always respect privacy and adhere to local laws when using this plugin. Use responsibly!







SkyHigh Plugin for Pwnagotchi

SkyHigh is a custom plugin for Pwnagotchi that enables you to track nearby aircraft using the OpenSky Network API. It displays the number of detected aircraft on your Pwnagotchi’s screen and provides a detailed map view via a webhook, featuring aircraft types, DB flags, and distinct icons for airplanes and helicopters. The plugin also includes a pruning feature to keep the log clean by removing outdated aircraft data.



Why It Works





    API Integration: SkyHigh uses the OpenSky Network API to fetch real-time aircraft data within a configurable radius of your Pwnagotchi’s GPS coordinates (or static coordinates if GPS isn’t available). This ensures accurate and current information 
    about aircraft in your area.



    Dynamic GPS Support: With a GPS adapter connected to BetterCAP, SkyHigh uses real-time coordinates for precise tracking. Without GPS, it relies on default coordinates set in the configuration.



    Efficient Data Management: A pruning mechanism removes aircraft data older than a specified time (default: 10 minutes), keeping the log file lightweight and relevant.



    Visual Feedback: The plugin updates the Pwnagotchi screen with the aircraft count and provides a webhook with a map and table, enhancing the user experience with clear visuals and detailed data.



How It Works





    Data Fetching: The plugin queries the OpenSky API every 60 seconds (configurable) to retrieve aircraft data within the specified radius of your coordinates.



    Metadata Enrichment: For each aircraft, it fetches additional details like the model, origin country, and DB flags using the aircraft’s ICAO24 code.



    Pruning: Aircraft not seen within the prune_minutes interval are removed from the log to maintain efficiency.



    UI Display: The Pwnagotchi screen shows the number of detected aircraft, refreshed periodically.



    Webhook Map: The webhook (/plugins/skyhigh/) renders a table and interactive map with aircraft details, including scrollable navigation.



Installation and Usage

Prerequisites:

    A Pwnagotchi device with internet access.

    GPS Adapter: For dynamic tracking, simply connect a GPS adapter to your Pwnagotchi and configure it with BetterCAP. The plugin will use real-time coordinates if available, falling back to static ones otherwise.



(Optional) A GPS module for dynamic coordinate tracking.

Step-by-Step Installation:

You can install SkyHigh in two ways: the easy way (recommended) or the manual way. Here’s how:

Easy Way (Recommended)

Update Your Config FileEdit /etc/pwnagotchi/config.toml and add the following lines to enable custom plugin repositories:

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


Install the PluginRun these commands to update the plugin list and install SnoopR:

    sudo pwnagotchi update plugins
    
    sudo pwnagotchi plugins install skyhigh



That’s it! You’re ready to configure SnoopR.

Manual Way (Alternative)
If you prefer a hands-on approach:

Clone the SkyHigh plugin repo from GitHub:

    sudo git clone https://github.com/AlienMajik/pwnagotchi_plugins.git
    
    cd pwnagotchi_plugins


Copy the Plugin FileMove snoopr.py to your Pwnagotchi’s custom plugins directory:

    sudo cp skyhigh.py /usr/local/share/pwnagotchi/custom-plugins/

Alternatively, if you’re working from a computer, use SCP:

    sudo scp skyhigh.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/


Configure the Plugin:

Edit your config.toml file (typically located at /etc/pwnagotchi/config.toml) and add the following section:


    main.plugins.skyhigh.enabled = true
    main.plugins.skyhigh.timer  = 60  # Fetch data every 60 seconds
    main.plugins.skyhigh.aircraft_file = "/root/handshakes/skyhigh_aircraft.json"
    main.plugins.skyhigh.adsb_x_coord = 160  # Screen X position
    main.plugins.skyhigh.adsb_y_coord = 80   # Screen Y position
    main.plugins.skyhigh.latitude = -66.273334  # Default latitude
    main.plugins.skyhigh.longitude = 100.984166  # Default longitude
    main.plugins.skyhigh.radius = 50  # Radius in miles
    main.plugins.skyhigh.prune_minutes = 10  # Prune data older than 10 minutes



Enable GPS (Optional):

If you have a GPS adapter, connect it to your Pwnagotchi with gps plugin and configure it in config.toml with BetterCAP:

    main.plugins.gps.enabled = true
    main.plugins.gps.device = "/dev/ttyUSB0"  # Adjust to your GPS device path



Restart Pwnagotchi with:

    pwnkill

Or:

    Rebooting the pwnagotchi

    
Usage

On-Screen Display: The Pwnagotchi screen will show the number of detected aircraft, updating every minute (or as configured).



Webhook Access:


    1.Open a browser and go to http://<pwnagotchi-ip>/plugins/skyhigh/ to view a detailed map and table of aircraft data.

    2.From pwnagotchi plugins page you can just click on skyhigh plugin to open it as well

The map uses distinct icons for helicopters and airplanes, with popups showing callsign, type, and altitude.



Configuration Options





timer: Interval in seconds for fetching data (default: 60).



aircraft_file: Path to store aircraft data (default: /root/handshakes/skyhigh_aircraft.json).



adsb_x_coord and adsb_y_coord: Screen coordinates for the aircraft count display.



latitude and longitude: Default coordinates if GPS is unavailable.



radius: Search radius in miles for aircraft data.



prune_minutes: Time in minutes after which old data is pruned (default: 10). Set to 0 to disable pruning.



Known Issues and Solutions





Transient Network Errors: The SkyHigh plugin may encounter a temporary error that causes it to stop working for 1–2 minutes before resuming automatically. This issue appears to be related to a network connectivity problem when fetching data from the OpenSky Network API.





Description: The plugin logs an error like [SkyHigh] Error fetching data from API: <error details> but recovers on the next fetch cycle.



Solution: No action is needed; the plugin is designed to handle these transient errors gracefully and resumes operation automatically. If persistent, check your internet connection.



Why You’ll Love It





Real-Time Awareness: Track aircraft activity around you as it happens.



Flexible Configuration: Customize the radius, update interval, and pruning to fit your preferences.



Interactive Map: The webhook’s visual interface makes it easy to explore aircraft details.

Take your Pwnagotchi to the skies with SkyHigh! ✈️

This plugin fetches nearby aircraft data using the OpenSky Network API.

Acknowledgment: Aircraft data is provided by the OpenSky Network.
Disclaimer: This plugin is not affiliated with OpenSky Network. Data is used in accordance with their API terms.
