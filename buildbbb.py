import os, sys
import shutil
import json

import paramiko
from paramiko import SSHClient
from scp import SCPClient


SSH_CONFIG_FILE = "ssh_config.json" # editable
APP_CONFIG_FILE = ""

SERVER_ADDR  = ""
SERVER_PORT  = ""
SERVER_USERNAME = ""
SERVER_PASSWORD = ""

SERVER_SOURCE_PATH = ""
SERVER_OUTPUT_PATH = ""
LOCAL_SOURCE_PATH  = ""
LOCAL_OUTPUT_PATH  = "/Users/admin/Desktop/repo_TestApp/Release" # editable

APP_FILE = ""
TEST_FILE = ""
LIB_FILES = []

TARGET_ADDR = ""
TARGET_PORT = ""
TARGET_USERNAME = ""
TARGET_PASSWORD = ""

TARGET_APP_FILE_PATH = "/home/pi/TestApp_Prj/opt/bin" # editable
TARGET_TEST_FILE_PATH = "/home/pi/TestApp_Prj/opt/test" # editable
TARGET_LIB_FILES_PATH = "/home/pi/TestApp_Prj/opt/lib" # editable

# TARGET_APP_FILE_PATH  = "/home/khanhtoandn99/TestApp_Simulation/opt/bin" # editable
# TARGET_TEST_FILE_PATH = "/home/khanhtoandn99/TestApp_Simulation/opt/test" # editable
# TARGET_LIB_FILES_PATH = "/home/khanhtoandn99/TestApp_Simulation/opt/lib" # editable

SSH_SERVER_CONNECT_TIMEOUT = 5 #5s
SSH_SERVER_EXEC_TIMEOUT    = 5 #5s

# Variables:
server_ssh = None
app_name = None
g_build_result = False

target_ssh = None


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
    global TARGET_ADDR, TARGET_PORT, TARGET_USERNAME, TARGET_PASSWORD

    print(f'Reading "{SSH_CONFIG_FILE}"...')

    if not os.path.isfile(SSH_CONFIG_FILE):
        raise Exception(f'config file {SSH_CONFIG_FILE} not found')

    with open(SSH_CONFIG_FILE, 'r') as f:
        data = json.load(f)

        server_json = data.get('servers')[0] # default use the first server
        target_json = data.get('targets')[0] # default use the first target

        if server_json is None: raise Exception(f'Server config data not found')
        if target_json is None: raise Exception(f'Target config data not found')

        print('Reading server info:')
        SERVER_ADDR = get_config_param(server_json, 'host')
        SERVER_PORT = get_config_param(server_json, 'port')
        SERVER_USERNAME = get_config_param(server_json, 'username')
        SERVER_PASSWORD = get_config_param(server_json, 'password')
        if SERVER_PORT == "": SERVER_PORT = "22"

        print('\nReading target info:')
        TARGET_ADDR = get_config_param(target_json, 'host')
        TARGET_PORT = get_config_param(target_json, 'port')
        TARGET_USERNAME = get_config_param(target_json, 'username')
        TARGET_PASSWORD = get_config_param(target_json, 'password')
        if TARGET_PORT == "": TARGET_PORT = "22"


def read_app_config():
    global SERVER_SOURCE_PATH, SERVER_OUTPUT_PATH
    global LOCAL_SOURCE_PATH
    global APP_FILE, TEST_FILE, LIB_FILES
    global PROCESS_NAME

    app_config_file = f'{APP_CONFIG_FILE}.json'
    print(f'You\'re building "{APP_CONFIG_FILE}", reading "{APP_CONFIG_FILE}"...')

    if not os.path.isfile(APP_CONFIG_FILE):
        raise Exception(f'file {APP_CONFIG_FILE} not found')

    with open(APP_CONFIG_FILE, 'r') as f:
        data = json.load(f)

        SERVER_SOURCE_PATH = get_config_param(data, 'SERVER_SOURCE_PATH')
        SERVER_OUTPUT_PATH = get_config_param(data, 'SERVER_OUTPUT_PATH')
        LOCAL_SOURCE_PATH = get_config_param(data, 'LOCAL_SOURCE_PATH')

        APP_FILE = get_config_param(data, 'APP_FILE')
        TEST_FILE = get_config_param(data, 'TEST_FILE')
        LIB_FILES = get_config_param(data, 'LIB_FILES')
        PROCESS_NAME = get_config_param(data, 'PROCESS_NAME')


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


def copySourceToServer():
    print("Copying source to server ...")
    # Clean folder first:
    server_ssh.exec_command('rm -R ' + SERVER_SOURCE_PATH)

    # Zip local path:
    global app_name
    app_name = getAppName()
    os.chdir(LOCAL_SOURCE_PATH.replace('/'+app_name, ''))
    shutil.make_archive(app_name, 'zip', LOCAL_SOURCE_PATH)

    # Push to server:
    server_ssh.exec_command('mkdir ' + SERVER_SOURCE_PATH)
    with SCPClient(server_ssh.get_transport()) as scp:
        scp.put(f''+LOCAL_SOURCE_PATH+'.zip', SERVER_SOURCE_PATH)

    # Unzip source
    cmd =           'cd '+ SERVER_SOURCE_PATH # cd to directory
    cmd = cmd + ' && unzip ' + app_name+'.zip' # unzip source
    cmd = cmd + ' && rm -R ' + app_name+'.zip' # then delete zip
    ssh_stdin, ssh_stdout, ssh_stderr = server_ssh.exec_command(cmd)
    print(ssh_stdout.readline())


def build():
    print("Building ...\n")
    global g_build_result
    cmd = 'cd ' + SERVER_SOURCE_PATH
    cmd = cmd + ' && arm-linux-gnueabi-g++ -static ' + app_name+'.cpp' + ' -o ' + APP_FILE
    ssh_stdin, ssh_stdout, ssh_stderr = server_ssh.exec_command(cmd)
    for line in iter(ssh_stderr):
        print(line)
        if line.find("error") != -1:
            print("Build failed!")
            return

    g_build_result = True
    cmd = 'mkdir -p ' + SERVER_OUTPUT_PATH
    cmd = cmd + '&& cp ' + SERVER_SOURCE_PATH + '/' + APP_FILE + ' ' + SERVER_OUTPUT_PATH
    server_ssh.exec_command(cmd)
    print("Build success!")


def getBuildOutput():
    if g_build_result == False:
        return
    print("Getting build output to local ...")
    if os.path.isdir(LOCAL_OUTPUT_PATH + '/'+app_name):
        shutil.rmtree(LOCAL_OUTPUT_PATH + '/'+app_name)
    os.mkdir(LOCAL_OUTPUT_PATH + '/'+app_name)
    with SCPClient(server_ssh.get_transport()) as scp:
        scp.get(SERVER_OUTPUT_PATH+'/'+APP_FILE, LOCAL_OUTPUT_PATH + '/'+app_name)
    print("Done")


def disconnectToServer():
    server_ssh.close()


# -------------------------------------------------- TARGET EXECUTE ------------------------------------------------------#
def connectToTarget():
    print("Connecting to Target Device at IP " + TARGET_ADDR + "...")
    global target_ssh
    target_ssh = paramiko.SSHClient()
    target_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if TARGET_PORT != "":
        target_ssh.connect(hostname=TARGET_ADDR, port=TARGET_PORT, username=TARGET_USERNAME, password=TARGET_PASSWORD, timeout=SSH_SERVER_CONNECT_TIMEOUT)
    else:
        target_ssh.connect(hostname=TARGET_ADDR, username=TARGET_USERNAME, password=TARGET_PASSWORD, timeout=SSH_SERVER_CONNECT_TIMEOUT)
    print("Target Device connected!")


def pushToTarget():
    # Clean folder first:
    print("Flashing to Target Device ...")
    target_ssh.exec_command('rm -R ' + TARGET_APP_FILE_PATH + '/'+APP_FILE)

    # Push to Target Device:
    with SCPClient(target_ssh.get_transport()) as scp:
        scp.put(f'' + LOCAL_OUTPUT_PATH + '/'+app_name + '/'+APP_FILE, TARGET_APP_FILE_PATH)
    
    # Set chmod:
    print("Set chmod ...")
    target_ssh.exec_command('cd ' + TARGET_APP_FILE_PATH + ' && chmod 777 ' + APP_FILE)
    print("Done.")


def disconnectToTarget():
    target_ssh.close()


######### MAIN #########
if __name__ == '__main__':
    need_restore = False
    os.system("clear")

    app = [i for i in sys.argv if not i.startswith("-")]
    APP_CONFIG_FILE = app[1]
    
    read_ssh_config()
    read_app_config()
    connectToServer()
    copySourceToServer()
    build()
    getBuildOutput()
    disconnectToServer()

    need_push = input('Push to board? ')
    if need_push == 'YES' or need_push == 'y' or need_push == 'yes':
        connectToTarget()
        pushToTarget()
        disconnectToTarget()
