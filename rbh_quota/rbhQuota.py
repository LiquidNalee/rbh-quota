#!/usr/bin/env python

import argparse
import re
from sys import exit
import subprocess
import smtplib
from email.mime.text import MIMEText
from rbh_quota import config
import MySQLdb


def insert():

    parser = argparse.ArgumentParser(description='Creates a QUOTA table in MySQL database and fills it with the Lustre filesystem quotas')
    parser.add_argument(
        '-H', '--host', required=False, action='store', help='Database host name'
    )
    parser.add_argument(
        '-u', '--user', required=False, action='store', help='Database user name'
    )
    parser.add_argument(
        '-x', '--password', required=False, action='store', help='Database password'
    )
    parser.add_argument(
        '-d', '--database', required=False, action='store', help='Database name'
    )
    parser.add_argument(
	'-a', '--alerts', required=False, action='store', help='Trigger mail on soft quota'
    )    
    parser.add_argument(
	'-m', '--domain', required=False, action='store', help='User mail domain'
    )

    args = parser.parse_args()

    if args.host:
        DB_HOST = args.host
    else:
        if config.db_host:
            DB_HOST = config.db_host
        else:
            print 'ERROR: missing database host name from config file !'
            exit(1)

    if args.user:
        DB_USER = args.user
    else:
        if config.db_user:
            DB_USER = config.db_user
        else:
            print 'ERROR: missing database user name from config file !'
            exit(1)

    if args.password:
        DB_PWD = args.password
    else:
        if config.db_pwd:
            DB_PWD = config.db_pwd
        else:
            print 'ERROR: missing database password from config file !'
            exit(1)

    if args.database:
        DB = args.database
    else:
        if config.db:
            DB = config.db
        else:
            print 'ERROR: missing database from config file !'
            exit(1)

    if args.alerts:
        alerts_on = args.alerts
    else:
        if config.alerts:
            alerts_on = config.alerts
        else:
	    alerts_on = False;

    if args.domain:
        mail_domain = args.domain
    else:
        if config.domain:
            mail_domain = config.domain
        else:
	    if alerts_on:
            	print 'ERROR: alerts activated but mail domain missing from config file !'
            	exit(1)

    try:
        connection = MySQLdb.connect(DB_HOST, DB_USER, DB_PWD, DB)
    except:
        print 'Error: Unable to connect'
        exit(1)
    else:
        db = connection.cursor()

    try:
        db.execute("""SELECT value FROM VARS WHERE varname='FS_Path'""")
    except:
        print 'Error: Query failed to execute'
        exit(1)
    else:
        fs_path = (db.fetchone())[0]

    try:
        db.execute("""DROP TABLE IF EXISTS QUOTA""")
    except:
        print 'Error: Query failed to execute'
        exit(1)

    try:
        db.execute("""CREATE TABLE `QUOTA`
                      (`owner` varchar(127) NOT NULL,
                      `softBlocks` bigint(20) unsigned DEFAULT '0',
                      `hardBlocks` bigint(20) unsigned DEFAULT '0',
                      `softInodes` bigint(20) unsigned DEFAULT '0',
                      `hardInodes` bigint(20) unsigned DEFAULT '0',
                      PRIMARY KEY (`owner`) )""")
    except:
        print 'Error: Query failed to execute'
        exit(1)

    try:
        db.execute("""SELECT DISTINCT(uid), SUM(size), SUM(count) FROM ACCT_STAT GROUP BY uid""")
    except:
        print 'Error: Query failed to execute'
        exit(1)
    else:
        user = db.fetchall()
	i = 0
        while (i < len(user)):
            p = subprocess.Popen(["lfs", "quota", "-u", user[i][0], fs_path], stdout=subprocess.PIPE)
	    out = p.communicate()[0].replace('\n', ' ')
	    values = re.findall('([\d]+|\-)\s(?![(]uid)', out)
            db.execute("INSERT INTO QUOTA VALUES('" + user[i][0] + 
				"', " + values[1] + ", " + values[2] + 	
				", " + values[5] + ", " + values[6] + ")")
	    if (user[i][1] >= 0):
		p = subprocess.Popen(["touch", "rbh-quota-tmpMailFile"], stdout=subprocess.PIPE)
		fp = open("rbh-quota-tmpMailFile", 'w+r')
		p = subprocess.Popen(["echo", "Warning :\nYou, " + user[i][0] + ", have reached your softBlock quota of " + values[1] + " on " + fs_path], stdout=fp)
		msg = MIMEText(fp.read())
		fp.close()
		p = subprocess.Popen(["rm", "-f", "rbh-quota-tmpMailFile"], stdout=subprocess.PIPE)
		msg['Subject'] = '[Warning] softBlock quota reached'
		msg['From'] = 'rbh-quotaAlert'
		msg['To'] = user[i][0] + '@' + mail_domain
	        s = smtplib.SMTP('localhost')
#		s.sendmail('rbh-quotaAlert', user[i][0] + '@' + mail_domain, msg.as_string())
		s.quit()

	    i += 1

    try:
        db.close()
    except:
        print 'Error: Connection to database/carbon server failed to close'
        exit(1)
