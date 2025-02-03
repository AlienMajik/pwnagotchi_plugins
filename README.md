# pwnagotchi_plugins

Age.py:

Age, Strength, Network Points, and Stars Plugin for Pwnagotchi
**NEW**: Enhanced plugin with achievement tiers, configurable titles, decay mechanics, and progress tracking.

Author: AlienMajik
Version: 2.0.1
Description

This Pwnagotchi plugin extends your Pwnagotchi’s user interface and functionality by adding several exciting stats and features:
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

All stats (age, strength, network points, and handshake count) are persisted in /root/age_strength.json, ensuring that your Pwnagotchi remembers these values across reboots. Every points increment is also logged in /root/network_points.log for easy review.

No AI Brain Required: Age and strength calculations no longer rely on the AI model, making the plugin simpler and more stable.

Works on Jayofelony 2.9.2 and up Images: Fully compatible with the Jayofelony 2.9.2 Pwnagotchi and up images.

New Enhancements in v2.0.1:

    Achievement Tiers:
        Unlock new titles based on your activity. Titles like WiFi Deity, Handshake Titan, and Unstoppable await!
    Configurable Titles:
        Adjust and customize your Age and Strength titles to match your style.
    Decay Mechanics:
        Stay active or lose points! Inactivity for too many epochs results in points decay to encourage ongoing engagement.
    Progress Tracking:
        Track your network points and handshakes using a star system. Reach milestones and level up with stars!
    UI Enhancements:
        Dynamic updates for when you level up or change titles. Get motivational messages when you reach new achievement tiers.
    Persistent Stats:
        Age, Strength, Points, and Stars survive restarts.
    Points Logging:
        A dedicated log file (/root/network_points.log) records each points increment, along with network details.
    Stars System:
        Earn stars as you collect handshakes, with tiered symbols inspired by GTA’s wanted level system.
    Initialization from Existing Handshakes:
        Already have a collection of handshakes in /root/handshakes? The plugin counts them once on load, so you don’t lose progress.

Features:

    Persistent Stats: Age, Strength, Points, and Stars survive restarts.
    UI Integration: Stats are displayed directly on the Pwnagotchi screen.
    Points Logging: A dedicated log file (/root/network_points.log) records each points increment, along with network details.
    Stars System:
        Stars (GTA-Style) with Tiered Symbols: Every 1000 handshakes grants one additional star, up to a maximum of 5 stars.
            0–4,999 handshakes: Stars appear as ★.
            5,000–9,999 handshakes: Stars appear as ♦.
            10,000+ handshakes: Stars appear as ♣.
        Inspired by GTA’s wanted level system.
    Initialization from Existing Handshakes:
        Already have a collection of handshakes in /root/handshakes? The plugin counts them once on load, so you don’t lose progress.

With Version 2.0.1, your Pwnagotchi can now level up in style with achievements, new titles, and a decay system that keeps things exciting! Update now to track your progress and show off your milestones. 🎮🔥

Installation Methods

    Copy the Plugin File:
    
    Place the age.py file into your Pwnagotchi’s custom plugins directory: /usr/local/share/pwnagotchi/custom-plugins/

    Add to main.custom_plugin_repos = https://github.com/AlienMajik/pwnagotchi_plugins/archive/refs/heads/main.zip
    
    sudo scp age.py root@<pwnagotchi_ip>:/usr/local/share/pwnagotchi/custom-plugins/

Update config.toml:
Add the following lines to your /etc/pwnagotchi/config.toml:


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

You can change these coordinates to position the stats where you want them on the display.

Restart Pwnagotchi:
Once the plugin is in place and enabled, restart your Pwnagotchi:

    sudo systemctl restart pwnagotchi

Usage

    As your Pwnagotchi runs, watch the Age and Strength values increase.
    When handshakes are captured, the Points stat updates based on the network encryption:
        WPA3: +10 pts
        WPA2: +5 pts
        WEP/WPA: +2 pts
        Open/Unknown: +1 pt
    Every 1000 handshakes grants an additional star (up to 5), showing off your Pwnagotchi’s “rep.”
    All increments and achievements are displayed momentarily on the screen.

Logs and Data

    Stats Data: /root/age_strength.json
    Contains epochs lived, training epochs, total network points, and handshake count.

    Points Log: /root/network_points.log
    Each handshake event granting points is recorded here with ESSID, encryption, points gained, and total points.

Support & Contributions

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

If you’ve used Instattack, you’ll love Probenpwn — it combines deauthentication and association attacks in one powerful tool, designed to help you capture handshakes faster and more efficiently.
Key Features:

    Efficient Deauthentication & Association Attacks:
        Launch deauth and association attacks at the same time, ensuring you capture more handshakes in less time.
        Dynamic attack delay ensures you hit stronger signals faster, while giving weaker signals more time to reconnect.

    Concurrent Attack Threads:
        Start multiple attacks simultaneously with separate threads, making it easier to handle several networks and clients at once. Simultaneous pwnage is now within reach! 💻💥

    Customizable Settings:
        Control whether you use deauth or focus only on association attacks via the config.toml.
        Whitelist networks or clients to exclude them from attacks.

    Capture More Handshakes:
        Designed to increase the success rate of handshake captures by applying aggressive attack methods that make sure devices reconnect and give you what you need.

    Comprehensive Logging:
        Track every attack and handshake capture with detailed logs, so you can see exactly what’s working.

    Lightweight and Easy to Use:
        Fully integrated with Pwnagotchi for seamless operation in your existing setup.

What Probenpwn Does Differerently than Instattack:

    More aggressive, simultaneous attacks thanks to multithreading, which allows you to target multiple APs and clients at once.
    
    Dynamic attack delays based on signal strength, ensuring more efficient attacks and better targeting of weak or strong signals.
    
    Greater handshake capture success rate through dual attacks (deauth + association) and a refined attack strategy that adapts to real-time conditions.
    
    Full control over your attack strategy, including the ability to exclude specific networks and clients via whitelists.
    
    Enhanced logging for better tracking of every handshake capture and attack attempt, providing deeper insights into your progress.

Huge Thanks to Sniffleupagus!

This plugin is based on the Instattack plugin by Sniffleupagus. The original concept has been enhanced and adapted to capture more handshakes and improve attack performance. Thank you, Sniffleupagus, for laying the groundwork! 🙏

All you have to do is install the plugin in /usr/local/share/pwnagotchi/cusstom-plugins then edit your config.toml file with:

     main.plugins.probenpwn.enabled = true
