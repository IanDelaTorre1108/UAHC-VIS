import subprocess

# Start each app in a new subprocess
subprocess.Popen(["python", "app.py"])  # Runs on default port 5000
subprocess.Popen(["python", "Administrator/app.py"])  # Customize ports below
subprocess.Popen(["python", "gatepass/app.py"])
