# -*- coding: utf-8 -*-
import os
import os.path
import pickle
import urllib2
import time

import tinyurl

from threading import Thread

from oauthtwitter import OAuthApi

from localexceptions import NotAuthorizedException

try:
    import sqlite3 as sqlite
except ImportError:
    import sqlite

#twitter oauth staff
CONSUMER_KEY = 'CyHMeMPDAu2Ct5MELdpKEQ'
CONSUMER_SECRET = 'Yh21vGIiMrWBu4TnjWPKxETI5JCGBiRQ7vHEQ6ynY'
TNT_PATH = os.environ['HOME']+'/.tnt-devel/'
ACCESS_TOKEN_FILENAME = TNT_PATH+'access.tkn'
QUEUEDB = TNT_PATH+"queuedb.sqlite.db"
VERSION_FILE = TNT_PATH+"tnt.version"
DB_INITIALIZATION_TWITTS="CREATE TABLE twitts (tid varchar PRIMARY KEY, created_at varchar, in_reply_to varchar, text varchar, author varchar,is_reply varchar, is_dm varchar);"
DB_UPGRADE_0_1=("ALTER TABLE twitts ADD COLUMN is_reply varchar;", "ALTER TABLE twitts ADD COLUMN is_dm varchar;")
DB_INITIALIZATION_USER_TWITTS="CREATE TABLE user_twitts (tid varchar, whos_timeline varchar);"
LOGFILE = TNT_PATH+'log'


if not os.path.exists(TNT_PATH):
    #Create conf folder on first run
    os.mkdir(TNT_PATH)

if not os.path.isfile(QUEUEDB):
    #Create DB on first run
    a_connection = sqlite.Connection(QUEUEDB)
    a_cursor = a_connection.cursor()
    a_cursor.execute(DB_INITIALIZATION_TWITTS)
    a_cursor.execute(DB_INITIALIZATION_USER_TWITTS)
    a_connection.commit()
    a_connection.close()
    version_file = open(VERSION_FILE, 'w')
    version_file.write("1")
    version_file.close()


if not os.path.isfile(VERSION_FILE):
    #Upgrade DB from version 0 to 1
    a_connection = sqlite.Connection(QUEUEDB)
    a_cursor = a_connection.cursor()
    for each_query in DB_UPGRADE_0_1:
        a_cursor.execute(each_query)
    a_cursor.execute(DB_INITIALIZATION_USER_TWITTS)
    a_connection.commit()
    a_connection.close()
    version_file = open(VERSION_FILE, 'w')
    version_file.write("1")
    version_file.close()
    

class Logger(object):
    def __init__(self):
        if not (os.path.exists(LOGFILE) and os.path.isfile(LOGFILE)):
            self.file = open(LOGFILE, 'w')
        else:
            self.file = open(LOGFILE, 'a') 
    def log(self, message):
        import datetime
        towrite = (datetime.datetime.now().strftime("%D %H:%M:%S") + ' ' + message +'\n').encode('utf-8')
        self.file.write(towrite)
        self.file.close()

class AuthFail(Exception):
    """
    Basic Exception to raise when authorization was not possible. 
    """
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)

class FakeRawTwitt(object):
    def __init__(self, results):
        """
        tid, created_at, in_reply_to, text, author
        """
        self.contents=results
    def GetId(self):
        return int(self.contents[0])
    def GetCreatedAtInSeconds(self):
        return int(self.contents[1])
    def GetInReplyToStatusId(self):
        in_reply_to = self.contents[2]
        if in_reply_to:
            in_reply_to = int(in_reply_to)
        return in_reply_to
    def GetText(self):
        return self.contents[3]
    def GetUser(self):
        class dummy_user(object):
            def GetId(ignore):
                return int(self.contents[4])
        return dummy_user()
        
def load_twitt(twitterId):
    conn = sqlite.Connection(QUEUEDB)
    cursor=conn.cursor()
    sql_query = """SELECT tid, created_at, in_reply_to, text, author FROM twitts WHERE tid=?"""
    cursor_result = cursor.execute(sql_query, (str(twitterId), ))
    results = cursor_result.fetchone()
    cursor.close()
    conn.close()
    result_twitt = None
    if results:
        result_twitt = Twitt(FakeRawTwitt(results))
    return result_twitt

class Twitt(object):
    def __init__(self, status, db_conn=None):
        self.tid = status.GetId()
        self.created_at = status.GetCreatedAtInSeconds()
        self.in_reply_to = status.GetInReplyToStatusId()
        self.text = status.GetText()
        self.author = status.GetUser().GetId()
        self.index = None
        super(Twitt, self).__init__()
        if db_conn: 
            sql_query = """SELECT 1 FROM twitts WHERE tid=?"""
            self.cursor = db_conn.cursor()
            if not self.cursor.execute(sql_query, (str(self.tid), )).fetchone():
                self.save()
                db_conn.commit()
            self.cursor.close()

    def save(self):
        sql_query = """INSERT INTO twitts (tid, created_at, in_reply_to, text, author) VALUES (?, ?, ?, ?, ?)"""
        self.cursor.execute(sql_query, (self.tid, self.created_at, self.in_reply_to, self.text, self.author))


class TwittQueue(object):
    def __init__(self, threaded=True):
        self.messages = {}
        self.index = []
        self.dm_index = []
        self.replies_index = []
        self.last_update = []
        self.threaded = threaded
        self.thread_identifier = ''
        self.oaapi = None

    def setOAApi(self, oaapi):
        self.oaapi = oaapi

    def reindex(self, start_position=0):
        for ind in range(start_position,len(self.index)):
            twitt_to_reindex = self.messages.get(self.index[ind], None)
            if twitt_to_reindex is not None:
                twitt_to_reindex.index = ind

    def append(self, twitt_list): 
        db_conn = sqlite.Connection(QUEUEDB)
        update_length = 0
        #twitt_list.reverse()
        if self.threaded:
            update_length = self._appendThreaded(twitt_list, db_conn)
        else:
            update_length = self._appendUnthreaded(twitt_list, db_conn)
        db_conn.commit()
        db_conn.close()
        return update_length

    def latest(self):
        if self.index:
            latest = self.index[-1]
        else:
            conn = sqlite.Connection(QUEUEDB)
            cursor=conn.cursor()
            sql_query = """SELECT tid FROM twitts WHERE created_at=(SELECT  MAX(created_at) FROM twitts)"""
            cursor_result = cursor.execute(sql_query)
            results = cursor_result.fetchone()
            cursor.close()
            conn.close()
            latest = results and results[0] or None
        return latest

    def length(self):
        return len(self.index)

    def text(self, pos):
        return self.messages[self.index[pos]].text
    
    def time(self, pos):
        return self.messages[self.index[pos]].created_at
        
    def author(self, pos):
        return self.messages[self.index[pos]].author
        
    def mid(self, pos):
        return self.index[pos]

    def getMessage(self, mid):
        """
        This method is supposed to fetch the message at all costs
        """    
        message = self.messages.get(mid, None) or self._fetchFromDb(mid) or self._fetchFromWeb(mid)
        return message

    def getPosition(self, mid):
        return self._resolveThreadPosition(mid)

    def _fetchFromDb(self, mid):
        twitt = load_twitt(mid)
        if twitt:
            self.index.insert(0, twitt.tid)
            twitt.index = 0
            self.messages[mid] = twitt
            self.reindex()
            return twitt

    def _fetchFromWeb(self, mid):
        #FIXME: WTF happens if this mid is not accessible or existent?
        Logger().log("_fetchFromWeb() : Fetching from web")
        status = self.oaapi.GetStatus(mid)
        self.append([status])
        return self.messages.get(status.GetId())
    
    def _appendUnthreaded(self, twitt_list, db_conn):
        update_list = []
        for raw_twitt in twitt_list:
            update_list.append(Twitt(raw_twitt, db_conn))
        self.last_update = [updated.tid for updated in update_list]
        update_list.reverse()
        return self._append(update_list)

    def _appendThreaded(self, twitt_list, db_conn):
        full_update = []
        self._appendUnthreaded(twitt_list, db_conn)
        for tid in self.last_update:
            twitt_thread = [self.messages[tid]] + self._resolveThread(self.messages[tid].in_reply_to)
            full_update.extend(twitt_thread)
        full_update.reverse()
        return  self._append(full_update)

    def _append(self, twitt_list):
        update_length = len(set(twitt_list))
        for twitt in twitt_list:
            if twitt.tid not in self.messages:
                self.messages[twitt.tid] = twitt
            if twitt.tid in self.index:
                current_index =self.index.index(twitt.tid)
                self.index.pop(current_index)
                self.reindex(current_index)
            self.index.append(twitt.tid)
            self.messages[twitt.tid].index = len(self.index)-1

        return update_length #len(twitt_list)


    def _resolveThread(self, twitt_id):
        full_thread = []
        twitt = self.messages.get(twitt_id, None)
        if not twitt:
            twitt = self._fetchFromDb(twitt_id) #dont use getMessage to avoid hitting so much twitter
        if (twitt is not None):
            if (twitt.tid in self.index):
                self.index.pop(twitt.index)
                self.reindex(twitt.index)
            full_thread.append(twitt)
            full_thread.extend(self._resolveThread(twitt.in_reply_to))
        return full_thread

    def _resolveThreadPosition(self, message_id):
        position = 0
        if self.messages[message_id].in_reply_to in self.messages:
            position+=1
            position += self._resolveThreadPosition(self.messages[message_id].in_reply_to)
        return position
        
            
class FriendList(object):
    def __init__(self):
        self.friends = {}
        self.oaapi = None
        
    def setOAApi(self, oaapi):
        self.oaapi = oaapi

    def addUsers(self, friend_list):
        for friend in friend_list:
            self.friends[friend.GetId()] = friend
            
    def fetchMissingUser(self, userid):
        tolog = 'fetchMissingUser((%s) %s) : getting User' % (type(userid), userid)
        Logger().log(tolog)
        new_user = self.oaapi.GetUser(userid)
        if new_user:
            self.addUsers([new_user])
        
        return new_user

    def getScreenNameFor(self, userid):
        user = self.friends.get(userid, '')
        if not user:
            user = self.fetchMissingUser(userid)
        return user and user.GetScreenName() or 'UnNamed'

    def getNameFor(self, userid):
        user = self.friends.get(userid, '')
        if not user:
            user = self.fetchMissingUser(userid)

        return user and user.GetName() or 'UnNamed'
    

class Tnt (object):

    def __init__(self, guiHandle, sleep=30):
        super(Tnt, self).__init__()
        self._authorized = False
        self._access_token = ''
        self._user = ''
        self._friendsTL = TwittQueue()
        self._friendList = FriendList()
        self.oauthapi = None
        self.guiHandle = guiHandle
        self.sleep = sleep
        self.runner = None
        #initialize
        self.authorize()
        self._start()

    def _start(self):
        self.doRun = True
        self.executeRefresh = True #used to stop refreshing while preparing threads like timeline or replies
        self.runner = Thread(target=self.run)
        self.runner.setDaemon(True)
        self.runner.start()

    def stop(self):
        self.doRun = False 

    def _authorizeFromFile(self):
        if(os.path.exists(ACCESS_TOKEN_FILENAME) and os.path.isfile(ACCESS_TOKEN_FILENAME)):
            file = open(ACCESS_TOKEN_FILENAME, 'r')
            self._access_token = pickle.load(file)
            file.close()
            return True
    
    def _authorizeBootstrap(self):
        """
        """
        oauth_api = OAuthApi(CONSUMER_KEY, CONSUMER_SECRET)
        request_token = oauth_api.getRequestToken()
        pin = self.guiHandle.requestAuthPin(
                            oauth_api.getAuthorizationURL(request_token))
        if (not pin) or (isinstance(pin, str) and not pin.isdigit()):
            #I rather do this ugly check than catch this later and have no clue
            #of what is causing the erro
            raise AuthFail("The retrieved pin is not valid")
        self._access_token = OAuthApi(CONSUMER_KEY, CONSUMER_SECRET, 
                                    request_token).getAccessToken(pin)
        #Lets write this access token to a filename to reload it next time
        #Lets check if directory .tnt exists
        directory = os.environ['HOME']+'/.tnt'
        if not (os.path.exists(directory) and os.path.isdir(directory)):
            os.mkdir(directory)
        file = open(ACCESS_TOKEN_FILENAME, 'w')
        pickle.dump(self._access_token, file)
        file.close()

    def authorize(self):
        """
        First Method to call, this initializes all, if it is not called and
        succesful, TNT will not work
        """
        self._authorizeFromFile() or self._authorizeBootstrap()
        if not self._access_token:
            raise AuthFail("Access Token retrieval was not possible.")
        Logger().log("authorize() : Loging in to twitter")
        self.oauthapi = OAuthApi(CONSUMER_KEY, CONSUMER_SECRET, self._access_token)
        Logger().log("authorize() : LFetching user info from web")
        self._user = self.oauthapi.GetUserInfo()
        self._friendList.setOAApi(self.oauthapi)
        self._friendsTL.setOAApi(self.oauthapi)
        friends_list = []
        friends_page=0
        while len(friends_list)<self._user.friends_count:
            Logger().log("authorize() : LFetching friends from web")
            friends_list += self.oauthapi.GetFriends(page=friends_page)
            friends_page+=1
        self._friendList.addUsers(friends_list)

    def run(self):
        while(self.doRun):
            if not self.executeRefresh:
                time.sleep(5) #sleep 5 secs till I finish doing some things
            else:
                Logger().log("run() : Fetching friends timeline from web")
                latest_status = self.oauthapi.GetFriendsTimeline(since_id=self._friendsTL.latest()) 
                if latest_status:
                    self.guiHandle.updated(self._friendsTL.append(latest_status))
                time.sleep(self.sleep)

    def setThreadIdentifier(self, identifier):
        self._friendsTL.thread_identifier = identifier
        
    def getTextFor(self, index):
        return self._friendsTL.text(index)
        
    def getTimeFor(self, index):
        return self._friendsTL.time(index)
        
    def getAuthorNameFor(self, index):
        author = self._friendsTL.author(index)
        return self._friendList.getNameFor(author)

    def getAuthorScreenNameFor(self, index):
        author = self._friendsTL.author(index)
        return self._friendList.getScreenNameFor(author)
        
    def getIdFor(self, index):
        return self._friendsTL.mid(index)
        
    def getLength(self):
        return self._friendsTL.length()

    def getAuthorOf(self, message_id):
        author = self._friendList.getScreenNameFor(self._friendsTL.getMessage(message_id).author)
        return author

    def getThreadPositionOf(self, message_id):
        return self._friendsTL.getPosition(message_id)

    def isNewTweet(self, message_id):
        return message_id in self._friendsTL.last_update
    
    def isMentioned(self, text):
        return self._user.GetScreenName() in text

    def isMine(self, message_id):
        return self.getAuthorOf(message_id) == self._user.GetScreenName()
    
    #Deprecated, you must use tweetWithCheck and add askIfSplit in the client. True if you want to split the long tweet, False if you just want to cut it and send the first 140 chars
    def tweet(self, message, reply=None):
        for text in message.split(' '):
            if(text.startswith('http') and len(text) >= 27): #len of a tinyurl
                newLink = tinyurl.create_one(text)
                message = message.replace(text,newLink)
        if self.oauthapi is None:
            raise NotAuthorizedException()
        Logger().log("tweet() : Tweeting")
        status = self.oauthapi.PostUpdates(message.encode('utf-8'), in_reply_to_status_id=reply)
        return status

    def tweetWithCheck(self, message, reply=None):
        status = list()
        for text in message.split(' '):
            if(text.startswith('http') and len(text) >= 27):
                newLink = tinyurl.create_one(text)
                message = message.replace(text,newLink)
        if self.oauthapi is None:
            raise NotAuthorizedException()
        if(len(message) > 140):
            if (self.guiHandle.askIfSplit()):
                #http://snippets.dzone.com/posts/show/5641
                import math
                # v = value to split, l = size of each chunk
                f = lambda v, l: [v[i*l:(i+1)*l] for i in range(int(math.ceil(len(v)/float(l))))]
                messages = f(message,140)
                for message in messages:
                    Logger().log("tweetWithCheck() : Tweeting")
                    status.append(self.oauthapi.PostUpdates(message.encode('utf-8'), in_reply_to_status_id=reply))
            else:
                message = message[:140]
                Logger().log("tweetWithCheck() : Tweeting")
                status.append(self.oauthapi.PostUpdates(message.encode('utf-8'), in_reply_to_status_id=reply))
        else:
            Logger().log("tweetWithCheck() : Tweeting")
            status.append(self.oauthapi.PostUpdates(message.encode('utf-8'), in_reply_to_status_id=reply))
        return status

    # Still to be ported to tnt2

    def getUser(self):
        return self._user

    def getDirectMessages(self):
        Logger().log("getDirectMessages() : Getting DMS from web")
        return self.oauthapi.GetDirectMessages()

    def sendDirectMessage(self, to, message):
        Logger().log("sendDirectMessage() : Sending DM")
        return self.oauthapi.PostDirectMessage(to, message.encode('utf-8'))

    def getRemainingHits(self):
        Logger().log("getRemaininHits() : Getting remaining hits")
        return self.oauthapi.GetRemainingHits()
    
    def getUserTimeline(self, screenname):
        self.executeRefresh = False
        Logger().log("getUserTimeline() : Fetching User from web")
        user = self.oauthapi.GetUser(screenname)
        Logger().log("getUserTimeline() : Fetching user timeline from web")
        tl = self.oauthapi.GetUserTimeline(id=user.GetId())
        if tl:
            self.guiHandle.updated(self._friendsTL.append(tl))
        self.executeRefresh = True
    
    def getFriends(self):
        return self.oauthapi.GetFriends()
    
    # This must be checked, it is toooooo slow, maybe we shouldnt send it before it is complete
    def getReplies(self):
        self.executeRefresh = False
        Logger().log("getReplies() : Fetching replies from web")
        replies = self.oauthapi.GetReplies()
        if replies:
            self.guiHandle.updated(self._friendsTL.append(replies))
        self.executeRefresh = True
