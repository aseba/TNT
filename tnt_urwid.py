#!/usr/bin/python
# -*- coding: utf-8 -*-
#Heavily inspired on 
# Urwid example fibonacci sequence viewer / unbounded data demo
#    Copyright (C) 2004-2007  Ian Ward
#DialogDisplay and InputDialogDisplay are an almost exact copy of
# http://excess.org/urwid/browser/dialog.py?rev=65%3Af71120f89f4a
# Urwid example similar to dialog(1) program
#    Copyright (C) 2004-2007  Ian Ward
#Both Licenced under GPL

import sys, os
import datetime
import pickle
from tnt import Tnt
from tnt import TNT_PATH
from threading import Thread
try:
    import urwid
    import urwid.curses_display
except ImportError, import_error:
    print """
    Sorry dude or gal, you need to install urwid to use this wonderful
    app, please visit http://excess.org/urwid , this is most likely available
    for your distro.
    In the meantime, try tty
    """
    sys.exit(1)

class DialogExit(Exception):
    pass

#------------------------------------------------------------------
class DialogDisplay(object):
    palette = [
        ('body','black','light gray', 'standout'),
        ('border','black','dark blue'),
        ('shadow','white','black'),
        ('selectable','black', 'dark cyan'),
        ('focus','white','dark blue','bold'),
        ('focustext','light gray','dark blue'),
        ]
        
    def __init__(self, text, height, width, body=None):
        width = int(width)
        if width <= 0:
            width = ('relative', 80)
        height = int(height)
        if height <= 0:
            height = ('relative', 80)
    
        self.body = body
        if body is None:
            # fill space with nothing
            body = urwid.Filler(urwid.Divider(),'top')

        self.frame = urwid.Frame( body, focus_part='footer')
        if text is not None:
            self.frame.header = urwid.Pile( [urwid.Text(text),
                urwid.Divider()] )
        w = self.frame
        
        # pad area around listbox
        w = urwid.Padding(w, ('fixed left',2), ('fixed right',2))
        w = urwid.Filler(w, ('fixed top',1), ('fixed bottom',1))
        w = urwid.AttrWrap(w, 'body')
        
        # "shadow" effect
        w = urwid.Columns( [w,('fixed', 2, urwid.AttrWrap(
            urwid.Filler(urwid.Text(('border','  ')), "top")
            ,'shadow'))])
        w = urwid.Frame( w, footer = 
            urwid.AttrWrap(urwid.Text(('border','  ')),'shadow'))

        # outermost border area
        w = urwid.Padding(w, 'center', width )
        w = urwid.Filler(w, 'middle', height )
        w = urwid.AttrWrap( w, 'border' )
        
        self.view = w
        super(DialogDisplay, self).__init__()


    def add_buttons(self, buttons):
        l = []
        for name, exitcode in buttons:
            b = urwid.Button( name, self.button_press )
            b.exitcode = exitcode
            b = urwid.AttrWrap( b, 'selectable','focus' )
            l.append( b )
        self.buttons = urwid.GridFlow(l, 10, 3, 1, 'center')
        self.frame.footer = urwid.Pile( [ urwid.Divider(),
            self.buttons ], focus_item = 1)

    def button_press(self, button):
        raise DialogExit(button.exitcode)
    
    def main(self):
        self.ui = urwid.curses_display.Screen()
        self.ui.register_palette( self.palette )
        return self.ui.run_wrapper( self.run )
            
    def run(self):
        self.ui.set_mouse_tracking()
        size = self.ui.get_cols_rows()
        try:
            while True:
                canvas = self.view.render( size, focus=0 )
                self.ui.draw_screen( size, canvas )
                keys = None
                while not keys: 
                    keys = self.ui.get_input()
                for k in keys:
                    if urwid.is_mouse_event(k):
                        event, button, col, row = k
                        self.view.mouse_event( size, 
                            event, button, col, row,
                            focus=0)
                    if k == 'window resize':
                        size = self.ui.get_cols_rows()
                    k = self.view.keypress( size, k )

                    if k:
                        self.unhandled_key( size, k)
        except DialogExit, e:
            return self.on_exit( e.args[0] )
        
    def on_exit(self, exitcode):
        return exitcode, ""
        


class InputDialogDisplay(DialogDisplay):
    def __init__(self, text, height, width):
        self.edit = urwid.Edit()
        body = urwid.ListBox([self.edit])
        body = urwid.AttrWrap(body, 'selectable','focustext')
        super(InputDialogDisplay, self).__init__(text, height, width, body)
        self.frame.set_focus('body')
    
    def unhandled_key(self, size, k):
        if k in ('up','page up'):
            self.frame.set_focus('body')
        if k in ('down','page down'):
            self.frame.set_focus('footer')
        if k == 'enter':
            # pass enter to the "ok" button
            self.frame.set_focus('footer')
            self.view.keypress( size, k )
    
    def on_exit(self, exitcode):
        return exitcode, self.edit.get_edit_text()
        
#------------------------------------------------------------------

class TwittsWalker(urwid.ListWalker):
    """ListWalker-compatible class for browsing twitts from tnt2
    """
    def __init__(self, tnt, hl_list):
        self.focus = (1, 0)
        self.last_focus_change = None
        self.tnt = tnt
        self.hl_list = hl_list
        self.twitt_layout = TwittLayout()

    
    def _get_at_pos(self, pos_tuple):
        """Return a widget and the position passed."""
        pos = pos_tuple[1]
        if (pos < self.tnt.getLength()) and (pos >= 0):
            columns = [] 
            message_id = self.tnt.getIdFor(pos)
            hour_text= "[%s]" % datetime.datetime.fromtimestamp(self.tnt.getTimeFor(pos)).strftime("%H:%M:%S")
            hour = urwid.AttrWrap(urwid.Text(hour_text),'hour') 
            columns.append(('fixed',len(hour_text), hour))
            number_text = " %s :" % self.tnt.getIdFor(pos)
            number = urwid.AttrWrap(urwid.Text(number_text),'twitnumber') 
            columns.append(('fixed', len(number_text), number))


            new_char=' '
            if self.tnt.isNewTweet(message_id):
                new_char = '>'
            new_indicator = urwid.AttrWrap(urwid.Text(new_char),'thread_indicator')
            columns.append(('fixed', 1, new_indicator))

            nickname_text = " %s (@%s): " % (self.tnt.getAuthorNameFor(pos), self.tnt.getAuthorScreenNameFor(pos))
            nickname = urwid.AttrWrap(urwid.Text(nickname_text),'nickname')
            nickname_length = 40 #arbitrary lenght, cheaper in processing than calculating the longest
            if len(nickname_text) > 40:
                nickname_length = len(nickname_text)
            columns.append(('fixed', nickname_length, nickname)) 

            thread_order = self.tnt.getThreadPositionOf(message_id)
            if thread_order:
                thread_arrow = u'└─' + u'─' * (thread_order-1) + u'> '
                thread_indicator = urwid.AttrWrap(urwid.Text(thread_arrow),'thread_indicator')
                columns.append(('fixed', len(thread_arrow), thread_indicator))

            text_text = "%s" % self.tnt.getTextFor(pos)
            text_color = 'text'
            if self.tnt.isMentioned(text_text):
                text_color += '_mentioned'
            if self.tnt.isMine(message_id):
                text_color = 'text_mine' #I wont create that many palettes
            if ("@"+self.tnt.getAuthorScreenNameFor(pos).lower()) in self.hl_list:
                text_color = 'hilight'
            clean_text = self.tnt.getTextFor(pos).replace("&lt;","<").replace("&gt;",">")
            text = urwid.AttrWrap(urwid.Text("%s" % clean_text), text_color)
            columns.append(text)
            to_print = urwid.Columns(columns, dividechars=1), pos_tuple
        else:
            to_print = urwid.Text("[%d]" % pos, layout=self.twitt_layout), pos_tuple
        return to_print

    
    def get_focus(self): 
        return self._get_at_pos(self.focus )
    
    def set_focus(self, focus):
        self.focus = focus
        self._modified()

    def updated(self, update_len=None, size=(0,)):
        screen_height = size[0]-2 #minus the message composition line and the info line
        twitt_list_length = self.tnt.getLength() 

        #if (update_len and size) and (twitt_list_length > screen_height):
        #    offset = 1+twitt_list_length - screen_height
        #    focus_to_change = (offset+1, offset)
        #    if self.focus == self.last_focus_change:
        #        self.set_focus(focus_to_change)
        #    self.last_focus_change = focus_to_change 
        #else:
        if (self.last_focus_change is not None) and (self.focus[0] >= self.last_focus_change):
            focus=(self.focus[0]+1, self.focus[1]+1)
            self.set_focus(focus)
	    self.last_focus_change=focus[0]
        else:
            self.last_focus_change = self.focus[0]
	    self._modified()
    
    def get_next(self, start_from):
        a, b = start_from
        focus = (b, b+1)
        return self._get_at_pos(focus)
    
    def get_prev(self, start_from):
        """
        Called on arrow down
        """
        #FIXME: This repeats a lot of times the first element when start_from == 1
        a, b = start_from
        if b <= 0:
            focus = (1, 0)
        else:
            focus = (a -1, a)
        return self._get_at_pos(focus)   

class TwitterDisplay(object):
    palette = [
        ('body','light gray','black', 'standout'),
        ('foot','light gray', 'black', None),
        ('key','light cyan', 'black', 'underline'),
        ('title', 'white', 'black', None),
        ('nickname','light green','black', 'standout'),
        ('hour','light gray', 'black', None),
        ('twitnumber','light cyan', 'black', ),
        ('thread_indicator','dark red', 'black', 'standout'),
        ('text', 'white', 'black', None),
        ('text_mentioned','yellow','black', 'standout'),
        ('hilight', 'black', 'light gray', None),
        ('text_mine','light green','black', 'standout'),
        ]

        
    footer_text = [
        ('title', "TNT Urwid Frontend"), "    ",
        ('key', "UP"), ", ", ('key', "DOWN"), ", ",
        ('key', "PAGE UP"), " and ", ('key', "PAGE DOWN"),
        " move view  ",
        ('key', "Esc"), " exits",
        ]
    
    def __init__(self):
    	self._cheap_queue=dict()
        self.tnt = Tnt(self, 180)
        self.hl_list = self._readHilightList() or list()
        self.tnt.setThreadIdentifier(u'└─>')
        self.twitt_walker = TwittsWalker(self.tnt, self.hl_list) 
        self.twitter_scroll_box = urwid.ListBox(self.twitt_walker)
        self.info_bar = urwid.AttrWrap(urwid.Text(self.footer_text ),'foot')
        self.text_edit_area = urwid.AttrWrap(urwid.Edit(caption="[ 140]"), 'body')
        self.twitt_display_area = urwid.Frame(urwid.AttrWrap( self.twitter_scroll_box, 'body'), footer=self.info_bar)
        self.body=urwid.Pile([self.twitt_display_area,('flow',self.text_edit_area)])

    def main(self):
        self.ui = urwid.curses_display.Screen()
        self.ui.register_palette( self.palette )
        self.ui.run_wrapper( self.run )

    def updated(self, update_len):
        size = self.ui.get_cols_rows()
        self.twitt_walker.updated(update_len, size)
        canvas = self.body.render(size, focus=0)
        self.ui.draw_screen( size, canvas )
        
    def requestAuthPin(self, authURL):
        dialog = InputDialogDisplay("Please go to the following URL and authorize TNT for your account. \nPaste the resulting PIN Number in the textbox below and press enter. \n%s" % authURL, 0, 0)
        dialog.add_buttons([("Submit", 0)])
        return dialog.main()[1]

    def askIfSplit(self):
        return False

    def run(self):
        size = self.ui.get_cols_rows()
        urwid.set_encoding("utf-8")
        self.body.set_focus(1)
        while 1:
            self.body.set_focus(1)
            canvas = self.body.render(size, focus=True)
            self.ui.draw_screen( size, canvas )
            keys = None
            while not keys: 
                keys = self.ui.get_input()
            for k in keys:
                if k == 'window resize':
                    size = self.ui.get_cols_rows()
                    canvas = self.body.render(size, focus=True)
                    self.ui.draw_screen( size, canvas )
                elif k == 'esc':
                    self.do_quit()    
                elif k == 'enter':
                    self.commitText()
                elif ("up" in k) or ("down" in k):
                    self.body.set_focus(0)
                else:
                    self.body.set_focus(1)
                    #self.text_edit_area.keypress((1,), k) 
                    self.updatePrompt()
                self.body.keypress(size, k)
                self.body.set_focus(1)

                d_keys =  self._cheap_queue.keys() #not smart to iterate a dict and delete elements on the process
                for cheap_thread_key in d_keys:
                    if not self._cheap_queue[cheap_thread_key].isAlive():
                        self._cheap_queue[cheap_thread_key].join()
                        del(self._cheap_queue[cheap_thread_key])

                
    def commitText(self):
        text_to_send = self.text_edit_area.get_edit_text()
        temp_thread=Thread(target=self._process_command, args=(text_to_send,))
        self._cheap_queue[id(temp_thread)]=temp_thread
        self._cheap_queue[id(temp_thread)].start()
        #self._process_command(text_to_send)
        self.text_edit_area.set_edit_text("")
        self.updatePrompt()

    def updatePrompt(self):
        current_length = 140 - len(self.text_edit_area.get_edit_text())
        self.text_edit_area.set_caption("[ %03d] "% current_length)

    def lart(self, lart_title, lart_message=None):
        pass

    def _process_command(self, action):
        if action.startswith("/"):
            command_params = action.split(' ',1)
            command = command_params[0][1:].lower()
            params = ((len(command_params) > 1) and (command_params[1])) or None
            method = getattr(self, 'do_' + command, lambda x: None)
            method(params)
        elif len(action)>0:
            self.tnt.tweet(action)

    def _saveHilightList(self):
        file = open(TNT_PATH + 'hilights', 'w')
        pickle.dump(self.hl_list, file)
        file.close()

    def _readHilightList(self):
        done = False
        if(os.path.exists(TNT_PATH) and os.path.isfile(TNT_PATH + 'hilights')):
            file = open(TNT_PATH + 'hilights', 'r')
            hl = pickle.load(file)
            file.close()
            return hl
            
        
    #-- Actions --#    
    def _extract_params(self, params, message):
        split_message = message.split(' ', len(params)-1)
        param_dict = None
        if len(split_message) == len(params):
            param_dict = dict(zip(params, split_message))
        return param_dict


    def do_quit(self):
        sys.exit(0)
    do_q = do_quit

    def do_reply(self, message):
        args = self._extract_params(['id', 'message'], message)
        if args:
            replyingTo = self.tnt.getAuthorOf(args['id'])
            self.tnt.tweet('@%s %s' % (replyingTo, args['message']), args['id'])
        else:
            self.lart('reply')
    do_r = do_reply

    def do_dm(self, message):
        args = self._extract_params(['id', 'message'], message)
        if args and args['id'].startswith('@'):
            self.tnt.sendDirectMessage(args['id'], args['message'])
        else:
            self.lart('dm')

    def do_retweet(self, message):
        args = self._extract_params(['id'], message)
        if args:
            rtmessage = self.getMessage(args['id'])
            if(rtmessage):
                author = self.tnt.getAuthorOf(rtmessage.tid)
                text = 'RT @%s : %s' % (author, rtmessage.text)
                self.tnt.tweet(text)
            else:
                self.lart('retweet', "This message does not exist")
        else:
            self.lart('retweet')
    do_rt = do_retweet

    def do_hilight(self, message):
        args = self._extract_params(['id'], message)
        if args['id']:
            self.hl_list.append(args['id'].lower())
            self.twitt_walker.updated()
            self._saveHilightList()
    do_hl = do_hilight
    
    def do_unhilight(self, message):
        args = self._extract_params(['id'], message)
        if args['id'] and (args['id'].lower() in self.hl_list):
            self.hl_list.remove(args['id'].lower())
            self.twitt_walker.updated()
            self._saveHilightList()
    do_uhl = do_unhilight
    do_dehilight = do_unhilight


    def do_tweet(self, action):
        self.tnt.tweetWithCheck(action)


class TwittLayout(urwid.TextLayout):
    """
    TextLayout class for bottom-right aligned numbers
    """
    def layout( self, text, width, align, wrap ):
        """
        Return layout structure for right justified numbers.
        """
        linestarts = range( 0, 1, width )
        return [[(width, x, x+width)] for x in linestarts]


def main():
    TwitterDisplay().main()
    


if __name__=="__main__": 
    main()
