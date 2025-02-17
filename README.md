# pwnagotchi_plugins

Age.py:
Age, Strength, Network Points, and Stars Plugin for Pwnagotchi v2.0.2

Author: AlienMajik
Version: 2.0.2
Description: Enhanced plugin with achievement tiers, configurable titles, decay mechanics, progress tracking, and dynamic status messages.
Key Stats:

    Age (♥ Age): Tracks how many epochs your Pwnagotchi has lived, now without any reliance on the AI brain.
    Strength (Str): Reflects how much your Pwnagotchi has "trained," increasing every 10 epochs.
    Network Points (★ Pts): Earn points by capturing handshakes, with the number of points determined by the encryption strength of the networks encountered:
        WPA3: +10 points
        WPA2: +5 points
        WEP/WPA: +2 points
        Open/Unknown: +1 point
    
Stars (GTA-Style) with Tiered Symbols: Every 1000 handshakes grants one additional star, up to a maximum of 5 stars.
       
        0–4,999 handshakes: Stars appear as ★.
        5,000–9,999 handshakes: Stars appear as ♦.
        10,000+ handshakes: Stars appear as ♣.

This provides a fun, evolving visual progression as your handshake count climbs. The plugin also counts existing handshakes in /root/handshakes, so you never start from zero!
New Enhancements in v2.0.2:

    Dynamic Status Messages:
        Motivational Quotes: Displayed when the user levels up in age or strength (e.g., "You're a WiFi wizard in the making!").
        Inactivity Messages: Shown when the agent undergoes decay due to inactivity (e.g., "Time to wake up, you're rusting!").
        These dynamic messages are randomly chosen and help keep the user engaged, providing a personalized experience as they reach milestones or experience inactivity.

    Improved Age and Strength Titles:
        The titles for both age and strength have been revised to be more interesting and engaging:
            Age Titles: "Neon Spawn," "WiFi Outlaw," "Data Raider," etc.
            Strength Titles: "Fleshbag," "Deauth King," "Handshake Hunter," etc.
        These titles make the progression more varied and fun, allowing users to see their growth in a more exciting way.

    Updated UI:
        The UI now includes a section showing users their current stats, including Age, Strength, Network Points, and Stars, as well as dynamic updates reflecting achievements or decay status.

    Updated Logging and Milestones:
        The logging system has been maintained and now includes milestone tracking for key intervals (e.g., every 100 epochs).
        Milestones trigger UI updates with faces and messages to keep the agent engaged as they reach new achievements.

Features:

    Persistent Stats: Age, Strength, Points, and Stars survive reboots, ensuring no progress is lost.
    UI Integration: Stats, progress, and decay messages are displayed directly on the Pwnagotchi screen.
    Points Logging: Every points increment is logged in /root/network_points.log along with network details.
    Star System:
        Every 1000 handshakes grants one additional star, up to a maximum of 5 stars.
        0–4,999 handshakes: Stars appear as ★.
        5,000–9,999 handshakes: Stars appear as ♦.
        10,000+ handshakes: Stars appear as ♣.
    Decay Mechanism: Inactivity causes points decay after a specified number of epochs.
    Dynamic Status Messages: Motivational quotes and inactivity messages keep users engaged.

Installation Instructions:

 Copy the Plugin File: Place the age.py file into your Pwnagotchi’s custom plugins directory:

    /usr/local/share/pwnagotchi/custom-plugins/

Alternatively, clone it from GitHub:

    sudo scp age.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/

Update config.toml: Add the following lines to your /etc/pwnagotchi/config.toml:

    main.plugins.age.enabled = true
    main.plugins.age.age_x_coord = 101
    main.plugins.age.age_y_coord = 80
    main.plugins.age.str_x_coord = 160
    main.plugins.age.str_y_coord = 80
    main.plugins.age.decay_interval = 50
    main.plugins.age.decay_amount = 5
    main.plugins.age.points_x_coord = 10
    main.plugins.age.points_y_coord = 100
    main.plugins.age.stars_x_coord = 10
    main.plugins.age.stars_y_coord = 120
    main.plugins.age.max_stars = 5
    main.plugins.age.star_interval = 1000

Restart Pwnagotchi: After adding the plugin and configuring it, restart your Pwnagotchi:

    sudo systemctl restart pwnagotchi

Usage:

    As your Pwnagotchi runs, watch the Age, Strength, and Network Points stats increase.
    Handshakes are captured to update the Points stat based on network encryption:
        WPA3: +10 pts
        WPA2: +5 pts
        WEP/WPA: +2 pts
        Open/Unknown: +1 pt
    Every 1000 handshakes grants an additional star, showing off your Pwnagotchi’s “rep.”
    Decay: Inactivity causes points decay after a specified number of epochs, tracked by the plugin.

Logs and Data:

    Stats Data: /root/age_strength.json
    Contains epochs lived, training epochs, total network points, handshake count, and decay progress.

    Points Log: /root/network_points.log
    Each handshake event granting points is recorded here with ESSID, encryption, points gained, and total points.

Support & Contributions:

Feel free to open issues or pull requests to improve this plugin or suggest new features. Enjoy leveling up your Pwnagotchi’s stats!





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

Add adsbsniffer.py to /usr/local/share/pwnagotchi/installed-plugins and /usr/local/share/pwnagotchi/availaible-plugins

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
 




















Neurolyzer Plugin:
The Neurolyzer plugin introduces a significant enhancement to the Pwnagotchi platform, aiming to augment the device's stealth and privacy capabilities. Its main function is to automate the randomization of the MAC address for the designated Wi-Fi interface. This action helps make the Pwnagotchi less visible to network monitoring systems, thereby decreasing its digital footprint within the networks it scans. The plugin offers several noteworthy features:

    Varied Operational Modes: It introduces different modes of operation, including a 'stealth' mode. When activated, this mode triggers periodic changes to the device's MAC address, effectively masking its identity. This is particularly useful for operating within networks that are under strict surveillance.

    Adjustable MAC Address Change Interval: The plugin allows users to customize how frequently the MAC address changes, providing control over the degree of stealth based on the user's needs.

    User Interface Enhancements: Leveraging Pwnagotchi's existing UI framework, the Neurolyzer plugin offers immediate visual feedback on the device's screen. It displays the current mode of operation ('stealth' or 'normal') and the time until the next MAC address change. These interface elements are adjustable, enabling users to customize their display positions as needed.

    Wi-Fi Interface Customization: Users have the flexibility to define which Wi-Fi interface the plugin should manage, catering to devices with multiple or unconventional interface names.

    Seamless Activation/Deactivation: The plugin assesses its activation status upon loading, based on the configured settings, and commences its functions automatically if enabled. This feature allows for a hassle-free transition to stealth mode.

    Comprehensive Logging: The Neurolyzer plugin meticulously logs key events and potential errors during its operation. This aids in monitoring the plugin's performance and simplifying troubleshooting processes.

In essence, the Neurolyzer plugin significantly bolsters the Pwnagotchi's capability for stealthy operations, ensuring users can engage in ethical hacking and network exploration with an enhanced level of privacy. Through its thoughtful integration with the Pwnagotchi ecosystem, the plugin elevates the device's functionality, aligning with the objectives of privacy-conscious users and ethical hackers.

Requirements: Flask
Sudo apt install macchanger

1.When installing macchanger choose no on change mac address on startup.

2.Add neurolyzer.py to /usr/local/share/pwnagotchi/custom-plugins

3.Add this to /etc/pwnagotchi/config.toml: 

main.plugins.neurolyzer.enabled = true
main.plugins.neurolyzer.wifi_interface = "wlan0mon" #Change this to your wireless adapter
main.plugins.neurolyzer.operation_mode = "stealth"  #You can choose between stealh and normal
main.plugins.neurolyzer.mac_change_interval = 3600  #what interval you want you mac address to change in seconds
main.plugins.neurolyzer.mode_label_x = 0
main.plugins.neurolyzer.mode_label_y = 50  # Adjust as needed
main.plugins.neurolyzer.next_mac_change_label_x = 0
main.plugins.neurolyzer.next_mac_change_label_y = 60  # Adjust as needed

4.For full stealh mode change: personality.advertise = false

5.Reboot or sudo systemctl restart pwnagotchi

Neurolyzer Plugin Disclaimer

Please read this disclaimer carefully before using the Neurolyzer plugin ("Plugin") developed for the Pwnagotchi platform.

    General Use: The Neurolyzer Plugin is intended for educational and research purposes only. It is designed to enhance the privacy and stealth capabilities of the Pwnagotchi device during ethical hacking and network exploration activities. The user is solely responsible for ensuring that all activities conducted with the Plugin adhere to local, state, national, and international laws and regulations.

    No Illegal Use: The Plugin must not be used for illegal or unauthorized network access or data collection. The user must have explicit permission from the network owner before engaging in any activities that affect network operations or security.

    Liability: The developers of the Neurolyzer Plugin, the Pwnagotchi project, and any associated parties will not be liable for any misuse of the Plugin or for any direct, indirect, incidental, special, exemplary, or consequential damages (including, but not limited to, procurement of substitute goods or services; loss of use, data, or profits; or business interruption) however caused and on any theory of liability, whether in contract, strict liability, or tort (including negligence or otherwise) arising in any way out of the use of this Plugin, even if advised of the possibility of such damage.

    Network Impact: Users should be aware that randomizing MAC addresses and altering device behavior can impact network operations and other users. It is the user's responsibility to ensure that their activities do not disrupt or degrade network performance and security.

    Accuracy and Reliability: While efforts have been made to ensure the reliability and functionality of the Neurolyzer Plugin, the developers make no representations or warranties of any kind, express or implied, about the completeness, accuracy, reliability, suitability, or availability with respect to the Plugin or the information, products, services, or related graphics contained within the Plugin for any purpose. Any reliance placed on such information is therefore strictly at the user's own risk.

    Modification and Discontinuation: The developers reserve the right to modify, update, or discontinue the Plugin at any time without notice. Users are encouraged to periodically check for updates to ensure optimal performance and compliance with new regulations.

By using the Neurolyzer Plugin, you acknowledge and agree to this disclaimer. If you do not agree with these terms, you are advised not to use the Plugin.



🚀 Probenpwn Plugin - Enhanced Wi-Fi Hacking with Pwnagotchi! 🚀

The Probenpwn Plugin is a more aggressive and enhanced version of the original Instattack by Sniffleupagus, now supercharged for maximum Wi-Fi handshake captures! 🔥

If you’ve used Instattack, you’ll love Probenpwn — it combines deauthentication and association attacks in one powerful tool, designed to help you capture handshakes faster and more efficiently. With the latest updates, it now features dynamic attack tuning, randomization, watchdog recovery, and more!
Key Features:

Efficient Deauthentication & Association Attacks:

    Launch deauth and association attacks simultaneously to capture more handshakes in less time.
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

What's New in Probenpwn 1.1.0:
Dynamic Parameter Tuning:

    The dynamic_attack_delay method now adjusts the attack delay based not only on the client’s signal strength but also on the number of previous attack attempts for a given AP (Access Point). As the number of attacks increases, the delay between attacks decreases slightly, making the attacks more aggressive while preventing the system from overloading.
    The delay is further randomized with random.uniform(0.9, 1.1) to prevent detection by automated systems that might look for consistent attack patterns.

Watchdog Thread for Recovery:

    The plugin introduces a watchdog thread that periodically checks for the presence of the wlan0mon interface, which is essential for monitoring Wi-Fi networks. If this interface is missing (likely due to a Wi-Fi adapter crash), the watchdog attempts to restart the Pwnagotchi system automatically by running a systemctl restart command, providing a more robust recovery mechanism.

Tracking and Limiting Attack Attempts:

    The plugin now tracks the number of attack attempts for each AP using a dictionary (attack_attempts). If an AP has been attacked more than a certain number of times, the delay for subsequent attacks is adjusted to prevent excessive and repetitive attacking, reducing the risk of detection.
    This approach helps balance the aggressiveness of the attacks with performance considerations, ensuring that the plugin remains effective over extended periods.

Tracking Successful Handshakes:

    The plugin now also tracks the number of successful handshakes captured per AP with the success_counts dictionary. Each time a handshake is successfully captured, the count for that AP is incremented. This can be useful for monitoring attack success rates and potentially adjusting attack strategies based on success frequency.

Improved Device Handling:

    The handling of new and updated APs and clients is more refined. The plugin ensures that each device (AP or client) is only attacked if it's not on the whitelist. Devices are also tracked more effectively with better time management, ensuring that only recently seen devices are targeted.
    The track_recent method tracks both APs and clients, with more granular control over when devices should be removed from the recent list based on activity.

Channel Sanitization:

    The plugin includes a new sanitize_channel_list method, which ensures that only valid Wi-Fi channels (1-14 for 2.4 GHz and 36-165 for 5 GHz) are included in the scan list. This prevents attempts to scan invalid channels and ensures more efficient use of scanning resources.

Enhanced Logging and Error Handling:

    The plugin now includes more detailed logging, especially around the dynamic attack delay, attack attempts, and handshakes. The logging makes it easier to monitor the plugin's behavior and diagnose issues.
    It also improves error handling by catching and logging exceptions in key methods, ensuring that the plugin can gracefully handle unexpected issues without crashing.

Better UI Integration:

    The plugin continues to update the Pwnagotchi UI with status messages like "Probing!\nPWNING THEM GUTS!" and ensures the UI reflects the state of the plugin, such as when it's probing aggressively.

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

Exempt specific networks or clients from attacks:

    main.plugins.probenpwn.whitelist = ["00:11:22:33:44:55", "TrustedNetwork"]

Epoch Duration and Recent Tracking:

Control how long attack records are retained before being automatically removed:

    main.plugins.probenpwn.epoch_duration = 60  # Default value in seconds

Personality Settings:

The Pwnagotchi personality settings control whether to perform deauth or association attacks:

    personality.advertise = true
    personality.deauth = true

Example config.toml Snippet:

    main.plugins.probenpwn.enabled = true
    main.plugins.probenpwn.associate_attack_delay = 0.2
    main.plugins.probenpwn.deauth_attack_delay = 0.75
    main.plugins.probenpwn.dynamic_delay_threshold = -60
    main.plugins.probenpwn.epoch_duration = 60
    main.plugins.probenpwn.whitelist = ["00:11:22:33:44:55", "TrustedNetwork"]

Summary

The Probenpwn plugin gives you full control over your Wi-Fi attack strategies, allowing you to:

    Enable or disable the plugin as needed.
    Dynamically adjust attack timing based on client signal strength.
    Launch simultaneous attacks using multi-threading.
    Whitelist specific networks or devices to avoid unintended targeting.
    Customize attack timing and cleanup frequency via epoch duration.
    Leverage your Pwnagotchi personality settings to fine-tune attack behavior.

The plugin now includes advanced features like dynamic tuning, attack attempt tracking, a watchdog recovery system, improved logging, channel sanitization, and better error handling. These changes make the plugin more reliable, flexible, and effective in performing aggressive Wi-Fi probing and attacks.

This plugin is based on the Instattack plugin by Sniffleupagus, with significant enhancements for capturing more handshakes and optimizing attack performance. Huge thanks to Sniffleupagus for the original work! 🙏

DISCLAIMER: This software is provided for educational and research purposes only.
Use of this plugin on networks or devices that you do not own or have explicit permission
to test is strictly prohibited. The author(s) and contributors are not responsible for any 
misuse, damages, or legal consequences that may result from unauthorized or improper usage.
By using this plugin, you agree to assume all risks and take full responsibility for ensuring
that all applicable laws and regulations are followed.
