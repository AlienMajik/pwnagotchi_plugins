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







🚀 Probenpwn Plugin - Pwnagotchi! 🚀

The Probenpwn Plugin is a more aggressive and enhanced version of the original Instattack by Sniffleupagus, now supercharged for maximum Wi-Fi handshake captures! 🔥
his updated version (2.0.0) brings a host of new features, including richer data collection, smarter snooper detection, whitelisting, automatic data pruning, and an improved web interface.
If you’ve used Instattack, you’ll love Probenpwn — it combines deauthentication and association attacks in one powerful tool, designed to help you capture handshakes faster and more efficiently. With the latest updates, it now features dynamic attack tuning, randomization, watchdog recovery, performance stats, and more!
Key Features:

Efficient Deauthentication & Association Attacks:

    Launch attacks simultaneously to capture more handshakes in less time.
    Dynamic attack delay ensures you hit stronger signals faster, while giving weaker signals more time to reconnect.

Concurrent Attack Threads:

    Start multiple attacks simultaneously using separate threads, enabling you to handle several networks and clients at once. Simultaneous pwnage is now within reach! 💻💥

Customizable Settings:

    Control whether you use deauth or focus solely on association attacks via the config.toml.
    
    Whitelist networks or clients to exclude them from attacks.

Capture More Handshakes:

    Aggressive attack methods ensure devices reconnect faster, helping you capture more handshakes.

Comprehensive Logging:

    Track every attack and handshake capture with detailed logs, giving you visibility into what’s working.

Lightweight and Easy to Use:

    Fully integrated with Pwnagotchi for seamless operation in your existing setup.

What's New in Probenpwn 1.1.2:

New Features & Enhancements:

Performance Stats and Feedback Loop:

    self.performance_stats: This new dictionary tracks the performance of each AP, including success and failure rates, as well as the number of attempts. This enables dynamic adjustments based on the performance of attacks against specific APs.
    
    self.total_handshakes & self.failed_handshakes: These new counters track the total number of successful and failed handshakes across all APs, contributing to overall performance monitoring.
    
    Dynamic Adjustments: The new adjust_attack_parameters method adjusts the aggressiveness of the attack based on the success rate:
    
        If the success rate is low (below 20%), the attack becomes more aggressive.
        
        If the success rate is high (above 80%), the attack aggressiveness is reduced.
        
        For moderate success rates, the current tactics are maintained.
        
    Logging Success/Failure Rates: After each handshake is captured, the success and failure rates for each AP are logged. This adds valuable insight into how effectively the plugin is working against different APs.
      
Expanded Watchdog Functionality:

    New Log Check: The watchdog now not only checks for the wlan0mon interface but also monitors the logs for the error wifi.interface not set or not found. If this error occurs, the plugin attempts to restart the Pwnagotchi service. This makes the watchdog more robust by addressing multiple failure scenarios.
    
    Logging Improvements: When restarting the service or encountering an error, the plugin logs additional context, such as a success message after restarting the service or the error message if the restart fails.

More Aggressive Attack Tuning:

    The attack_target method now includes a call to adjust_attack_parameters, which fine-tunes the attack aggressiveness based on the success rate of prior attacks. This allows the plugin to adapt its strategy in real-time based on observed performance, making it more efficient over time.
    
    Increased Attack Frequency: For APs with low success rates, the plugin increases the number of attack attempts to try and improve the chances of a successful handshake capture.

Expanded Feedback Loop in Handshake Detection:

    The on_handshake method now calculates and logs the handshake success rate (percentage of successful handshakes over total attack attempts) for each AP. This provides better visibility into how effective the attack is and helps inform the dynamic adjustments made by the plugin.

General Improvements:

    Code Robustness: Additional error handling and logging for potential issues that may arise during the execution of the plugin, especially in the watchdog and during the attack execution process.
    
    Logging Clarity: Improved logging throughout, providing more detailed feedback for debugging and monitoring the plugin's behavior in various situations.

    def load_whitelist: Now loads the whitelist from Pwnagotchi's global config.
    
Summary of What’s Better:

    Dynamic Attack Strategy: The plugin now adjusts the aggressiveness of its attacks based on real-time performance, leading to better handling of different APs and more successful attacks.
    
    Enhanced Logging and Feedback: The plugin logs success and failure rates for handshakes, providing clear insight into its effectiveness. The added performance stats help in tuning attack strategies over time.
    
    Improved Robustness: The watchdog is more resilient, with checks for additional errors (e.g., missing wifi.interface) and the ability to restart the service when necessary.
    
    Adaptability: By adjusting the attack parameters based on success rates, the plugin can adapt its behavior, making it more intelligent and resource-efficient.

Summary:

The Probenpwn plugin gives you full control over your Wi-Fi attack strategies, allowing you to:

    Enable or disable the plugin as needed.
    
    Dynamically adjust attack timing based on client signal strength.
    
    Launch simultaneous attacks using multi-threading.
    
    Whitelist specific networks or devices to avoid unintended targeting.
    
    Customize attack timing and cleanup frequency via epoch duration.
    
    Leverage your Pwnagotchi personality settings to fine-tune attack behavior.

Full Control Over Attack Strategies:

With Probenpwn, you have more control than ever over the attack process. The following parameters in your config.toml file give you full flexibility:
Enabling/Disabling the Plugin:

To enable or disable Probenpwn, modify the [main.plugins.probenpwn] section:

    main.plugins.probenpwn.enabled = true

Attack Timing and Delays:

Probenpwn adjusts attack delay dynamically:

    main.plugins.probenpwn.associate_attack_delay = 0.2    # Base delay for association attacks
    main.plugins.probenpwn.deauth_attack_delay = 0.75      # Base delay for deauthentication attacks
    main.plugins.probenpwn.dynamic_delay_threshold = -60   # Signal threshold for dynamic delay adjustment


Target Whitelisting:
New 1.1.2 Update Now uses /etc/pwnagotchi/config.toml whitelist no need to use this anymore: 
Exempt specific networks or clients from attacks:


    main.plugins.probenpwn.whitelist = ["00:11:22:33:44:55", "TrustedNetwork"]


Epoch Duration and Recent Tracking:

Control how long attack records are retained before being automatically removed:

  
    main.plugins.probenpwn.epoch_duration = 60  # Default value in seconds



Example config.toml Snippet:

    main.plugins.probenpwn.enabled = true
    main.plugins.probenpwn.associate_attack_delay = 0.2
    main.plugins.probenpwn.deauth_attack_delay = 0.75
    main.plugins.probenpwn.dynamic_delay_threshold = -60
    main.plugins.probenpwn.epoch_duration = 60
    

ProbeNpwn logs will up in pwnagotchi.log/pwnagotchi-debug.log as shown:
         
    [INFO] [Thread-11] : Probed and Pwnd!
    
    [INFO] [Thread-27 (attack_target)] : sending association frame to  (xx:xx:xx:xx:xx:xx) on channel 4 [0 clients], -60 dBm...
    
    [INFO] [Thread-11] : Captured handshake from Hidden (xx:xx:xx:xx:xx:xx) -> 'Unknown Client' (xx:xx:xx:xx:xx:xx)()
    
    [INFO] [Thread-27 (attack_target)] : Low success rate (0.00%) on AP xx:xx:xx:xx:xx:xx. Making attack more aggressive.
    
    [INFO] [Thread-272 (attack_target)] : High success rate (100.00%) on AP xx:xx:xx:xx:xx:xx. Reducing attack aggressiveness.

Update Summary:

    Dynamic Attack Strategy: The plugin now adjusts the aggressiveness of its attacks based on real-time performance, leading to better handling of different APs and more successful attacks.
    
    Enhanced Logging and Feedback: The plugin logs success and failure rates for handshakes, providing clear insight into its effectiveness. The added performance stats help in tuning attack strategies over time.
    
    Improved Robustness: The watchdog is more resilient, with checks for additional errors (e.g., missing wifi.interface) and the ability to restart the service when necessary.
    
    Adaptability: By adjusting the attack parameters based on success rates, the plugin can adapt its behavior, making it more intelligent and resource-efficient.


What’s New in ProbeNpwn v1.1.3?

We’ve packed five major enhancements into this release, making ProbeNpwn more effective and stable. Here’s what’s new:
    
1. Minimized Attack Delays ⏱️

       What’s Changed: We’ve slashed attack delays to 0.1 seconds for strong signals (≥ -60 dBm) and 0.2 seconds for weaker ones.
       Why It’s Better: Faster attacks mean more attempts in less time, boosting your chances of capturing handshakes—especially in busy or fast-moving environments.

2. Retry Mechanism for Stubborn APs 🔄

       What’s New: If an AP resists initial attacks, ProbeNpwn now retries with shorter delays after 2 and 5 attempts.
       Why It’s Better: Persistence pays off! This feature ensures the plugin keeps pushing against tough targets, increasing your success rate.

3. Smart Target Prioritization 🎯

       What’s New: APs with more connected clients are now prioritized with reduced attack delays.
       Why It’s Better: Focusing on high-value targets (APs with multiple clients) maximizes handshake opportunities, making your attacks more efficient.

4. Concurrency Throttling with ThreadPoolExecutor 🛡️

       What’s New: We’ve introduced ThreadPoolExecutor to manage a pool of 50 concurrent attack threads, replacing manual thread creation.
       Why It’s Better: This optimizes performance by reusing threads and prevents system overload, ensuring your Pwnagotchi stays responsive even in dense Wi-Fi environments.

5. Channel Coordination 📡

       What’s New: Before each attack, ProbeNpwn syncs with Pwnagotchi’s channel management to ensure it’s on the right channel.
       Why It’s Better: Eliminates missed opportunities due to channel mismatches, ensuring every attack is on target.

Why You’ll Love It

These updates make ProbeNpwn a smarter, faster, and more relentless handshake-capturing tool. Here’s what you’ll experience:

    Lightning-Fast Captures: Minimized delays mean near-maximum attack speed.
    
    Persistent Pursuit: The retry mechanism doesn’t give up on difficult APs.
    
    Resource Efficiency: Throttling with ThreadPoolExecutor prevents crashes while keeping the aggression high.
    
    Optimized Targeting: Prioritization focuses your Pwnagotchi on the best opportunities.

Key Features (Enhanced from v1.1.2)

ProbeNpwn v1.1.3 builds on the solid foundation of v1.1.2, enhancing these core features:

    Efficient Deauth & Association Attacks: Launch both simultaneously for maximum handshake potential.
    
    Concurrent Attack Threads: Handle multiple networks and clients with multi-threading.
    
    Dynamic Attack Tuning: Adjusts delays and aggression based on signal strength and performance.
    
    Whitelist Support: Exclude specific networks or clients from attacks via config.toml.
    
    Comprehensive Logging: Detailed logs track every attack and capture.
    
    Watchdog Recovery: Monitors and restarts Pwnagotchi if the Wi-Fi interface fails.
    
    Lightweight Integration: Seamlessly works with your existing Pwnagotchi setup.
    
    Real-Time UI Feedback: Displays attack counts and successes on your Pwnagotchi screen.
    
ProbeNpwn v1.1.3 is a smarter, more relentless evolution of Wi-Fi handshake capturing. This version introduces intelligent, self-correcting capabilities, allowing the plugin to analyze its own performance in real time and dynamically adjust its attack strategies. The result? Higher efficiency, fewer failed attempts, and a smoother experience as it adapts to whatever the Wi-Fi environment throws its way.

This release also amps up robustness to keep your Pwnagotchi humming. With a watchdog recovery system, improved logging, and enhanced error handling, the plugin powers through interface glitches or service hiccups without breaking a sweat. It’s built to stay reliable and flexible, even during the most aggressive Wi-Fi probing and attacks.

New features take the aggression up a notch:

    Dynamic tuning optimizes attack strategies on the fly.
    
    Attack attempt tracking ensures no opportunity slips through the cracks.
    
    Minimized attack delays (as low as 0.1 seconds for strong signals) keep the pressure on.
    
    Retry mechanisms tackle stubborn access points relentlessly.
    
    Smart target prioritization zeroes in on APs with the most clients for maximum handshake captures.
    
    Concurrency throttling via ThreadPoolExecutor caps threads at 50, keeping your device responsive in dense Wi-Fi zones.
    
    Channel coordination ensures every attack hits the right frequency.

Based on the stellar Instattack plugin by Sniffleupagus, ProbeNpwn v1.1.3 adds these cutting-edge enhancements to capture more handshakes and optimize attack performance like never before. A massive shoutout to Sniffleupagus for laying the groundwork—thank you! 🙏


!!!Config.toml Updates!!!

!!!To take full advantage of v1.1.3’s enhancements, update your config.toml with these settings!!!:


    main.plugins.probenpwn.enabled = true
    main.plugins.probenpwn.attacks_x_coord = 110
    main.plugins.probenpwn.attacks_y_coord = 20
    main.plugins.probenpwn.success_x_coord = 110
    main.plugins.probenpwn.success_y_coord = 30
    main.plugins.probenpwn.verbose = true  # Keep to true for detailed logs putting on false may produce errors at the moment

Note: The whitelist now pulls directly from Pwnagotchi’s global config, so ensure your SSIDs or MACs are listed there.

DISCLAIMER: This software is provided for educational and research purposes only.
Use of this plugin on networks or devices that you do not own or have explicit permission
to test is strictly prohibited. The author(s) and contributors are not responsible for any 
misuse, damages, or legal consequences that may result from unauthorized or improper usage.
By using this plugin, you agree to assume all risks and take full responsibility for ensuring
that all applicable laws and regulations are followed.




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
