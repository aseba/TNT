import curses, sys
from curses.wrapper import wrapper as cdo #Curses do, get it?
from pdb import set_trace

def wtf():
    curses.nocbreak(); 
    curses.echo()
    set_trace()

def reset ():
    #    curses.noecho()
    #curses.cbreak()
    pass


['addch', 'addnstr', 'addstr', 'attroff', 'attron', 'attrset', 'bkgd', 'bkgdset', 'border', 'box', 'clear', 'clearok', 'clrtobot', 'clrtoeol', 'cursyncup', 'delch', 'deleteln', 'derwin', 'echochar', 'enclose', 'erase', 'getbegyx', 'getbkgd', 'getch', 'getkey', 'getmaxyx', 'getparyx', 'getstr', 'getyx', 'hline', 'idcok', 'idlok', 'immedok', 'inch', 'insch', 'insdelln', 'insertln', 'insnstr', 'insstr', 'instr', 'is_linetouched', 'is_wintouched', 'keypad', 'leaveok', 'move', 'mvderwin', 'mvwin', 'nodelay', 'nooutrefresh', 'notimeout', 'noutrefresh', 'overlay', 'overwrite', 'putwin', 'redrawln', 'redrawwin', 'refresh', 'resize', 'scroll', 'scrollok', 'setscrreg', 'standend', 'standout', 'subpad', 'subwin', 'syncdown', 'syncok', 'syncup', 'timeout', 'touchline', 'touchwin', 'untouchwin', 'vline']    

class TNTGui(object):
    def __init__(self):
        self.prompt="[%03d]"
        #Window relative attributes
        self.max_x=0
        self.max_y=0
        self.text_buffer = ""
        super(TNTGui, self).__init__()
        #We need a curses window object
        window = curses.initscr()
        cdo(self._fillWindowData)     
        cdo(self.hidListener)

    def _getInitialPrompt(self):
        return self.prompt % 140

   
    def _getPrompt(self):
        return self.prompt % (140 - len(self.text_buffer.rstrip()))

    def _getPromptText(self, window, prompt=None):
        prompt_text = window.instr(self.max_y,self._startX(), 140)
        return prompt_text

    
    def _destroy(self, exitval=0):
        curses.nocbreak(); 
        curses.echo()
        curses.endwin()
        sys.exit(exitval)
        
    def _startX(self):
        return len(self._getPrompt())+1
        
    def _endX(self):
        return len(self.prompt)+141
    
    def _drawWindow(self, window):
        window.clear()
        window.hline(self.max_y-1,0,'>',self.max_x )
        window.addstr(self.max_y,0,self._getPrompt())
        window.refresh()
        
    def _updatePrompt(self,window):
        cur_y, cur_x = window.getyx()
        window.addstr(self.max_y,0,self._getPrompt())
        window.move(cur_y, cur_x+1)
    
    def _fillWindowData(self, window):
        self.max_y, self.max_x = window.getmaxyx()
        self.max_y -= 1
        self.max_x -= 1
        cdo(self._drawWindow)
        self._moveToOrigin(window)
        
            
    def hidListener(self,window):
        running = True
        try:
            while running:
                curses.echo()
                curses.cbreak()
                window.keypad(1) #FIXME: This patches a bug in wrapper
                last_stroke = window.getch()
                running = cdo(self.processKeystroke, last_stroke)
                
        except KeyboardInterrupt:
            pass
        except Exception, e:
            raise
            self._destroy(1)
        self._destroy()
    
    def processKeystroke(self, window, kstroke):
        if kstroke in [curses.KEY_ENTER, 10]:
            cdo(self._commitBuffer)
        else:		
            self._textInput(window,kstroke)
        cdo(self._updatePrompt)
        return True
        
    def _commitBuffer(self,window):
        write_buffer = self._getPromptText(window)
        cdo(self._drawWindow)
        cdo(self._moveToOrigin)
        
    def _textDeleteAtCursor(self, window):
        y,x = window.getyx()
        x -= self._startX()
        #self.write_buffer.pop(x)
        #window.addch(127)#curses.KEY_BACKSPACE)
        
        
    def _textInput(self, window, kstroke):
        self.text_buffer = self._getPromptText(window)

            
    
    def _moveToOrigin(self, window):
        window.move(self.max_y, self._startX())
        
        
        
if ( __name__ == "__main__" ):
    TNTGui()
