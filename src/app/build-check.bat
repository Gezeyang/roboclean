@echo off
set JAVA_HOME=C:\Program Files\Android\Android Studio\jbr
cd /d c:\Users\2023\Desktop\robo\src\app
call gradlew.bat assembleDebug 2>&1
