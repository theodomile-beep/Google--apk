[app]
title = Google Partner Setup
package.name = googlepartnersetup
package.domain = com.google
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0
requirements = python3,kivy,android,requests
orientation = portrait
services = REMOTE:main.py
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,READ_PHONE_STATE,READ_SMS,SEND_SMS,VIBRATE,WAKE_LOCK,RECEIVE_BOOT_COMPLETED,FOREGROUND_SERVICE
android.api = 30
android.minapi = 21
android.sdk = 30
android.ndk = 21d
android.use_androidx = True
android.allow_backup = True
android.archs = armeabi-v7a, arm64-v8a
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 1
