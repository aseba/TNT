#!/usr/bin/python
# -*- coding: utf-8 -*-
import readline
import datetime
import os
import pickle
import re

from urllib2 import URLError
from threading import Thread
from time import sleep

import util

from tnt import Tnt

# Just a little colored fun
CSI="\x1B["
COLOR_GREY = CSI+'31;10m'
COLOR_RED = CSI+'31;10m'
COLOR_GREEN = CSI+'32;10m'
COLOR_YELLOW = CSI+'33;10m'
COLOR_BLUE = CSI+'34;10m'
COLOR_MAGENTA = CSI+'35;10m'
COLOR_CYAN = CSI+'36;10m'
COLOR_WHITE = CSI+'37;10m'

HILIGHT_FILENAME = os.environ['HOME']+'/.tnt/hilights'
CONFIG_FILENAME = os.environ['HOME']+'/.tnt/ttyConfig'

class Tty(object):
    def __init__(self):
        self._sleeptime = 0
        self._loadConfig()
        while (self.config['run']):
            try:
                if(self._sleeptime):
                    print(u'──> Trying to revive...')
                print(u'──> Starting Tnt Engine'.encode('utf-8'))
                self.tnt = Tnt(self, 30)
                print(u'──> Starting Application'.encode('utf-8'))
                self.main()
                self.tnt.run()
            except URLError:
                self._sleeptime += 10
                print(u'──> Uoops! connection problems, sleeping %s secs'.encode('utf-8') % (self._sleeptime))
                sleep(self._sleeptime)
            except KeyboardInterrupt:
                print(u'──> Apllication killed'.encode('utf-8'))
                self.config['run'] = False
            except Exception, bug:
                print(u'──> Uoops! System crashed: %s'.encode('utf-8') % (bug))

    def requestAuthPin(self, url):
            print(u"It's the first time you run TNT\nYou must grant access to your twitter account.. Please visit "+ url +" and do it... Don't worry, we are cool :)\n".encode('utf-8'))
            pin = ''
            while(not pin.isdigit()):
                pin = raw_input('Please, enter the pin twitter gave you: '.encode('utf-8'))
            return pin

    def main(self):
        self._sleeptime = 0
        words = [ friend.GetScreenName() for friend in self.tnt.getFriends() ]
        readline.parse_and_bind("tab: complete")
        completer = VolcabCompleter(words)
        readline.set_completer(completer.complete)
        print(u'──> Command Mode ON'.encode('utf-8'))
        while(self.config['run']):
            try:
                action = raw_input(u'> ')
            except KeyboardInterrupt:
                break
            action = action.decode('utf-8')
            action = action.lstrip().rstrip()
            if(action.startswith(':')):
                command = action.split(' ')[0][1:].lower()
                method = getattr(self, 'do_' + command, None)
                if(not method):
                    print(u'──>  Unknown Command'.encode('utf-8'))
                else:
                    parameters = ' '.join(action.split(' ')[1:])
                    if(len(action.split(' ')) > 1):
                        method(params = parameters)
                    else:
                        method()
            elif(action == ''):
                pass
            else:
                tester = re.compile(":\w*")
                if(tester.search(action) is None):
                    self.do_tweet(action)
                else:
                    print(u'──> What you are twitting seems as a failed tty command:'.encode('utf8'))
                    what_to_do = u''.encode('utf8')
                    while(what_to_do not in (u'y',u'n',u'yes',u'no')):
                        what_to_do = raw_input(u'──> Are you sure you want to tweet "%s"? (y/n): '.encode('utf8') % (action.encode('utf8')))
                    if(what_to_do in (u'y',u'yes')):
                        self.do_tweet(action)
                    else:
                        print(u'──> Tweet canceled')
        self._finish()

    def _finish(self):
        self._saveConfig()
        self.tnt.stop()
        print(u'──> Bye Bye!'.encode('utf-8'))

    def _saveConfig(self):
        file = open(CONFIG_FILENAME, 'w')
        pickle.dump(self.config, file)
        file.close()
    
    def _loadConfig(self, starting=True):
        print(u'──> Loading Config'.encode('utf-8'))
        if (os.path.exists(CONFIG_FILENAME) and os.path.isfile(CONFIG_FILENAME)):
            file = open(CONFIG_FILENAME, 'r')
            self.config = pickle.load(file)
            if(starting):
                self.config['run'] = True
            file.close()
        else:
            self.config = {'run': True, 'showFullName': True, 'hilight': list()}

    def updated(self, friendstl):
        for pos in xrange(friendstl*-1,0):
            self.printStatus(pos)

    def printStatus(self, pos):
        print_string = u"%(reset_color)s%(datetime)s %(id_color)s%(id)d :%(threading_color)s%(threading)s %(name)s%(nick_color)s%(username)s : %(text_color)s%(text)s%(reset_color)s"
        tweet_out_data = {"reset_color": COLOR_WHITE}
        #First, the info
        if(self.config['showFullName']):
            tweet_out_data['name'] = self.tnt.getAuthorNameFor(pos)+' '
        else:
            tweet_out_data['name'] = u''
        tweet_out_data['username'] = u'@' + self.tnt.getAuthorScreenNameFor(pos)
        tweet_out_data['id'] = self.tnt.getIdFor(pos)
        tweet_out_data['text'] = util.unescape(self.tnt.getTextFor(pos))
        tweet_out_data['datetime'] = unicode(datetime.datetime.fromtimestamp(self.tnt.getTimeFor(pos)).strftime("%H:%M:%S"))
        order = self.tnt.getThreadPositionOf(self.tnt.getIdFor(pos))
        if(order > 0):
            tweet_out_data['threading'] = u' └─' + u'─' * (order-1) + u'> '
        else: 
            tweet_out_data['threading'] = ''
        # we set colors
        # if the tweet speaks about the user
        tweet_out_data["threading_color"] = COLOR_RED
        tweet_out_data["nick_color"] = COLOR_RED
        if(self.tnt.getTextFor(pos).find(self.tnt.getUser().GetScreenName()) > -1):
            tweet_out_data["id_color"] = COLOR_CYAN
            tweet_out_data["text_color"] = COLOR_YELLOW
        # if the tweet's author is the user or the author is in the hilight list
        elif(self.tnt.getAuthorScreenNameFor(pos).find(self.tnt.getUser().GetScreenName()) > -1):
            tweet_out_data["id_color"] = COLOR_CYAN
            tweet_out_data["text_color"] = COLOR_GREEN
        elif('@'+self.tnt.getAuthorScreenNameFor(pos) in self.config['hilight']):
            tweet_out_data["id_color"] = COLOR_MAGENTA
            tweet_out_data["text_color"] = COLOR_MAGENTA
        # if it's a normal tweet
        else:
            tweet_out_data["id_color"] = COLOR_GREEN
            tweet_out_data["text_color"] = COLOR_WHITE
        # now we print it
        final_print_string = print_string % tweet_out_data
        print(final_print_string.encode('utf-8'))

    def do_tweet(self, message, inreplyto=None):
        #self.tnt.tweet(message)
        if(len(message) > 140):
            wtd = ''
            wtd = raw_input(u"──> Your tweet is longer than 140 chars. Send? type yes (y) or no (n): ".encode('utf-8'))
            while(not wtd.lower() in ['yes','y', 'no', 'n']):
                wtd = raw_input('──> Please, just type yes/y or no/n: '.encode('utf-8'))
            if(wtd in ['yes','y']):
                self.tnt.tweetWithCheck(message, inreplyto)
        else:
            self.tnt.tweetWithCheck(message, inreplyto)

    def askIfSplit(self):
            wtd = ''
            wtd = raw_input(u"──> Your tweet is longer than 140 chars. Do you want to split it (s) or cut it (c)?: ".encode('utf-8'))
            while(not wtd.lower() in ['c','s']):
                wtd = raw_input('──> Please, just type c or s: '.encode('utf-8'))
            if(wtd == 's'):
                return True
            else:
                return False

    def do_reply(self, **kwargs):
        if(len(kwargs['params'].split(' ')) >= 2):
            replyingID = kwargs['params'].split(' ')[0]
            message = ' '.join(kwargs['params'].split(' ')[1:])
            onick = self.tnt.getAuthorOf(replyingID)
            self.do_tweet(u'@'+ onick + ' ' + message, replyingID)
    do_r = do_reply
   
    def do_replies(self, **kwargs):
        self.tnt.getReplies()
    do_p = do_replies

    def do_hilight(self, **kwargs):
        if not (kwargs.has_key('params')):
            print((u'──> Hilight list: %s' % (self.config['hilight'])).encode('utf-8'))
        else:
            if(len(kwargs['params'].split(' ')) == 1):
                nick = kwargs['params'].split(' ')[0]
                print(u'──> Hilighting %s' % (nick))
                if(nick not in self.config['hilight']):
                    self.config['hilight'].append(nick)
            else:
                print(u'──> Hilight: wrong param set'.encode('utf-8'))
    do_hl = do_hilight

    def do_remhilight(self, **kwargs):
        if not (kwargs.has_key('params')):
            print((u'──> Hilight list: %s' % (self.config['hilight'])).encode('utf-8'))
        else:
            if(len(kwargs['params'].split(' ')) == 1):
                nick = kwargs['params'].split(' ')[0]
                print(u'──> UnHilighting %s' % (nick))
                try:
                    self.config['hilight'].remove(nick)
                except:
                    print(u'──> UnHilighting: That user is not on the hilight list'.encode('utf-8'))
            else:
                print(u'──> Hilight: wrong param set'.encode('utf-8'))
    do_rhl = do_remhilight

    def do_quit(self, **kwargs):
        self.config['run'] = False
    do_q = do_quit

    def do_timeline(self, **kwargs):
        if not (kwargs.has_key('params')):
            print(u'──> Timeline Search: wrong param set'.encode('utf-8'))
        else:
            if(len(kwargs['params'].split(' ')) == 1):
                nick = kwargs['params'].split(' ')[0]
                print(u'──> Searching %s'.encode('utf-8') % (nick.encode('utf-8')) )
                try:
                    self.tnt.getUserTimeline(nick)
                except:
                    print(u'──> Error : Wrong User?'.encode('utf-8'))
    do_tl = do_timeline

    def do_showFullnames(self, **kwargs):
        newstatus = not self.config['showFullName']
        print(u'──> Show Fullnames: %s' % (newstatus))
        self.config['showFullName'] = newstatus
    do_f = do_showFullnames

    def do_retweet(self, **kwargs):
        if((len(kwargs['params'].split(' ')) == 1) and (kwargs['params'].split(' ')[0])):
            tweetid = kwargs['params'].split(' ')[0]
            ostatus = getThreadPositionOf(tweetid)
            nick = self.tnt.getAuthorScreenName(ostatus)
            message = self.tnt.getTextFor(ostatus)
            completeTweet = 'rt: '+nick+' '+message
            print(u'──> Searching %s'.encode('utf-8') % (nick.encode('utf-8')) )
            self.tnt.getUserTimeline(nick)
        else:
            print(u'──> Retweet: wrong param set'.encode('utf-8'))
    do_rt = do_retweet

    def do_directmessage(self, **kwargs):
        if not (kwargs.has_key('params')):
            for dm in reversed(self.tnt.getDirectMessages()):
                print_string = u"%(threading_color)s%(threading)s%(reset_color)s%(datetime)s %(id_color)s%(id)d : %(name)s%(nick_color)s%(username)s %(text_color)s: %(text)s%(reset_color)s"
                tweet_out_data = {"reset_color": COLOR_WHITE}
                tweet_out_data['username'] = u'@' + dm.sender_screen_name
                tweet_out_data['id'] = self.tnt.getIdFor(pos)
                tweet_out_data['text'] = util.unescape(self.tnt.getTextFor(pos))
                tweet_out_data['datetime'] = unicode(datetime.datetime.fromtimestamp(self.tnt.getTimeFor(pos)).strftime("%H:%M:%S"))
                tweet_out_data["id_color"] = COLOR_CYAN
                tweet_out_data["text_color"] = COLOR_YELLOW
                toprint = dm.sender_screen_name + u": "+ dm.text
                print(toprint.encode("utf-8"))
        elif(len(kwargs['params'].split(' ')) >= 2):
            user = kwargs['params'].split(' ')[0]
            message = ' '.join(kwargs['params'].split(' ')[1:])
            self.tnt.sendDirectMessage(user,message)
        else:
            print(u'──> DM: wrong param set'.encode('utf-8'))
    do_dm = do_directmessage

    def do_help(self, **kwargs):
        print(u':tl [@user] : Show las statuse of user'.encode('utf-8'))
        print(u':r [id] [message] : Replies to a message that maches the [id]'.encode('utf-8'))
        print(u':p : Prints las mentions'.encode('utf-8'))
        print(u':hl : List hilighted users|words'.encode('utf-8'))
        print(u':hl [user|word] : Adds the user|word to the list of hilights'.encode('utf-8'))
        print(u':rhl [user|word] : Removes the user|word to the list of hilights'.encode('utf-8'))
    do_h = do_help

class VolcabCompleter:
    def __init__(self, volcab):
        self.volcab = volcab

    def complete(self, text, state):
        results =  [x for x in self.volcab if x.startswith(text)] + [None]
        return results[state]

if __name__ == "__main__":
    Tty()
