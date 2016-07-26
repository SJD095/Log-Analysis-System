#!/usr/bin/python
# -*- coding: utf-8 -*-

#SDCS of SYSU 孙中阳
#szy@sunzhongyang.com 13717558798

import sys
import os
import time
import socket
import httplib
import urllib
import json
import re
import hashlib
import types
import platform

#服务端hostname或者IP地址
hostname = 'sunzhongyang.com'
#服务端端口号
port = 12333
#获取客户端程序所在绝对路径
current_path = os.getcwd()

#默认设置
#默认客户端名称
server_name = "default_server_name"
#日志绝对路径
log_path = current_path
#客户端对应的发件人列表
mail_list = []
#日志文件命名规则（正则表达式）
log_name_regex = '[a-z]+[_][0-9]+(.log.)[0-9]{4}[-][0-9]{2}[-][0-9]{2}'

#从服务端读取本客户端的配置
def Read_Configure_From_Server():
	global mail_list, log_name_regex, server_name, log_path
	#从服务器获取JSON格式的配置文件并读取为字典
	configure_fom_server = Send_To_Server(platform.node(), 'configure')
	configure_dict = json.loads(configure_fom_server)
	#获取服务端配置文件标志的配置信息
	#JSON默认采用UTF-8传输，需要以UTF-8格式从字典中读取数据
	server_name = configure_dict[u'nickname']
	log_path = configure_dict[u'logpath']
	mail_list = configure_dict[u'mail'].split(':')
	log_name_regex = configure_dict[u'logname']


#计算日志目录下所有文件的MD5信息，并发送至服务器核验
def Calculate_Md5(input_string):
	#首先确认输入类型是字符串
	if type(input_string) == types.StringType:
		#如果能够成功计算则返回计算的MD5，否则返回代码1
		m = hashlib.md5()
		m.update(input_string)
		return m.hexdigest()
	else:
		return '1'

#根据spec内容将body发送至指定的URL
def Send_To_Server(body, spec):
	#使用httplib类和服务器建立HTTP连接
	httpconn = httplib.HTTPConnection(hostname + ':' + str(port))
	#根据已知信息确定目标URL
	requrl = 'http://'+ hostname + ':' + str(port) + '/' + spec
	#HTTP header为空，并发起POST连接
	headers = {}
	httpconn.request(method='POST', url=requrl,body=body, headers=headers)
	#返回服务端的报文body
	return httpconn.getresponse().read()

#构造发送给服务器的报文的body，包括日志文件有关信息
def Make_Body(file_name, log_content, md5, create_time):
	file_content = {}
	#日志名
	file_content['file_name'] = file_name
	#日志详细内容
	file_content['log_content'] = log_content
	#客户端名称
	file_content['server_name'] = server_name
	#告警邮件收件人列表
	file_content['mail_list'] = mail_list
	#日志建立时间
	file_content['create_time'] = create_time
	#日志MD5
	file_content['md5'] = md5
	#将字典转化为JSON格式
	encodedjson = json.dumps(file_content)
	return encodedjson

#客户端程序首先从服务端读取配置信息
Read_Configure_From_Server()

#从log地址获取该地址下的文件名列表
filelist = os.listdir(log_path)
#建立一个字典用于记录每个计算出的MD5对应的原文件的文件名
md5_dict = {}
#储存所有计算出的MD5
md5_list = []
#对于文件列表中的所有文件，测试其是否是合法日志，如果是合法日志则计算MD5并发送至服务端
for file_name in filelist:
	#获取文件的绝对路径
	full_file_position = log_path + '/' + file_name
	#首先测试该文件是否是文件夹，如果不是文件夹则进一步检查其文件名是否符合日志名的正则表达式
	if os.path.isfile(full_file_position) and re.match(log_name_regex, file_name):
		#获取文件内容并根据文件名和文件内容计算MD5
		log_content = open(full_file_position, 'r').read()
		md5 = Calculate_Md5(str(file_name+log_content))
		#将获取的MD5记录至字典和列表中
		md5_dict[md5] = file_name
		md5_list.append(md5)
#将MD5列表转换为JSON格式并发送至服务器，获取返回报文
response = Send_To_Server(json.dumps(md5_list), 'md5')
#返回报文是服务端查询数据库后发现之前没有收到过该文件的文件的MD5的列表
md5_list = json.loads(response)

#对每一个服务端返回的MD5对应的日志文件，发送包括日志详细内容等的具体信息至服务端
for md5_return in md5_list:
	full_file_position = log_path + '/' + md5_dict[md5_return]
	#获取日志建立时间
	create_time = os.path.getctime(full_file_position)
	#获取日志具体内容
	log_content = open(full_file_position, 'r').read()
	#构造发送报文的body部分并发送至服务器
	body = Make_Body(md5_dict[md5_return], log_content, md5_return, create_time)
	Send_To_Server(body, 'log_to_db')
print "execute successful"
