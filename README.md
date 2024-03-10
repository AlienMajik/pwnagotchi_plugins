# pwnagotchi_plugins
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


