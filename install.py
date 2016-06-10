import os

os.system("pip install -r requirements.py")
os.system("cp local_settings_default.py multiexplorer/local_settings.py")
os.system("python multiexplorer/manage.py migrate")
