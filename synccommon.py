import os, sys
import shutil
import json

import paramiko
from paramiko import SSHClient
from scp import SCPClient


SSH_CONFIG_FILE = "ssh_config.json"

SERVER_ADDR  = ""
SERVER_PORT  = ""
SERVER_USERNAME = ""
SERVER_PASSWORD = ""

SERVER_SOURCE_PATH = "/home/ubuntu/TestApp_Prj/Framework/Common" # edit here
LOCAL_SOURCE_PATH  = "/Users/admin/Desktop/repo_TestApp/Framework/Common" # edit here

APP_FILE = ""
TEST_FILE = ""
LIB_FILES = []

SSH_SERVER_CONNECT_TIMEOUT = 5 #5s
SSH_SERVER_EXEC_TIMEOUT    = 5 #5s

# Variables:
server_ssh = None
app_name = None
g_build_result = False

target_ssh = None

isScpPutCompleted = False


# -------------------------------------------------- GET CONFIGURATION -------------------------------------------------#
def get_config_param(json_data, key, mandatory=True, default_val=""):
    value = json_data.get(key)

    if value is None or len(value) == 0: 
        if mandatory:
            raise Exception(f'Config key not found: "{key}"')
        else:
            value = default_val
    print(f'### {key}="{value}"')
    return value


def read_ssh_config():
    global SERVER_ADDR, SERVER_PORT, SERVER_USERNAME, SERVER_PASSWORD

    print(f'Reading "{SSH_CONFIG_FILE}"...')

    if not os.path.isfile(SSH_CONFIG_FILE):
        raise Exception(f'config file {SSH_CONFIG_FILE} not found')

    with open(SSH_CONFIG_FILE, 'r') as f:
        data = json.load(f)

        server_json = data.get('servers')[0] # default use the first server

        if server_json is None: raise Exception(f'Server config data not found')

        print('Reading server info:')
        SERVER_ADDR = get_config_param(server_json, 'host')
        SERVER_PORT = get_config_param(server_json, 'port')
        SERVER_USERNAME = get_config_param(server_json, 'username')
        SERVER_PASSWORD = get_config_param(server_json, 'password')
        if SERVER_PORT == "": SERVER_PORT = "22"


# -------------------------------------------------- BUILD SERVER ------------------------------------------------------#
def getAppName():
    app_name = LOCAL_SOURCE_PATH.split('/')
    app_name = app_name[len(app_name)-1]
    return app_name


def connectToServer():
    print("Connecting to build server at IP " + SERVER_ADDR + "...")
    global server_ssh
    server_ssh = paramiko.SSHClient()
    server_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if SERVER_PORT != "":
        server_ssh.connect(hostname=SERVER_ADDR, port=SERVER_PORT, username=SERVER_USERNAME, password=SERVER_PASSWORD, timeout=SSH_SERVER_CONNECT_TIMEOUT)
    else:
        server_ssh.connect(hostname=SERVER_ADDR, username=SERVER_USERNAME, password=SERVER_PASSWORD, timeout=SSH_SERVER_CONNECT_TIMEOUT)
    print("Server connected!")

def progress(filename, size, sent):
    sys.stdout.write("%s's progress: %.2f%%   \r" % (filename, float(sent)/float(size)*100) )
    global isScpPutCompleted
    isScpPutCompleted = False
    if int(sent)/int(size)*100 == 100:
        isScpPutCompleted = True

def copySourceToServer():
    print("Copying source to server ...")
    # Clean folder first:
    server_ssh.exec_command('rm -R ' + SERVER_SOURCE_PATH)

    # Zip local path:
    global app_name
    app_name = getAppName()
    os.chdir(LOCAL_SOURCE_PATH.replace('/'+app_name, ''))
    if os.path.exists(LOCAL_SOURCE_PATH + '.zip'):
        print(LOCAL_SOURCE_PATH + '.zip' + " is existed, removing ...")
        os.remove(LOCAL_SOURCE_PATH + '.zip')
    shutil.make_archive(app_name, 'zip', LOCAL_SOURCE_PATH)

    # Push to server:
    server_ssh.exec_command('mkdir ' + SERVER_SOURCE_PATH)
    with SCPClient(server_ssh.get_transport(), progress=progress) as scp:
        scp.put(f''+LOCAL_SOURCE_PATH+'.zip', SERVER_SOURCE_PATH)
    while isScpPutCompleted == False: {}

    # Unzip source
    cmd =           'cd '+ SERVER_SOURCE_PATH # cd to directory
    cmd = cmd + ' && unzip ' + app_name+'.zip' # unzip source
    ssh_stdin, ssh_stdout, ssh_stderr = server_ssh.exec_command(cmd)
    print(ssh_stdout.readline())

    cmd = ''
    cmd = 'cd ' + SERVER_SOURCE_PATH
    cmd = cmd + ' && rm -R ' + app_name+'.zip'
    ssh_stdin, ssh_stdout, ssh_stderr = server_ssh.exec_command(cmd)
    print(ssh_stdout.readline())
    print("Completed pushed to server and unziped")



def disconnectToServer():
    server_ssh.close()


######### MAIN #########
if __name__ == '__main__':
    need_restore = False
    os.system("clear")

    read_ssh_config()
    connectToServer()
    copySourceToServer()
    disconnectToServer()
