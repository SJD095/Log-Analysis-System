#!/usr/bin/python
# -*- coding: UTF-8 -*-

#SDCS of SYSU 孙中阳
#szy@sunzhongyang.com 13717558798

import json

import pymongo

import os.path
import os

import time
import datetime

import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web

import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.mime.multipart import MIMEMultipart

import matplotlib
matplotlib.use('Agg')

from matplotlib.pyplot import plot,savefig
import matplotlib

from xml.dom.minidom import parse
import xml.dom.minidom

import zipfile
import zlib

import shutil

#设置服务端端口号（default=端口号）
from tornado.options import define, options
define("port", default=12333, help="run on the given port", type=int)

#客户端日志的详细信息
information_about_log = {}
#默认时间格式
ISOTIMEFORMAT='%Y-%m-%d %X'

#建立和本地MongoDB数据库的连接，默认端口号为27017
connection = pymongo.MongoClient('localhost', 27017)
#和logs中的表单log、statistic建立连接，其中log用于存储和日志有关的详细信息，statistic存储统计信息
db = connection.logs
log = db.log
statistic = db.statistics

#显示在网页上的出现了fatal错误的日志的详细内容
log_web = ''

#根据开始日期，结束日志绘制名为diagram_name的统计图表
def Draw(from_date, to_date, diagram_name):
    #标记该日是否有错误
    has_append = False
    #日期计数
    count = 1
    #绘制折线图时x坐标对应的list
    x_coordinate = []
    #统计图表对应的y坐标的三个list，分别标记了
    warning_coordinate = []
    error_coordinate = []
    fatal_coordinate = []
    #将字符串格式的日志转化为时间戳
    toArray = time.strptime(to_date, "%Y-%m-%d")
    toArray_timeStamp = int(time.mktime(toArray)) + 1
    toArray_datetime = datetime.datetime.utcfromtimestamp(toArray_timeStamp)

    #添加第一个x轴
    x_coordinate.append(count)

    #获取数据库statistic中截止日期对应的有关错误的统计信息
    for re in statistic.find({'date' : to_date}):
        #该日期已添加
        has_append = True
        #添加warning数量，fatal数量和error数量
        warning_coordinate.append(re['warnings'])
        fatal_coordinate.append(re['fatals'])
        error_coordinate.append(re['errors'])

    #如果该日期没有添加（数据库里找不到，说明该日期没有出现错误）
    if not has_append:
        #全部补零
        warning_coordinate.append(0)
        error_coordinate.append(0)
        fatal_coordinate.append(0)

    #暂存当前日期，用于和截起始日期比较
    oneday_ago = toArray_datetime

    #未到达起始日期时
    while oneday_ago.strftime("%Y-%m-%d") != from_date:
        #日期计数加一
        count += 1
        has_append = False
        #持续构造x轴
        x_coordinate.append(count)
        #获取数据库statistic中该日期对应的有关错误的统计信息
        for re in statistic.find({'date' : oneday_ago.strftime("%Y-%m-%d")}):
            #该日期已添加
            has_append = True
            #添加warning数量，fatal数量和error数量
            warning_coordinate.append(re['warnings'])
            fatal_coordinate.append(re['fatals'])
            error_coordinate.append(re['errors'])

        #如果该日期没有添加（数据库里找不到，说明该日期没有出现错误）
        if not has_append:
            #全部补零
            warning_coordinate.append(0)
            error_coordinate.append(0)
            fatal_coordinate.append(0)
        #将日期更新至前一日
        oneday_ago = oneday_ago - datetime.timedelta(days = 1)

    #向图表中添加起始日期的有关信息
    has_append = False

    #同上
    for re in statistic.find({'date' : from_date}):
        has_append = True
        warning_coordinate.append(re['warnings'])
        fatal_coordinate.append(re['fatals'])
        error_coordinate.append(re['errors'])
    if not has_append:
        warning_coordinate.append(0)
        error_coordinate.append(0)
        fatal_coordinate.append(0)

    #由于添加顺序是由截止日期到起始日期，所以需要反转
    fatal_coordinate.reverse()
    warning_coordinate.reverse()
    error_coordinate.reverse()

    count += 1
    x_coordinate.append(count)

    #绘图
    plot(x_coordinate, warning_coordinate,'-+g', x_coordinate, error_coordinate,'-+y', x_coordinate, fatal_coordinate,'-+r')

    #将图片保存至程序目录下的static目录中
    savefig(os.getcwd() + '/static/' + diagram_name)
    #关闭所有绘图信息，避免影响下一次绘图
    matplotlib.pyplot.close('all')

#绘制并保存默认图表
def Draw_Line_Diagram():
    #数据库连接有时会断掉，所以需要重新建立连接
    connection = pymongo.MongoClient('localhost', 27017)
    db = connection.logs
    statistic = db.statistics
    #默认一周的时间长度和一个月的时间长度
    weekdays = 7
    monthdays = 30
    #计算绘图的起始日期并转化为指定格式
    from_date_week = (datetime.datetime.now() - datetime.timedelta(days = weekdays)).strftime("%Y-%m-%d")
    from_date_month = (datetime.datetime.now() - datetime.timedelta(days = monthdays)).strftime("%Y-%m-%d")
    #计算截止日期并转化为指定格式
    now = int(time.time())
    timeArray = time.localtime(now)
    to_date = time.strftime("%Y-%m-%d", timeArray)
    #绘制周视图和月视图
    Draw(from_date_month, to_date, 'month_diagram')
    Draw(from_date_week, to_date, 'week_diagram')

#默认配置选项，如果程序启动时没有读取到配置文件，则创建一个配置文件并向文件中添加如下内容
#其中包括客户端默认名称nickname，默认发件列表mail，默认日志路径logpath,默认日志名guize logname
default_configure_content = '<configure>\n<default>\n\t<nickname>default_name</nickname>\n\t<mail>szy@sunzhongyang.com</mail>\n\t<logpath>/home/szy</logpath>\n\t<logname>[a-z]+[_][0-9]+(.log.)[0-9]{4}[-][0-9]{2}[-][0-9]{2}</logname>\n</default>\n</configure>'

#统计数据
warning_count = 0
error_count = 0
fatal_count = 0

#起始日期和截止日期
from_date = ''
to_date = ''

#计算并向statistic表加入统计数据
def Statictics_Insert(errors, fatals, warnings, create_time):
    #获取当前日期并转换为指定的字符串格式，statistic表以日期字符串为key
    timeArray = time.localtime(create_time)
    key = time.strftime("%Y-%m-%d", timeArray)
    #查找当前日期是否已被加入至数据库中
    re = statistic.find_one({'date' : key})
    #如果已经被加入到数据库中，则更新数据库
    if re:
        if warnings > 0:
            re['warnings'] += warnings
        if errors > 0:
            re['errors'] += errors
        if fatals > 0:
            re['fatals'] += fatals
        statistic.save(re)

    #如果没有加入进去，则创建新的条目
    else:
        new = {}
        new['date'] = key
        new['warnings'] = warnings
        new['errors'] = errors
        new['fatals'] = fatals
        statistic.insert(new)

#计算统计数据
def Calculate_Statistics():
    #声明需要用到的全局变量
    global from_date, to_date, warning_count, error_count, fatal_count, log_web
    log_web = ''
    #将出现fatal的日志压缩至一压缩文件中
    fatal_log = zipfile.ZipFile('fatal_log.zip', 'a', zipfile.ZIP_DEFLATED, True)
    #warning,error,fatal错误的计数
    warning_count = 0
    error_count = 0
    fatal_count = 0
    #获取两个日期的时间戳
    fromArray = time.strptime(from_date, "%Y-%m-%d")
    from_timestamp = float(time.mktime(fromArray))
    toArray = time.strptime(to_date, "%Y-%m-%d")
    to_timestamp = float(time.mktime(toArray))
    #根据时间戳从log表查找指定时间范围内创建的日志
    for re in log.find({'create_time' : {'$gte':from_timestamp, '$lt':to_timestamp}}):
        #将日志创建时间的时间戳转换为创建日期的字符串，存入数据库中使用UTF-8格式，从字典中取出时也需要使用UTF-8
        timeArray = time.localtime(re[u'create_time'])
        date = time.strftime("%Y-%m-%d", timeArray)
        #更新错误计数
        warning_count += re[u'warning']
        fatal_count += re[u'fatal']
        error_count += re[u'error']
        #对不为空（也就是出现了fatal错误的日志），将其信息整合并加入到网页显示中
        if re[u'log_content'] != '':
            #构造具体内容，包括日志创建时间，标题，客户端名称和具体日志内容
            log_web = log_web + date + '</br>' + re[u'server_name'] + ': ' + re[u'file_name'] + '</br>' + re[u'log_content'] + '</br>-----------------------------</br></br>'
            #将对应内容写入至压缩文件中
            fatal_log.write(os.getcwd() + '/logs/' + re['file_name'])
    #将压缩文件移动至static目录，方便tornado读取
    shutil.move(os.getcwd() + '/' + 'fatal_log.zip', os.getcwd() + '/static/fatal_log.zip')

#发送告警邮件
def Send_Mail():
    global information_about_log
    mail_host="smtp.***.***"  #设置服务器
    mail_user="***"    #用户名
    mail_pass="***"   #口令

    sender = 'szy@sunzhongyang.com'
    receivers = information_about_log[u'mail_list']
    #接收邮件，可设置为你的QQ邮箱或者其他邮箱
    mail_content = 'a FATAL error occured in ' + information_about_log[u'server_name'] + '\n' + time.strftime(ISOTIMEFORMAT, time.localtime())
    #设置SMTP协议具体信息
    message = MIMEMultipart()
    #邮件内容
    message.attach(MIMEText(mail_content, 'plain', 'utf-8'))
    #附件内容
    att1 = MIMEText(information_about_log[u'log_content'] + '\n', 'base64', 'utf-8')
    att1["Content-Type"] = 'application/octet-stream'
    att1["Content-Disposition"] = 'attachment; filename="' + information_about_log[u'file_name'] + '"'
    message.attach(att1)
    #发件人和收件人名称
    message['From'] = Header("log_analysis_server", 'utf-8')
    message['To'] =  Header("server_administrator", 'utf-8')
    #邮件标题
    subject = 'A FATAL error occured'
    message['Subject'] = Header(subject, 'utf-8')


    try:
        smtpObj = smtplib.SMTP()
        smtpObj.connect(mail_host, 25)    # 25 为 SMTP 端口号
        smtpObj.login(mail_user,mail_pass)
        smtpObj.sendmail(sender, receivers, message.as_string())
        print "邮件发送成功"
    except smtplib.SMTPException:
        print "Error: 无法发送邮件"

#决定是否要发送报警邮件
def Mail_Warning(mail_c):
    #检查邮件，并记录各类型错误的数量
    errors = 0
    warnings = 0
    fatals = 0
    #邮件内容
    content = mail_c.split('\n')
    #决定是否发送报警邮件
    mail_content = False
    #检查邮件内容中的每一行，如果有错误信息则记录并进行进一步的操作
    for line in content:
        tuples = line.split(' ')
        if len(tuples) > 2:
            if tuples[2] == 'FATAL':
                fatals += 1
                #出现FATAL错误，需要
                mail_content = True
            elif tuples[2] == 'ERROR':
                errors += 1
            elif tuples[2] == 'WARNING':
                warnings += 1
        information_about_log[u'error'] = errors
        information_about_log[u'fatal'] = fatals
        information_about_log[u'warning'] = warnings
    if errors > 0 or fatals > 0 or warnings > 0:
        #向statisitic中插入数据
        Statictics_Insert(errors, fatals, warnings, information_about_log[u'create_time'])
    #将日志内容转储到log目录下
    log_write = open('logs/' + information_about_log['file_name'], 'w')
    log_write.write(information_about_log['log_content'])
    log_write.close()
    if fatals == 0:
        information_about_log['log_content'] = ''
    #向log中插入该日志的详细信息
    log.insert(information_about_log)
    if mail_content == True:
        Send_Mail()

#如果没有配置文件，则创建默认配置文件
def Determine_Configure_File():
    if not os.path.exists(os.getcwd() + '/configure.xml'):
        configure_xml = open('configure.xml', 'w')
        #写入default_configure_content中的内容
        configure_xml.write(default_configure_content)

#从配置文件中读取指定客户端配置
def Get_Spec_Configure(server_id):
    DOMTree = xml.dom.minidom.parse("configure.xml")
    configure = DOMTree.documentElement

    #获取所有client标签下的内容
    clients = configure.getElementsByTagName("client")
    for client in clients:
        #确定传入的客户端ID是否存在
        if client.hasAttribute("id"):
            #如果存在，则将配置打包返回
            if client.getAttribute("id") == server_id:
                result = {}
                result['nickname'] = client.getElementsByTagName('nickname')[0].childNodes[0].data
                result['mail'] = client.getElementsByTagName('mail')[0].childNodes[0].data
                result['logpath'] = client.getElementsByTagName('logpath')[0].childNodes[0].data
                result['logname'] = client.getElementsByTagName('logname')[0].childNodes[0].data
                return json.dumps(result)

    #如果没有客户端ID，说明客户端是新加入连接的，传回默认设置并为该客户端创建默认配置
    default = configure.getElementsByTagName("default")[0]

    #为该客户端创建默认配置，先移除最后一行
    f = open('configure.xml', 'r')
    lines = f.readlines()
    curr = lines[:-1]
    f.close()

    #再写入
    f = open('configure.xml','w')
    for line in curr:
        f.write(line)

    new_line = '<client id="' + server_id +'">\n\t<nickname>'+ default.getElementsByTagName('nickname')[0].childNodes[0].data+ '</nickname>\n\t<mail>'+ default.getElementsByTagName('mail')[0].childNodes[0].data +'</mail>\n\t<logpath>' + default.getElementsByTagName('logpath')[0].childNodes[0].data + '</logpath>\n\t<logname>' + default.getElementsByTagName('logname')[0].childNodes[0].data + '</logname>\n</client>\n' + '</configure>\n'
    f.write(new_line)

    #传向客户端的内容
    result = {}
    result['nickname'] = default.getElementsByTagName('nickname')[0].childNodes[0].data
    result['mail'] = default.getElementsByTagName('mail')[0].childNodes[0].data
    result['logpath'] = default.getElementsByTagName('logpath')[0].childNodes[0].data
    result['logname'] = default.getElementsByTagName('logname')[0].childNodes[0].data
    return json.dumps(result)

#检查传入字典中未被包括在数据库log中的MD5码，并返回
def Check_Md5(md5s):
    result = []
    print md5s
    for md5 in md5s:
        if not log.find_one({"md5" : md5}):
            result.append(md5)
    print result
    return result

Determine_Configure_File()

#对客户端发来的邮件进行检查
class checkHandler(tornado.web.RequestHandler):
    #获取POST报文的body部分
    def post(self):
        global information_about_log
        result = ""
        text = self.request.body
        information_about_log = json.loads(text)
        #如果是数据库中没有的新邮件，则进行进一步处理
        if not log.find_one({"md5" : information_about_log[u'md5']}):
            Mail_Warning(information_about_log[u'log_content'])

#用于显示具体统计结果
class analysisHandler(tornado.web.RequestHandler):
    def get(self):
        Draw_Line_Diagram()
        self.render('new.html')

    #根据获取的起止日期生成统计信息和图表，并显示于网页
    def post(self):
        global from_date, to_date, warning_count, error_count, fatal_count, log_web
        from_date = self.get_argument('from')
        to_date = self.get_argument('to')
        Calculate_Statistics()
        #绘图部分
        Draw(from_date, to_date, 'search_diagram.png')
        self.render('poem.html', warning=warning_count, error=error_count, fatal= fatal_count, log=log_web)

#对客户端返回该客户端的配置
class getconfigureHandler(tornado.web.RequestHandler):
    def post(self):
        return_body = Get_Spec_Configure(self.request.body)
        self.write(return_body)

#负责MD5的检查与返回
class md5Handler(tornado.web.RequestHandler):
    def post(self):
        text = self.request.body
        md5s = json.loads(text)
        return_body = json.dumps(Check_Md5(md5s))
        self.write(return_body)

if __name__ == "__main__":
    tornado.options.parse_command_line()
    app = tornado.web.Application(
    handlers=[
            (r"/log_to_db", checkHandler), (r"/check", analysisHandler),(r"/configure", getconfigureHandler),(r"/md5", md5Handler)
        ],
    template_path=os.path.join(os.path.dirname(__file__), "templates"),
    static_path=os.path.join(os.path.dirname(__file__), "static")

    )

    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
