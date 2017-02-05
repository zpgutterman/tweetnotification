#!/usr/bin/python
# Tweet user notifications
# by Zach Gutterman January 2017  @zpgutterman
#
# Checks a list of twitter accounts, logs if there is a new tweet
# Can set a cron job to run every 5 minutes
#
# Original twitter Code modified from: Tim Bueno
# https://github.com/timbueno/SimpleTweetArchiver
#

import tweepy
import datetime
from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
from tweepy import Stream
import os
import sys
import psycopg2
from config import config
# For logging
import traceback
import time
import datetime
try:
    import json
except ImportError:
    import simplejson as json

pidfile = "/tmp/tweets.pid"
# The consumer keys can be found on your application's Details page located at
#  https://dev.twitter.com/apps (under "OAuth settings")
consumer_key="w9OIdxjf2ouoYypchOhdCOPjC"
consumer_secret="6gWyVDGY310vgupjE8jMVntRY1TG2Jyk6touP0a7uT8pANOqPz"
# The access tokens can be found on your applications's Details page located at
# https://dev.twitter.com/apps (located under "Your access token")
access_token="107847765-1fCRztdH0Nwms4XPPetTaHrlHoZdbxo4pclR8pvh"
access_token_secret="sza0GpkGtcp0btgzQ8bMuC7VLif1RVLKFsHR6qNr3TfYX"

# TWITTER ACCOUNTS TO CHECK
theUserName = ['realDonaldTrump',
               'zachgutterman',
               'devtestingTC']

# keywords to send additional alerts
keyword_alert = ['keyword']


# Create Twitter API Object
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)


# connect to db and write message

def writetweet(msgsub, msgtext):
    """ Connect to the PostgreSQL database server """
    conn = None
    sql = """INSERT INTO tweet_log(tweet,tweet_date,handle )
        VALUES(%(tweet)s, %(tweet_date)s, %(handle)s) RETURNING tweet_id;"""
    tweet_id = None
    try:
        print "connecting to db"
        # read database configuration
        params = config()
        # connect to the PostgreSQL database
        conn = psycopg2.connect(**params)
        # create a new cursor
        cur = conn.cursor()

        tweetdict = ({"tweet": msgtext.encode('utf8'), "tweet_date": datetime.datetime.now(), "handle": msgsub.encode('utf8')})
        # execute the INSERT statement
        cur.execute(sql, tweetdict)
        # get the generated id back
        tweet_id = cur.fetchone()[0]
        # commit the changes to the database
        conn.commit()
        # close communication with the database
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

    return tweet_id


# print tweet
def sendnotification(msgsub, msgtxt): # subject and main text
    # my setup has two levels ALERT and INFO, so any word in the keyword_alert list will be a classified as an alert
    # {"lvl":"1","sub":"xxxxxx","txt":"xxxxxx","img":"xxx","del":"10000"}
    print ("-- @"+msgsub.encode('utf8') + " - " + msgtxt.encode('utf8'))

    msgjson = json.dumps(dict(
                                        lvl='1',
                                        sub=msgsub,
                                        txt=msgtxt.encode('utf8'),
                                        delay='20000',
                                    ))
    print msgjson

    if any(word in msgtxt.lower() for word in keyword_alert): # checking for keyword in keyword_alert list
        print "-- ALERT KEYWORD FOUND"



def main_loop():
    # clear the screen
    # display current date and time
    now = datetime.datetime.now()
    # step though all the twitter accounts.
    for z in theUserName:
        print " "
        print "************"
        print "-- checking Twitter User : @" +z +" "+now.strftime("%Y-%m-%d %H:%M")
        # tweetid file
        idFile = z + '.tweetid'
        pwd = os.getcwd() # use the current working directory
        pwd = pwd.strip('"\n')
        idFile = os.path.join(pwd, idFile) # join dir and filename
        print "-- TweetIDFile : " + idFile

        # helpful variables
        status_list = [] # Create empty list to hold statuses
        cur_status_count = 0 # set current status count to zero

        if os.path.exists(idFile):
            # Get most recent tweet id from file
            f = open(idFile, 'r')
            idValue = f.read()
            f.close()
            idValue = int(idValue)
            print "-- tweetID file found! "
            print "-- tweetID read from file " + str(idValue)
            print "-- checking to see if there is any new tweets... "

            # Get first page of unarchived statuses

            while True:
                try:
                    statuses = api.user_timeline(count=200, include_rts=True, since_id=idValue, screen_name=z)
                except tweepy.error.TweepError:
                    print "#### ERROR getting tweet ####"
                    print "-- We will pause for 60 seconds before trying again"
                    sendnotification("tweet2mqtt",("Error getting tweet for : @" +z))
                    time.sleep(60)
                    continue
                break
            # Get User information for display
            if statuses != []:
                theUser = statuses[0].author
                total_status_count = theUser.statuses_count

            while statuses != []:
                cur_status_count = cur_status_count + len(statuses)
                for status in statuses:
                    status_list.append(status)

                theMaxId = statuses[-1].id
                theMaxId = theMaxId - 1
                # Get next page of unarchived statuses
                statuses = api.user_timeline(count=200, include_rts=True, since_id=idValue, max_id=theMaxId, screen_name=z) #changed from 200 to 50

        else:
            print "-- No tweetID file found"
            print "-- Please create a new archive file called : " +idFile
            print ""
            sendnotification("tweet2mqtt",("No tweetid file found for @"+z))
            time.sleep(20)

        # Write most recent tweet id to file for reuse if it isn't blank
        if status_list != []:
            for status in reversed(status_list):
                sendnotification(z,status.text)
                writetweet(z,status.text)
            # Write most recent tweet id to file
            print "-- saving last tweet id to file. ID:"+str(status_list[0].id)
            f = open(idFile, 'w')
            f.write(str(status_list[0].id))
            f.close()
        print "-- We had found " + str(len(status_list)) + " more tweets since you last run"
        print "-- Finished with account : @" + z
        # Delay to read the screen
        time.sleep(2)

if __name__ == '__main__':

    pid = str(os.getpid())
    if os.path.isfile(pidfile):
        print "%s already exists, exiting" % pidfile
        sys.exit()
    else:
        file(pidfile, 'w').write(pid)

    try:
        main_loop()
        os.unlink(pidfile)

    except:
        print >> sys.stderr, '\nExiting by user request.\n'
        type, value, tb = sys.exc_info()
        traceback.print_exc()
        last_frame = lambda tb=tb: last_frame(tb.tb_next) if tb.tb_next else tb
        frame = last_frame().tb_frame
        ns = dict(frame.f_globals)
        ns.update(frame.f_locals)
        traceback.print_exc(file=open("errlog.txt","w"))
        os.unlink(pidfile)
        sys.exit(0)