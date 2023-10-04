import os, sys
import shutil
import json

import paramiko
from paramiko import SSHClient
from scp import SCPClient

# ========== GET FROM ssh_config.json:
SSH_CONFIG_FILE = "ssh_config.json" # editable
APP_CONFIG_FILE = ""

SERVER_ADDR  = ""
SERVER_PORT  = ""
SERVER_USERNAME = ""
SERVER_PASSWORD = ""

TARGET_ADDR = ""
TARGET_PORT = ""
TARGET_USERNAME = ""
TARGET_PASSWORD = ""

# ========== GET FROM templateapp.json
SERVER_SOURCE_PATH = ""
SERVER_OUTPUT_PATH = ""
LOCAL_SOURCE_PATH  = ""
LOCAL_OUTPUT_PATH  = ""

TARGET_BIN_PATH = ""
TARGET_LIB_PATH = ""
TARGET_TEST_PATH = ""

APP_FILE = ""
TEST_FILE = ""
LIB_FILES = []

# ========== Build config:
SSH_SERVER_CONNECT_TIMEOUT = 5 #5s
SSH_SERVER_EXEC_TIMEOUT    = 5 #5s

BUILD_CMD = "make all" # Ex: make all


# Variables:
server_ssh = None
app_name = None
g_build_result = False

target_ssh = None
isScpPutCompleted = False


# -------------------------------------------------- GET CONFIGURATION -------------------------------------------------#
def getConfigParam(json_data, key, mandatory=True, default_val=""):
    value = json_data.get(key)

    if value is None or len(value) == 0: 
        if mandatory:
            raise Exception(f'Config key not found: "{key}"')
        else:
            value = default_val
    print(f'### {key}="{value}"')
    return value


def readSSHConfig():
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
        SERVER_ADDR = getConfigParam(server_json, 'host')
        SERVER_PORT = getConfigParam(server_json, 'port')
        SERVER_USERNAME = getConfigParam(server_json, 'username')
        SERVER_PASSWORD = getConfigParam(server_json, 'password')
        if SERVER_PORT == "": SERVER_PORT = "22"

        print('\nReading target info:')
        TARGET_ADDR = getConfigParam(target_json, 'host')
        TARGET_PORT = getConfigParam(target_json, 'port')
        TARGET_USERNAME = getConfigParam(target_json, 'username')
        TARGET_PASSWORD = getConfigParam(target_json, 'password')
        if TARGET_PORT == "": TARGET_PORT = "22"


def readAppConfig():
    global SERVER_SOURCE_PATH, SERVER_OUTPUT_PATH
    global LOCAL_SOURCE_PATH, LOCAL_OUTPUT_PATH
    global TARGET_BIN_PATH, TARGET_LIB_PATH, TARGET_TEST_PATH
    global APP_FILE, TEST_FILE, LIB_FILES
    global PROCESS_NAME

    app_config_file = f'{APP_CONFIG_FILE}.json'
    print(f'You\'re building "{APP_CONFIG_FILE}", reading "{APP_CONFIG_FILE}"...')

    if not os.path.isfile(APP_CONFIG_FILE):
        raise Exception(f'file {APP_CONFIG_FILE} not found')

    with open(APP_CONFIG_FILE, 'r') as f:
        data = json.load(f)

        SERVER_SOURCE_PATH = getConfigParam(data, 'SERVER_SOURCE_PATH')
        SERVER_OUTPUT_PATH = getConfigParam(data, 'SERVER_OUTPUT_PATH')
        LOCAL_SOURCE_PATH = getConfigParam(data, 'LOCAL_SOURCE_PATH')
        LOCAL_OUTPUT_PATH = getConfigParam(data, 'LOCAL_OUTPUT_PATH')
        TARGET_BIN_PATH = getConfigParam(data, 'TARGET_BIN_PATH')
        TARGET_LIB_PATH = getConfigParam(data, 'TARGET_LIB_PATH')
        TARGET_TEST_PATH = getConfigParam(data, 'TARGET_TEST_PATH')

        APP_FILE = getConfigParam(data, 'APP_FILE')
        TEST_FILE = getConfigParam(data, 'TEST_FILE')
        LIB_FILES = getConfigParam(data, 'LIB_FILES')
        PROCESS_NAME = getConfigParam(data, 'PROCESS_NAME')


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
    cmd = cmd + ' && rm -R ' + app_name+'.zip' # then delete zip
    ssh_stdin, ssh_stdout, ssh_stderr = server_ssh.exec_command(cmd)
    print(ssh_stdout.readline())
    print("Completed pushed to server and unziped")


def build():
    print("Building ...\n")
    global g_build_result
    cmd = 'cd ' + SERVER_SOURCE_PATH
    cmd = cmd + ' && ' + BUILD_CMD # For Beagebone/Pi Target
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
    target_ssh.exec_command('rm -R ' + TARGET_BIN_PATH + '/' + APP_FILE)

    # Push to Target Device:
    with SCPClient(target_ssh.get_transport()) as scp:
        scp.put(f'' + LOCAL_OUTPUT_PATH + '/'+app_name + '/'+ APP_FILE, TARGET_BIN_PATH)

    # Set chmod:
    print("Set chmod ...")
    target_ssh.exec_command('cd ' + TARGET_BIN_PATH + ' && chmod 777 ' + APP_FILE)
    print("Done.")


def disconnectToTarget():
    target_ssh.close()


######### MAIN #########
if __name__ == '__main__':
    need_restore = False
    os.system("clear")

    app = [i for i in sys.argv if not i.startswith("-")]
    APP_CONFIG_FILE = app[1]

    readSSHConfig()
    readAppConfig()
    connectToServer()
    copySourceToServer()
    build()
    getBuildOutput()
    disconnectToServer()

    need_push = input('Push to Target [y/n]? ')
    need_push.lower()
    if need_push == 'y' or need_push == 'yes':
        connectToTarget()
        pushToTarget()
        disconnectToTarget()
    print("Job done!")
