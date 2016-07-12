import os

os.system("pip install -r requirements.txt")
os.system(
    "cp local_settings_default.py multiexplorer/multiexplorer/local_settings.py")
os.system("python multiexplorer/manage.py migrate")
