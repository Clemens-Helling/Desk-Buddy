#!/bin/bash
sleep 8
chromium-browser --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --overscroll-history-navigation=0 --touch-events=enabled http://127.0.0.1:8000
