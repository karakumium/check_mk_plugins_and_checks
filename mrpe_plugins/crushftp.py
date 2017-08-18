#!/usr/bin/python3
'''
Return codes:
0 -- all OK with CrushFTP programm,
1 -- warning (if crushftp process alive time less than 300 sec),
2 -- critical (web-interface is not available, port is not listening, authorization is not work or crushftp process is dead)
return True in function -- if something bad '''

import requests
import psutil
import time
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--ip', type=str, required=True, default=300, help='CrushFTP ip address')
parser.add_argument('-P', '--ports', type=str, required=True, help='ports which should be listened by application')
parser.add_argument('-t', '--timeout', type=int, required=False, default=30, help='timeout for http request to web-interface (default=30)')
parser.add_argument('-u', '--username', type=str, required=True, help='crushftp account for monitoring ')
parser.add_argument('-pass', '--password', type=str, required=True, help='password crushftp account for monitoring')
parser.add_argument('-c', '--installed_dir', type=str, required=True, help='CrushFTP installed directory')
parser.add_argument('-a', '--min_alive', type=int, required=False, default=300, help='crushftp process minimum alive time in seconds (default=300)')
parser.add_argument('-hp', '--http_port', type=int, required=True, help='crushftp http port')
args = parser.parse_args()

message = ''
total_message=[]
alarm_level=0
total_alarm_level=0

def check_proc():
    '''search crushFTP process, return pid, listened ports by Crushftp, Crushftp timeout.
       Emergency exit if process not found
       alarm level: critical'''
    proc_tree = psutil.process_iter()
    for i in proc_tree:
        if i.name() == 'java' and i.ppid() == 1 and i.cwd() == args.installed_dir:
            pid = i.pid
            ports = i.connections(kind='tcp')
            proc_alive_time = time.time() - i.create_time()
            return pid, ports, proc_alive_time
    print("Critical error: crushftp is dead!")
    exit(2)


def check_uptime(proc_uptime):
    '''check CrushFTP uptime. return Warning if uptime is too low
    alarm level: warning'''
    message = ''
    if proc_uptime < args.min_alive:
        message = "process uptime is too low... Only " + str(round(proc_uptime)) + ' sec'
        return message, 1
    else:
        return message, 0


def check_authorization():
    '''Try to authorized on crushftp and show files (check authorization + web-interface)
    alarm level: critical -- web-interface is not available, warning level -- incorrect login or can not get list of files'''
    message=''
    #warning_or_crit=0 if a all OK, =1 if warning and =2 if crit
    critical=False; warning=False; warning_or_crit=0
    params_for_get_cookies = {'username': args.username,
                              'password': args.password,
                              'command': 'login',
                              'skip_login': 'true',
                              'encoded': 'true'}
    try:
        crash_request_get_cookie = requests.post("http://" + str(args.ip) + ":" + str(args.http_port), data=params_for_get_cookies)
        if crash_request_get_cookie.status_code != requests.codes.ok:
            message += "can not get cookies of crushftp. Http status code:" + str(crash_request_get_cookie.status_code)
            return message, 2
        try:
            params_for_check_file = {'command': 'stat',
                                     'path': '/hello',
                                     'format': 'json',
                                     'c2f': crash_request_get_cookie.cookies['CrushAuth'][-4:]}
        except KeyError:
            message += "can not get cookies. Http status code: " + str(crash_request_get_cookie.status_code)
            return message, 1
        crash_request_get_info = requests.post("http://" + str(args.ip) + ":" + str(args.http_port), data=params_for_check_file, cookies=crash_request_get_cookie.cookies)
        if crash_request_get_info.text.find("04c9433b") == -1:
            message += "can not  find file with hash 04c9433b on crushftp server. Http status code: " + str(crash_request_get_info.status_code)
            return  message, 1
    except:
        message += "can not get request to CrushFtp. Most likely that connection troubles. "
        return message, 2
    return message, 0

def check_ports(ports):
    '''check all ports which shoul be listened by application (optino -p)
    alarm level: critical'''
    message=''
    listened_ports_list=[]
    for i in ports:
        listened_ports_list.append(str(i[3][1]))
    listened_ports_set=set(listened_ports_list)
    targer_ports_set=set(args.ports.split(","))
    if len(listened_ports_set.intersection(targer_ports_set))!=len(targer_ports_set):
        message="port(s) are not listened: " + str(','.join(targer_ports_set-listened_ports_set))
        return message, 2
    else:
        return message, 0

pid, ports, proc_alive_time = check_proc()

message, alarm_level = check_uptime(proc_alive_time)
total_alarm_level += alarm_level
if message:
    total_message.append(message)

message, alarm_level = check_ports(ports)
total_alarm_level += alarm_level
if message:
    total_message.append(message)

if total_alarm_level < 2:
    message, alarm_level = check_authorization()
    total_alarm_level += alarm_level
    if message:
        total_message.append(message)

if total_alarm_level == 0:
    print("All OK with Crushftp. pid: {pid}, uptime: {uptime} hours".format(pid=pid, uptime=round(proc_alive_time/60/60,1)))
    exit(0)
else:
    if total_alarm_level>2:
        total_alarm_level=2
    message_for_print= ('Warning: ', 'Critical error: ')
    print(message_for_print[total_alarm_level-1],'; '.join(total_message))
    exit(total_alarm_level)
