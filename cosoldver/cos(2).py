#!/usr/bin/env python3
"""COS - Channel Operating System v2.0"""
import curses, os, subprocess, platform, shlex, random, math
from datetime import datetime

CP_MENUBAR,CP_MENU_SEL,CP_DESKTOP,CP_WINDOW,CP_WIN_TITLE = 1,2,3,4,5
CP_STATUS,CP_CURSOR,CP_TEXT,CP_BRIGHT,CP_SHADOW = 6,7,8,9,10
CP_INPUT,CP_WARN,CP_GREEN = 11,12,13
_CLIP = ''

def init_colors():
    curses.start_color(); curses.use_default_colors()
    curses.init_pair(CP_MENUBAR,  curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(CP_MENU_SEL, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(CP_DESKTOP,  curses.COLOR_CYAN,  curses.COLOR_BLUE)
    curses.init_pair(CP_WINDOW,   curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(CP_WIN_TITLE,curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(CP_STATUS,   curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(CP_CURSOR,   curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(CP_TEXT,     curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(CP_BRIGHT,   curses.COLOR_YELLOW,curses.COLOR_BLUE)
    curses.init_pair(CP_SHADOW,   curses.COLOR_BLACK, curses.COLOR_BLUE)
    curses.init_pair(CP_INPUT,    curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(CP_WARN,     curses.COLOR_RED,   curses.COLOR_BLACK)
    curses.init_pair(CP_GREEN,    curses.COLOR_GREEN, curses.COLOR_BLACK)

THEMES = [
    (curses.COLOR_BLACK,curses.COLOR_CYAN,  curses.COLOR_CYAN,  curses.COLOR_BLUE),
    (curses.COLOR_GREEN,curses.COLOR_BLACK, curses.COLOR_GREEN, curses.COLOR_BLACK),
    (curses.COLOR_BLACK,curses.COLOR_YELLOW,curses.COLOR_YELLOW,curses.COLOR_BLACK),
    (curses.COLOR_BLACK,curses.COLOR_WHITE, curses.COLOR_WHITE, curses.COLOR_BLACK),
    (curses.COLOR_WHITE,curses.COLOR_BLUE,  curses.COLOR_BLUE,  curses.COLOR_WHITE),
]
THEME_NAMES = ['COS Classic (Blue/Cyan)','Night Mode (Black/Green)',
               'Retro Amber (Black/Yellow)','High Contrast (White/Black)',
               'TCF Blue (Blue/White)']

def apply_theme(idx):
    if 0 <= idx < len(THEMES):
        mf,mb,df,db = THEMES[idx]
        curses.init_pair(CP_MENUBAR,mf,mb); curses.init_pair(CP_STATUS,mf,mb)
        curses.init_pair(CP_DESKTOP,df,db); curses.init_pair(CP_BRIGHT,curses.COLOR_YELLOW,db)

def sys_copy(text):
    global _CLIP; _CLIP = text
    for cmd in (['xclip','-selection','clipboard'],['xsel','-bi'],['wl-copy']):
        try:
            subprocess.run(cmd,input=text.encode(),timeout=2,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            return True
        except: continue
    return False

def sys_paste():
    for cmd in (['xclip','-selection','clipboard','-o'],['xsel','-bo'],['wl-paste']):
        try:
            r=subprocess.run(cmd,capture_output=True,timeout=2,text=True)
            if r.returncode==0: return r.stdout.strip()
        except: continue
    return _CLIP

MENUS = {
    'f':{'label':'FILE','key':'f','items':[
        ('New Session','new_session'),('Open Terminal','open_term'),
        ('----------',None),('Save Log','save_log'),
        ('----------',None),('Exit COS','exit')]},
    'e':{'label':'EDIT','key':'e','items':[
        ('Copy Last Line','copy'),('Paste','paste'),
        ('----------',None),('Clear Screen','clear'),
        ('----------',None),('Preferences','prefs')]},
    'a':{'label':'APPS','key':'a','items':[
        ('System Info','sysinfo'),('File Browser','filebrowser'),
        ('----------',None),('Calculator','calc'),('Clock','clock'),
        ('----------',None),('About COS','about')]},
    'c':{'label':'CONTROL','key':'c','items':[
        ('Processes','processes'),('Disk Usage','disk'),
        ('----------',None),('Network','network'),
        ('----------',None),('Settings','settings')]},
    's':{'label':'SHELLS','key':'s','items':[
        ('COS Shell','shell_cos'),('Batch Shell','shell_batch'),
        ('----------',None),
        ('POS Shell','shell_pos'),('COM Shell','shell_com'),
        ('Retro Shell','shell_retro')]},
    'p':{'label':'POWER','key':'p','items':[
        ('Server Wizard','server_wizard'),('----------',None),
        ('Restart Shell','restart'),('----------',None),
        ('Suspend','suspend'),('Reboot','reboot'),('Shutdown','shutdown')]},
    'o':{'label':'OTHER','key':'o','items':[
        ('Help','help'),('Keyboard Map','keymap'),
        ('----------',None),('Credits','credits')]},
}
MENU_ORDER = ['f','e','a','c','s','p','o']

def _safestr(win, y, x, s, attr=0):
    try: win.addstr(y, x, s, attr)
    except curses.error: pass

class PopupWindow:
    def __init__(self,stdscr,title,lines,width=None):
        self.stdscr=stdscr; self.title=title; self.lines=lines
        H,W=stdscr.getmaxyx()
        self.h=min(len(lines)+4,H-4)
        self.w=width or min(max((len(l) for l in lines),default=20)+6,W-4)
        self.y=max(1,(H-self.h)//2); self.x=max(0,(W-self.w)//2)
    def draw(self):
        try: win=curses.newwin(self.h,self.w,self.y,self.x)
        except: return
        win.bkgd(' ',curses.color_pair(CP_WINDOW)); win.border()
        t=f' {self.title} '
        _safestr(win,0,max(0,(self.w-len(t))//2),t[:self.w-2],curses.color_pair(CP_WIN_TITLE)|curses.A_BOLD)
        for i,line in enumerate(self.lines[:self.h-4]):
            _safestr(win,i+2,2,str(line)[:self.w-4],curses.color_pair(CP_TEXT))
        hint='[ press any key ]'
        _safestr(win,self.h-1,max(0,(self.w-len(hint))//2),hint,curses.color_pair(CP_STATUS))
        win.refresh(); win.getch()

class Dropdown:
    def __init__(self,stdscr,menu_key,col_x):
        self.stdscr=stdscr; self.items=MENUS[menu_key]['items']
        H,W=stdscr.getmaxyx()
        self.h=len(self.items)+2
        self.w=max(len(i[0]) for i in self.items)+4
        self.y=1; self.x=min(col_x,max(0,W-self.w-1))
    def draw(self,sel):
        try: win=curses.newwin(self.h,self.w,self.y,self.x)
        except: return
        win.bkgd(' ',curses.color_pair(CP_WINDOW)); win.border()
        for i,(label,action) in enumerate(self.items):
            a=curses.color_pair(CP_SHADOW) if action is None \
              else curses.color_pair(CP_MENU_SEL)|curses.A_BOLD if i==sel \
              else curses.color_pair(CP_TEXT)
            _safestr(win,i+1,1,f' {label:<{self.w-4}} ',a)
        win.refresh()
    def run(self):
        sel=0
        while self.items[sel][1] is None: sel+=1
        curses.mousemask(curses.ALL_MOUSE_EVENTS|curses.REPORT_MOUSE_POSITION)
        while True:
            self.draw(sel)
            key=self.stdscr.getch()
            if key==curses.KEY_MOUSE:
                try:
                    _,mx,my,_,bstate=curses.getmouse()
                    if self.y<my<self.y+self.h-1 and self.x<mx<self.x+self.w-1:
                        row=my-self.y-1
                        if 0<=row<len(self.items) and self.items[row][1]:
                            return self.items[row][1]
                    else: return None
                except: pass
            elif key==curses.KEY_UP:
                sel=(sel-1)%len(self.items)
                while self.items[sel][1] is None: sel=(sel-1)%len(self.items)
            elif key==curses.KEY_DOWN:
                sel=(sel+1)%len(self.items)
                while self.items[sel][1] is None: sel=(sel+1)%len(self.items)
            elif key in(curses.KEY_ENTER,10,13): return self.items[sel][1]
            elif key==27: return None

# =============================================================================
# SHELL BASE
# =============================================================================
class InShell:
    def __init__(self,stdscr,title,prompt_text,cp=CP_TEXT):
        self.stdscr=stdscr; self.title=title; self._pt=prompt_text
        self.cp=cp; self.output=[]; self.history=[]; self.hist_idx=0; self.running=True
    @property
    def prompt(self): return self._pt
    def write(self,text='',attr=None):
        for line in str(text).split('\n'): self.output.append((line,attr))
    def draw(self,cmd_buf):
        H,W=self.stdscr.getmaxyx(); h,w,y,x=H-2,W-2,1,1
        try: win=curses.newwin(h,w,y,x)
        except: return
        win.bkgd(' ',curses.color_pair(self.cp)); win.border()
        t=f' {self.title} '
        _safestr(win,0,max(0,(w-len(t))//2),t[:w-2],curses.color_pair(CP_WIN_TITLE)|curses.A_BOLD)
        shown=self.output[-(h-4):]
        for i,(line,attr) in enumerate(shown):
            a=attr if attr is not None else curses.color_pair(self.cp)
            _safestr(win,i+1,2,str(line)[:w-4],a)
        inp=f' {self.prompt} {cmd_buf}'
        _safestr(win,h-2,1,' '*(w-2),curses.color_pair(CP_INPUT))
        _safestr(win,h-2,1,inp[:w-2],curses.color_pair(CP_INPUT)|curses.A_BOLD)
        _safestr(win,h-1,1,' ESC=exit  UP/DN=history '[:w-2],curses.color_pair(CP_STATUS))
        win.refresh()
    def process_command(self,cmd): self.write(f'Unknown: {cmd}',curses.color_pair(CP_WARN))
    def run(self):
        cmd_buf=''; curses.curs_set(1); curses.mousemask(0)
        while self.running:
            self.draw(cmd_buf); key=self.stdscr.getch()
            if key==27: break
            elif key in(curses.KEY_ENTER,10,13):
                if cmd_buf.strip():
                    self.history.append(cmd_buf); self.hist_idx=len(self.history)
                    self.write(f'{self.prompt} {cmd_buf}',curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
                    if cmd_buf.strip().lower() in('exit','quit','bye','logout'):
                        self.write('Goodbye.'); self.running=False
                    else: self.process_command(cmd_buf.strip())
                else: self.write(f'{self.prompt}')
                cmd_buf=''
            elif key in(curses.KEY_BACKSPACE,127,8): cmd_buf=cmd_buf[:-1]
            elif key==curses.KEY_UP:
                if self.history and self.hist_idx>0:
                    self.hist_idx-=1; cmd_buf=self.history[self.hist_idx]
            elif key==curses.KEY_DOWN:
                if self.hist_idx<len(self.history)-1:
                    self.hist_idx+=1; cmd_buf=self.history[self.hist_idx]
                else: self.hist_idx=len(self.history); cmd_buf=''
            elif 32<=key<=126: cmd_buf+=chr(key)
        curses.curs_set(0); curses.mousemask(curses.ALL_MOUSE_EVENTS|curses.REPORT_MOUSE_POSITION)

# =============================================================================
# COS SHELL
# =============================================================================
class COSShell(InShell):
    def __init__(self,stdscr):
        super().__init__(stdscr,'COS Shell v1.0','COS>',CP_TEXT)
        self.write('COS Shell -- type "help" for commands, "exit" to quit.'); self.write('')
    def process_command(self,cmd):
        try: parts=shlex.split(cmd)
        except: parts=cmd.split()
        if not parts: return
        verb=parts[0].lower(); args=parts[1:]
        if verb=='help':
            for l in ['  ls [path]   list dir','  cd <path>   change dir',
                      '  pwd         working dir','  echo <text> print',
                      '  cat <file>  show file','  mkdir <dir> make dir',
                      '  rm <file>   remove file','  env         environment',
                      '  run <cmd>   run system cmd','  date        date/time',
                      '  uname       system info','  clear       clear output',
                      '  exit        exit shell']: self.write(l)
        elif verb=='ls':
            path=args[0] if args else '.'
            try:
                entries=sorted(os.listdir(os.path.expanduser(path))); row=''
                for e in entries:
                    m='/' if os.path.isdir(os.path.join(path,e)) else ''
                    row+=f'{e}{m}  '
                    if len(row)>70: self.write('  '+row); row=''
                if row: self.write('  '+row)
            except Exception as e: self.write(f'  Error: {e}',curses.color_pair(CP_WARN))
        elif verb=='cd':
            try: os.chdir(os.path.expanduser(args[0] if args else '~'))
            except Exception as e: self.write(f'  {e}',curses.color_pair(CP_WARN))
        elif verb=='pwd': self.write(f'  {os.getcwd()}')
        elif verb=='echo': self.write('  '+' '.join(args))
        elif verb=='cat':
            if not args: self.write('  Usage: cat <file>',curses.color_pair(CP_WARN)); return
            try:
                with open(os.path.expanduser(args[0])) as f:
                    for line in f.readlines()[:50]: self.write('  '+line.rstrip())
            except Exception as e: self.write(f'  {e}',curses.color_pair(CP_WARN))
        elif verb=='mkdir':
            if not args: self.write('  Usage: mkdir <dir>',curses.color_pair(CP_WARN)); return
            try: os.makedirs(args[0],exist_ok=True); self.write(f'  Created: {args[0]}')
            except Exception as e: self.write(f'  {e}',curses.color_pair(CP_WARN))
        elif verb=='rm':
            if not args: self.write('  Usage: rm <file>',curses.color_pair(CP_WARN)); return
            try: os.remove(args[0]); self.write(f'  Removed: {args[0]}')
            except Exception as e: self.write(f'  {e}',curses.color_pair(CP_WARN))
        elif verb=='env':
            for k,v in sorted(os.environ.items())[:25]: self.write(f'  {k}={v}')
        elif verb=='run':
            if not args: self.write('  Usage: run <cmd>',curses.color_pair(CP_WARN)); return
            try:
                out=subprocess.check_output(args,text=True,timeout=10,stderr=subprocess.STDOUT)
                for line in out.strip().split('\n')[:40]: self.write('  '+line)
            except subprocess.CalledProcessError as e:
                self.write(f'  Exit {e.returncode}',curses.color_pair(CP_WARN))
                if e.output:
                    for line in e.output.strip().split('\n')[:10]: self.write('  '+line,curses.color_pair(CP_WARN))
            except Exception as e: self.write(f'  {e}',curses.color_pair(CP_WARN))
        elif verb=='date': self.write(f'  {datetime.now().strftime("%A, %B %d %Y  %H:%M:%S")}')
        elif verb=='uname':
            u=platform.uname(); self.write(f'  {u.system} {u.node} {u.release} {u.machine}')
        elif verb=='clear': self.output.clear()
        else:
            try:
                out=subprocess.check_output(shlex.split(cmd),text=True,timeout=8,stderr=subprocess.STDOUT)
                for line in out.strip().split('\n')[:40]: self.write('  '+line)
            except FileNotFoundError: self.write(f'  Command not found: {verb}',curses.color_pair(CP_WARN))
            except Exception as e: self.write(f'  {e}',curses.color_pair(CP_WARN))

# =============================================================================
# BATCH SHELL
# =============================================================================
class BatchShell(InShell):
    def __init__(self,stdscr):
        self._drive='C'; self._path='\\COS'; self._vars={}
        super().__init__(stdscr,'COS Batch Shell (DOS Emulation)','',CP_TEXT)
        self.write('COS Batch Shell v1.0'); self.write('(C) TCF Channel Operating System'); self.write('')
    @property
    def prompt(self): return f'{self._drive}:\\COS>'
    def process_command(self,cmd):
        parts=cmd.strip().split(None,1); verb=parts[0].upper(); rest=parts[1] if len(parts)>1 else ''
        if verb in('HELP','/?'):
            for l in ['  DIR           list directory','  CD <path>     change dir',
                      '  MD <path>     make directory','  DEL <file>    delete file',
                      '  COPY <s> <d>  copy file','  TYPE <file>   show file',
                      '  ECHO <msg>    print message','  SET x=val     set variable',
                      '  SET           list variables','  CLS           clear screen',
                      '  VER           version info','  DATE / TIME   date and time',
                      '  MEM           memory status','  PAUSE         wait for key',
                      '  EXIT          exit']: self.write(l)
        elif verb=='DIR':
            try:
                path=os.path.expanduser(rest.strip() or '.'); entries=sorted(os.listdir(path))
                self.write(f' Directory of {os.path.abspath(path)}'); self.write('')
                for e in entries:
                    full=os.path.join(path,e)
                    try:
                        st=os.stat(full); dt=datetime.fromtimestamp(st.st_mtime).strftime('%m/%d/%Y  %I:%M %p')
                        if os.path.isdir(full): self.write(f' {dt}    <DIR>          {e}')
                        else: self.write(f' {dt}    {st.st_size:>12,}  {e}')
                    except: self.write(f'             {e}')
                nd=sum(1 for e in entries if os.path.isdir(os.path.join(path,e)))
                self.write(f'   {len(entries)-nd} File(s)   {nd} Dir(s)')
            except Exception as e: self.write(f' Cannot find path: {e}')
        elif verb=='CD':
            if not rest.strip(): self.write(f' {self._drive}:{self._path}')
            else:
                try:
                    os.chdir(os.path.expanduser(rest.strip()))
                    self._path='\\'+os.getcwd().replace('/','\\').lstrip('\\')
                except: self.write(' The system cannot find the path specified.')
        elif verb in('MD','MKDIR'):
            try: os.makedirs(rest.strip(),exist_ok=True)
            except Exception as e: self.write(f' {e}',curses.color_pair(CP_WARN))
        elif verb in('DEL','ERASE'):
            try: os.remove(rest.strip())
            except Exception as e: self.write(f' {e}',curses.color_pair(CP_WARN))
        elif verb=='COPY':
            import shutil as _sh; p2=rest.split()
            if len(p2)<2: self.write(' Usage: COPY <src> <dst>',curses.color_pair(CP_WARN))
            else:
                try: _sh.copy2(p2[0],p2[1]); self.write('        1 file(s) copied.')
                except Exception as e: self.write(f' {e}',curses.color_pair(CP_WARN))
        elif verb=='TYPE':
            try:
                with open(os.path.expanduser(rest.strip())) as f:
                    for line in f.readlines()[:60]: self.write(line.rstrip())
            except: self.write(' The system cannot find the file specified.')
        elif verb=='ECHO': self.write(rest if rest else 'ECHO is on.')
        elif verb=='SET':
            if '=' in rest:
                k,_,v=rest.partition('='); self._vars[k.strip()]=v.strip()
            elif rest.strip():
                k=rest.strip(); v=self._vars.get(k,os.environ.get(k,''))
                self.write(f' {k}={v}' if v else f' {k} not defined')
            else:
                for k,v in sorted({**dict(os.environ),**self._vars}.items())[:30]: self.write(f' {k}={v}')
        elif verb=='CLS': self.output.clear()
        elif verb=='VER':
            self.write(''); self.write(' Microsoft Windows [Version 10.0.19045]')
            self.write(' (COS Batch Emulation Layer v1.0)'); self.write('')
        elif verb=='DATE': self.write(f' The current date is: {datetime.now().strftime("%a %m/%d/%Y")}')
        elif verb=='TIME': self.write(f' The current time is: {datetime.now().strftime("%H:%M:%S.%f")[:12]}')
        elif verb=='MEM':
            self.write(' Memory Type         Total       Used       Free')
            self.write(' ----------------    --------    -------    -------')
            self.write(' Conventional          640 KB      412 KB    228 KB')
            self.write(' Extended (XMS)      65535 KB     8192 KB  57343 KB')
        elif verb=='PAUSE':
            self.write(' Press any key to continue . . .'); self.stdscr.getch()
        else:
            self.write(f" '{verb}' is not recognized as an internal or external command,")
            self.write('  operable program or batch file.')

# =============================================================================
# POS SHELL
# =============================================================================
class POSShell(InShell):
    def __init__(self,stdscr):
        super().__init__(stdscr,'COS POS Shell - Point of Sale','POS>',CP_GREEN)
        self.inv={'COLA':{'price':1.50,'stock':24,'name':'Cola 12oz'},
                  'CHIPS':{'price':2.00,'stock':18,'name':'Chips Bag'},
                  'WATER':{'price':1.00,'stock':30,'name':'Water Bottle'},
                  'COFFEE':{'price':2.50,'stock':10,'name':'Coffee 16oz'},
                  'SANDWICH':{'price':5.99,'stock':6,'name':'Deli Sandwich'},
                  'CANDY':{'price':0.99,'stock':40,'name':'Candy Bar'},
                  'JUICE':{'price':1.75,'stock':15,'name':'Orange Juice'},
                  'HOTDOG':{'price':3.50,'stock':8,'name':'Hot Dog'}}
        self.cart=[]; self.total=0.0; self.txn=0; self.last_cart=[]; self.last_total=0.0
        self.write('== COS POINT OF SALE SYSTEM =='); self.write('Type HELP for commands.'); self.write('')
    def process_command(self,cmd):
        parts=cmd.strip().split(); verb=parts[0].upper() if parts else ''; args=parts[1:]
        if verb=='HELP':
            for l in ['  INV              show inventory','  ADD <SKU> [qty]  add to cart',
                      '  CART             show cart','  REMOVE <SKU>     remove from cart',
                      '  TOTAL            subtotal + tax','  CHECKOUT         complete sale',
                      '  RECEIPT          print last receipt','  VOID             void cart',
                      '  SALES            daily summary','  STOCK <SKU> <n>  restock',
                      '  PRICE <SKU> <$>  update price','  NEWITEM <S> <$> <name>',
                      '  CLEAR            clear screen','  EXIT             exit']:
                self.write(l,curses.color_pair(CP_GREEN))
        elif verb=='INV':
            self.write('  SKU        PRICE   STOCK  NAME',curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
            self.write('  ---------  ------  -----  ------------------')
            for sku,item in self.inv.items():
                a=curses.color_pair(CP_WARN) if item['stock']<5 else curses.color_pair(CP_GREEN)
                self.write(f"  {sku:<10} ${item['price']:.2f}  {item['stock']:>4}   {item['name']}",a)
        elif verb=='ADD':
            if not args: self.write('  Usage: ADD <SKU> [qty]',curses.color_pair(CP_WARN)); return
            sku=args[0].upper()
            try: qty=int(args[1]) if len(args)>1 else 1
            except: qty=1
            if sku not in self.inv: self.write(f'  Unknown SKU: {sku}',curses.color_pair(CP_WARN))
            elif self.inv[sku]['stock']<qty: self.write(f"  Low stock: {self.inv[sku]['stock']} left",curses.color_pair(CP_WARN))
            else:
                self.cart.append({'sku':sku,'qty':qty,'price':self.inv[sku]['price'],'name':self.inv[sku]['name']})
                sub=qty*self.inv[sku]['price']
                self.write(f"  Added: {qty}x {self.inv[sku]['name']} = ${sub:.2f}",curses.color_pair(CP_GREEN))
        elif verb=='CART':
            if not self.cart: self.write('  Cart is empty.'); return
            self.write('  QTY  SKU        UNIT    SUBTOTAL'); total=0.0
            for item in self.cart:
                sub=item['qty']*item['price']; total+=sub
                self.write(f"  {item['qty']:>3}  {item['sku']:<10} ${item['price']:.2f}  ${sub:.2f}")
            self.write(f'  {"SUBTOTAL":>26} ${total:.2f}',curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
        elif verb=='REMOVE':
            if not args: self.write('  Usage: REMOVE <SKU>',curses.color_pair(CP_WARN)); return
            sku=args[0].upper(); before=len(self.cart)
            self.cart=[c for c in self.cart if c['sku']!=sku]
            self.write(f'  Removed {sku}.' if len(self.cart)<before else f'  {sku} not in cart.')
        elif verb=='TOTAL':
            sub=sum(c['qty']*c['price'] for c in self.cart); tax=sub*0.08
            self.write(f'  Subtotal: ${sub:.2f}'); self.write(f'  Tax (8%): ${tax:.2f}')
            self.write(f'  TOTAL:    ${sub+tax:.2f}',curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
        elif verb=='CHECKOUT':
            if not self.cart: self.write('  Cart is empty.',curses.color_pair(CP_WARN)); return
            sub=sum(c['qty']*c['price'] for c in self.cart); grand=sub*1.08
            for item in self.cart: self.inv[item['sku']]['stock']-=item['qty']
            self.total+=grand; self.txn+=1; self.last_cart=self.cart.copy(); self.last_total=grand; self.cart=[]
            self.write(f'  ** SALE COMPLETE  Txn #{self.txn} **',curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
            self.write(f'  Total: ${grand:.2f}  (type RECEIPT to print)')
        elif verb=='VOID': self.cart=[]; self.write('  Cart voided.',curses.color_pair(CP_WARN))
        elif verb=='RECEIPT':
            if not self.last_cart: self.write('  No previous transaction.'); return
            self.write('  ================================')
            self.write(f'  COS POS  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
            self.write(f'  Txn #{self.txn}'); self.write('  ================================')
            for item in self.last_cart:
                sub=item['qty']*item['price']
                self.write(f"  {item['qty']}x {item['name']:<18} ${sub:.2f}")
            self.write('  --------------------------------')
            tax=self.last_total-(self.last_total/1.08)
            self.write(f'  Tax (8%):              ${tax:.2f}')
            self.write(f'  TOTAL:                 ${self.last_total:.2f}',curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
            self.write('  ================================'); self.write('  ** THANK YOU **')
        elif verb=='SALES':
            avg=self.total/self.txn if self.txn else 0
            self.write(f'  Transactions: {self.txn}'); self.write(f'  Total Sales : ${self.total:.2f}')
            self.write(f'  Average Sale: ${avg:.2f}')
        elif verb=='STOCK':
            if len(args)<2: self.write('  Usage: STOCK <SKU> <n>',curses.color_pair(CP_WARN)); return
            sku=args[0].upper()
            try: qty=int(args[1])
            except: self.write('  Qty must be integer',curses.color_pair(CP_WARN)); return
            if sku not in self.inv: self.write(f'  Unknown: {sku}',curses.color_pair(CP_WARN))
            else: self.inv[sku]['stock']+=qty; self.write(f"  {sku}: stock now {self.inv[sku]['stock']}")
        elif verb=='PRICE':
            if len(args)<2: self.write('  Usage: PRICE <SKU> <$>',curses.color_pair(CP_WARN)); return
            sku=args[0].upper()
            try: price=float(args[1].lstrip('$'))
            except: self.write('  Invalid price',curses.color_pair(CP_WARN)); return
            if sku not in self.inv: self.write(f'  Unknown: {sku}',curses.color_pair(CP_WARN))
            else: old=self.inv[sku]['price']; self.inv[sku]['price']=price; self.write(f'  {sku}: ${old:.2f} -> ${price:.2f}')
        elif verb=='NEWITEM':
            if len(args)<3: self.write('  Usage: NEWITEM <SKU> <$> <name>',curses.color_pair(CP_WARN)); return
            sku=args[0].upper()
            try: price=float(args[1].lstrip('$'))
            except: self.write('  Invalid price',curses.color_pair(CP_WARN)); return
            name=' '.join(args[2:]); self.inv[sku]={'price':price,'stock':0,'name':name}
            self.write(f'  Created {sku}: {name} @ ${price:.2f}')
        elif verb=='CLEAR': self.output.clear()
        else: self.write(f'  Unknown: {verb}  (type HELP)',curses.color_pair(CP_WARN))

# =============================================================================
# COM SHELL
# =============================================================================
class COMShell(InShell):
    def __init__(self,stdscr):
        super().__init__(stdscr,'COS COM Shell - Serial Port Manager','COM>',CP_TEXT)
        self.port=None; self.baud=9600; self.ser=None; self._avail=[]
        self.write('COS COM Shell v1.0 -- Serial Port Manager')
        self.write('Type HELP for commands.'); self.write(''); self._scan()
    def _scan(self):
        found=[]
        for prefix in('/dev/ttyS','/dev/ttyUSB','/dev/ttyACM'):
            for i in range(8):
                p=f'{prefix}{i}'
                if os.path.exists(p): found.append(p)
        self._avail=found
        self.write(f'  Found {len(found)} port(s): {", ".join(found) if found else "none"}')
    def process_command(self,cmd):
        parts=cmd.strip().split(); verb=parts[0].upper() if parts else ''; args=parts[1:]
        if verb=='HELP':
            for l in ['  SCAN             scan for ports','  LIST             list ports',
                      '  OPEN <p> [baud]  open port','  CLOSE            close port',
                      '  SEND <data>      send data','  READ             read data',
                      '  BAUD <rate>      set baud rate','  STATUS           info',
                      '  PING             send ATZ ping','  HAYES            AT reference',
                      '  EXIT             exit']: self.write(l)
        elif verb=='SCAN': self._scan()
        elif verb=='LIST':
            if not self._avail: self.write('  No ports. Try SCAN.'); return
            for p in self._avail: self.write(f'  {p}{" [OPEN]" if p==self.port else ""}')
        elif verb=='OPEN':
            if not args: self.write('  Usage: OPEN <port> [baud]',curses.color_pair(CP_WARN)); return
            port=args[0]
            try: baud=int(args[1]) if len(args)>1 else self.baud
            except: baud=self.baud
            try:
                import serial
                if self.ser: self.ser.close()
                self.ser=serial.Serial(port,baud,timeout=1); self.port=port; self.baud=baud
                self.write(f'  Opened {port} @ {baud} baud.',curses.color_pair(CP_GREEN))
            except ImportError:
                self.port=port; self.baud=baud; self.ser=None
                self.write(f'  pyserial not installed -- simulating {port} @ {baud}',curses.color_pair(CP_BRIGHT))
            except Exception as e: self.write(f'  Error: {e}',curses.color_pair(CP_WARN))
        elif verb=='CLOSE':
            if self.ser: self.ser.close(); self.ser=None
            self.write(f'  Closed {self.port}.' if self.port else '  No port open.'); self.port=None
        elif verb=='SEND':
            data=(' '.join(args) if args else '')+'\r\n'
            if self.ser: self.ser.write(data.encode('ascii',errors='replace')); self.write(f'  >> {data.strip()}',curses.color_pair(CP_BRIGHT))
            elif self.port: self.write(f'  [SIM] >> {data.strip()}',curses.color_pair(CP_SHADOW))
            else: self.write('  No port open.',curses.color_pair(CP_WARN))
        elif verb=='READ':
            if self.ser:
                data=self.ser.read(self.ser.in_waiting or 1)
                if data: self.write(f'  << {data.decode("ascii",errors="replace")}',curses.color_pair(CP_GREEN))
                else: self.write('  (no data)')
            elif self.port: self.write('  [SIM] << OK',curses.color_pair(CP_SHADOW))
            else: self.write('  No port open.',curses.color_pair(CP_WARN))
        elif verb=='BAUD':
            if not args: self.write(f'  Current baud: {self.baud}'); return
            try:
                self.baud=int(args[0])
                if self.ser: self.ser.baudrate=self.baud
                self.write(f'  Baud set to {self.baud}')
            except: self.write('  Invalid baud rate',curses.color_pair(CP_WARN))
        elif verb=='STATUS':
            st='open' if self.ser else ('simulated' if self.port else 'closed')
            self.write(f'  Port : {self.port or "none"}'); self.write(f'  Baud : {self.baud}'); self.write(f'  State: {st}')
        elif verb=='PING':
            if not self.port: self.write('  No port open.',curses.color_pair(CP_WARN)); return
            if self.ser:
                self.ser.write(b'ATZ\r\n')
                import time; time.sleep(0.5)
                resp=self.ser.read(self.ser.in_waiting or 1)
                self.write('  >> ATZ',curses.color_pair(CP_BRIGHT))
                self.write(f'  << {resp.decode("ascii",errors="replace").strip()}',curses.color_pair(CP_GREEN))
            else:
                self.write('  >> ATZ',curses.color_pair(CP_BRIGHT))
                self.write('  << OK  (simulated)',curses.color_pair(CP_GREEN))
        elif verb=='HAYES':
            for l in ['  ATZ         reset modem','  AT          test','  ATA         answer',
                      '  ATH         hang up','  ATDT<n>     dial tone','  ATDP<n>     dial pulse',
                      '  ATI         modem ID','  ATL<0-3>    volume','  ATM<0-2>    speaker mode',
                      '  ATS0=1      auto-answer','  AT&V        view profile','  AT&W        save to NVRAM']:
                self.write(l)
        else: self.write(f'  Unknown: {verb}  (type HELP)',curses.color_pair(CP_WARN))

# =============================================================================
# RETRO SHELL
# =============================================================================
class RetroShell(InShell):
    def __init__(self,stdscr):
        super().__init__(stdscr,'>>> COS RETRO TERMINAL <<<','READY.',CP_GREEN)
        self.program={}
        self.write('*** CHANNEL OPERATING SYSTEM - RETRO TERMINAL ***')
        self.write('*** 64K RAM SYSTEM  ***'); self.write(''); self.write('READY.'); self.write('')
    @property
    def prompt(self): return 'READY.'
    def process_command(self,cmd):
        up=cmd.strip().upper()
        if up and up[0].isdigit():
            num_str,_,code=cmd.partition(' ')
            try: self.program[int(num_str)]=code
            except: self.write('?SYNTAX ERROR')
            return
        if up in('HELP','?'):
            for l in ['COMMANDS:','  PRINT <txt>  print text','  ? <txt>      print text',
                      '  LIST         list program','  RUN          run program',
                      '  NEW          clear program','  DIR          directory',
                      '  MEM          memory status','  TIME / DATE  clock',
                      '  PEEK <addr>  memory peek','  POKE <a> <v> memory poke',
                      '  BYE / EXIT   sign off']: self.write(l,curses.color_pair(CP_GREEN))
        elif up.startswith('PRINT ') or up.startswith('? '):
            text=cmd[6:] if up.startswith('PRINT ') else cmd[2:]
            self.write(text.strip('"\''))
        elif up=='LIST':
            if not self.program: self.write('NO PROGRAM IN MEMORY.')
            else:
                for num in sorted(self.program): self.write(f'{num} {self.program[num]}',curses.color_pair(CP_GREEN))
            self.write('READY.')
        elif up=='RUN':
            if not self.program: self.write('NO PROGRAM IN MEMORY.')
            else:
                self.write('RUNNING...')
                for num in sorted(self.program):
                    code=self.program[num].strip().upper()
                    if code.startswith('PRINT '): self.write(code[6:].strip('"\''))
                self.write('READY.')
        elif up=='NEW': self.program={}; self.write('OK')
        elif up=='DIR':
            try: entries=sorted(os.listdir('.'))[:20]
            except: entries=[]
            self.write('DISK DIRECTORY:')
            for e in entries: self.write(f'  {e.upper():<20}',curses.color_pair(CP_GREEN))
            self.write(f'{len(entries)} FILES'); self.write('READY.')
        elif up in('TIME','DATE'):
            self.write(datetime.now().strftime('%H:%M:%S  %A %B %d %Y').upper()); self.write('READY.')
        elif up=='MEM':
            self.write('MEMORY STATUS:'); self.write('  38911 BYTES FREE')
            self.write('  25025 BYTES USED'); self.write('  (COS RETRO EMULATION)'); self.write('READY.')
        elif up.startswith('PEEK'): self.write(str(random.randint(0,255))); self.write('READY.')
        elif up.startswith('POKE'): self.write('OK')
        elif up=='SYS': self.write('MONITOR NOT AVAILABLE.'); self.write('READY.')
        elif up.startswith('LOAD'): self.write('?FILE NOT FOUND  ERROR'); self.write('READY.')
        elif up.startswith('SAVE'): self.write('?DEVICE NOT READY ERROR'); self.write('READY.')
        elif up in('BYE','LOGOUT','SIGNOFF'): self.write('GOODBYE.'); self.running=False
        else: self.write('?SYNTAX ERROR'); self.write('READY.')

# =============================================================================
# CALCULATOR
# =============================================================================
def run_calculator(stdscr):
    H,W=stdscr.getmaxyx(); h,w=18,34
    wy=max(1,(H-h)//2); wx=max(0,(W-w)//2)
    expr=''; disp='0'; BTN_W=7
    BTNS=[[('CLR','CLR'),('DEL','DEL'),('(','('),(')',')'),],
          [('7','7'),('8','8'),('9','9'),('/','/')],
          [('4','4'),('5','5'),('6','6'),('*','*')],
          [('1','1'),('2','2'),('3','3'),('-','-')],
          [('0','0'),('.','.'),('+','+'),('=','=')]]
    def press(btn):
        nonlocal expr,disp
        if btn=='CLR': expr=''; disp='0'
        elif btn=='DEL': expr=expr[:-1]; disp=expr or '0'
        elif btn=='=':
            try:
                safe={k:getattr(math,k) for k in dir(math) if not k.startswith('_')}
                result=eval(expr,{'__builtins__':{}},safe)
                disp=str(int(result)) if isinstance(result,float) and result==int(result) else str(round(result,10))
                expr=disp
            except ZeroDivisionError: disp='DIV/0'; expr=''
            except: disp='ERROR'; expr=''
        else:
            if disp in('0','ERROR','DIV/0') and btn not in('.','+',' -','*','/','(',')'):
                expr=btn
            else: expr+=btn
            disp=expr
    def draw():
        try: win=curses.newwin(h,w,wy,wx)
        except: return
        win.bkgd(' ',curses.color_pair(CP_WINDOW)); win.border()
        _safestr(win,0,(w-16)//2,' COS Calculator ',curses.color_pair(CP_WIN_TITLE)|curses.A_BOLD)
        _safestr(win,2,1,' '*(w-2),curses.color_pair(CP_INPUT))
        _safestr(win,2,1,f' {disp[-(w-4):]:>{w-4}} ',curses.color_pair(CP_INPUT)|curses.A_BOLD)
        _safestr(win,3,1,f' {expr[-(w-4):]:>{w-4}} ',curses.color_pair(CP_SHADOW))
        for row,row_btns in enumerate(BTNS):
            for col,(label,_) in enumerate(row_btns):
                bx=1+col*BTN_W; by=5+row*2
                color=CP_BRIGHT if label=='=' else CP_WARN if label in('CLR','DEL') else CP_WIN_TITLE
                _safestr(win,by,bx,f'[{label:^5}]',curses.color_pair(color)|curses.A_BOLD)
        _safestr(win,h-1,1,' ESC=close  click or type ',curses.color_pair(CP_STATUS))
        win.refresh()
    curses.curs_set(0); curses.mousemask(curses.ALL_MOUSE_EVENTS)
    while True:
        draw(); key=stdscr.getch()
        if key==27: break
        elif key==curses.KEY_MOUSE:
            try:
                _,mx,my,_,bstate=curses.getmouse()
                if bstate&(curses.BUTTON1_PRESSED|curses.BUTTON1_CLICKED):
                    for row,row_btns in enumerate(BTNS):
                        for col,(_,val) in enumerate(row_btns):
                            bx=wx+1+col*BTN_W; by=wy+5+row*2
                            if my==by and bx<=mx<bx+BTN_W: press(val)
            except: pass
        elif key in(curses.KEY_ENTER,10,13): press('=')
        elif key in(curses.KEY_BACKSPACE,127,8): press('DEL')
        elif 32<=key<=126:
            ch=chr(key)
            if ch in '0123456789.+-*/()': press(ch)
            elif ch.lower()=='c': press('CLR')
    curses.mousemask(curses.ALL_MOUSE_EVENTS|curses.REPORT_MOUSE_POSITION)

# =============================================================================
# PREFERENCES
# =============================================================================
def run_prefs(stdscr,state):
    H,W=stdscr.getmaxyx()
    OPT_KEYS=['pref_clock','pref_mouse','pref_dots']
    OPT_NAMES=['Show clock in status bar','Show mouse coordinates','Desktop dot fill']
    theme_sel=state.get('theme_idx',0); section=0; row_sel=0
    while True:
        h=22; w=min(W-4,50); wy=max(1,(H-h)//2); wx=max(0,(W-w)//2)
        try: win=curses.newwin(h,w,wy,wx)
        except: break
        win.bkgd(' ',curses.color_pair(CP_WINDOW)); win.border()
        _safestr(win,0,(w-16)//2,' COS Preferences ',curses.color_pair(CP_WIN_TITLE)|curses.A_BOLD)
        _safestr(win,2,3,'COLOR THEME:',curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
        for i,name in enumerate(THEME_NAMES):
            mark='(*) ' if i==theme_sel else '( ) '
            a=(curses.color_pair(CP_MENU_SEL)|curses.A_BOLD) if section==0 and i==row_sel else curses.color_pair(CP_TEXT)
            _safestr(win,3+i,4,f'{mark}{name}'[:w-6],a)
        _safestr(win,10,3,'OPTIONS:',curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
        for i,name in enumerate(OPT_NAMES):
            val=state.get(OPT_KEYS[i],True); mark='[X] ' if val else '[ ] '
            a=(curses.color_pair(CP_MENU_SEL)|curses.A_BOLD) if section==1 and i==row_sel else curses.color_pair(CP_TEXT)
            _safestr(win,11+i,4,f'{mark}{name}'[:w-6],a)
        _safestr(win,h-2,3,'TAB=section  SPACE/ENTER=toggle',curses.color_pair(CP_SHADOW))
        _safestr(win,h-1,3,' UP/DN=nav  ESC=close ',curses.color_pair(CP_STATUS))
        win.refresh(); key=stdscr.getch()
        if key==27: break
        elif key==9: section=1-section; row_sel=0
        elif key==curses.KEY_UP:
            limit=len(THEME_NAMES) if section==0 else len(OPT_NAMES)
            row_sel=(row_sel-1)%limit
        elif key==curses.KEY_DOWN:
            limit=len(THEME_NAMES) if section==0 else len(OPT_NAMES)
            row_sel=(row_sel+1)%limit
        elif key in(curses.KEY_ENTER,10,13,ord(' ')):
            if section==0:
                theme_sel=row_sel; state['theme_idx']=theme_sel; apply_theme(theme_sel)
            else:
                k=OPT_KEYS[row_sel]; state[k]=not state.get(k,True)

# =============================================================================
# FILE BROWSER
# =============================================================================
def run_filebrowser(stdscr):
    H,W=stdscr.getmaxyx(); path=os.path.expanduser('~'); sel=0; scroll=0
    while True:
        try:
            raw=sorted(os.scandir(path),key=lambda e:(not e.is_dir(),e.name.lower()))
            entries=[('..',True)]+[(e.name,e.is_dir()) for e in raw]
        except: entries=[('..',True)]
        h=min(len(entries)+8,H-4); w=min(max(len(e[0]) for e in entries)+20,W-4,64)
        wy=max(1,(H-h)//2); wx=max(0,(W-w)//2); max_vis=h-6
        try: win=curses.newwin(h,w,wy,wx)
        except: break
        win.bkgd(' ',curses.color_pair(CP_WINDOW)); win.border()
        _safestr(win,0,(w-14)//2,' File Browser ',curses.color_pair(CP_WIN_TITLE)|curses.A_BOLD)
        _safestr(win,2,2,f'Path: {path}'[:w-4],curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
        vis=entries[scroll:scroll+max_vis]
        for i,(name,is_dir) in enumerate(vis):
            ri=scroll+i
            a=(curses.color_pair(CP_MENU_SEL)|curses.A_BOLD) if ri==sel \
              else curses.color_pair(CP_BRIGHT) if is_dir else curses.color_pair(CP_TEXT)
            _safestr(win,4+i,2,(name+('/' if is_dir else ' '))[:w-4],a)
        _safestr(win,h-2,2,f' {len(entries)} items ',curses.color_pair(CP_SHADOW))
        _safestr(win,h-1,2,' UP/DN=nav  ENTER=open  ESC=close ',curses.color_pair(CP_STATUS))
        win.refresh(); key=stdscr.getch()
        if key==27: break
        elif key==curses.KEY_UP:
            sel=max(0,sel-1)
            if sel<scroll: scroll=sel
        elif key==curses.KEY_DOWN:
            sel=min(len(entries)-1,sel+1)
            if sel>=scroll+max_vis: scroll=sel-max_vis+1
        elif key in(curses.KEY_ENTER,10,13):
            name,is_dir=entries[sel]
            if is_dir:
                new=os.path.dirname(path) if name=='..' else os.path.join(path,name)
                if os.path.isdir(new): path=new; sel=0; scroll=0
        elif key==curses.KEY_RESIZE: H,W=stdscr.getmaxyx()

# =============================================================================
# TERMINAL PASSTHROUGH
# =============================================================================
def run_terminal(stdscr,state):
    curses.def_prog_mode(); curses.endwin()
    print('\033[?1003l',end='',flush=True)
    print(); print('='*60)
    print('  COS Terminal  --  Real Bash Session')
    print('  Type "exit" or Ctrl+D to return to COS.')
    print('='*60); print()
    shell=os.environ.get('SHELL','/bin/bash')
    try: subprocess.run([shell])
    except:
        try: subprocess.run(['/bin/sh'])
        except Exception as e: print(f'Could not launch shell: {e}')
    print(); print('='*60); print('  Returning to COS...'); print('='*60)
    import time; time.sleep(0.5)
    curses.reset_prog_mode()
    print('\033[?1003h',end='',flush=True)
    stdscr.refresh(); state['messages'].append('[COS] Terminal session ended.')

# =============================================================================
# SERVER SETUP WIZARD
# =============================================================================
_SRV_TYPES=[
    ('Apache Web Server','apache'),('Nginx Web Server','nginx'),
    ('SSH Server','ssh'),('Samba File Share','samba'),
    ('FTP Server (vsftpd)','ftp'),('DNS Server (bind9)','dns'),
    ('Mail Server (Postfix)','mail'),('Node.js App Server','nodejs'),
    ('Python Flask App','flask'),('MariaDB Database','mariadb'),
]
_SRV_FIELDS={
    'apache':[('Port','80'),('ServerName','localhost'),('DocRoot','/var/www/html')],
    'nginx': [('Port','80'),('ServerName','localhost'),('Root','/var/www/html')],
    'ssh':   [('Port','22'),('PermitRoot','no'),('PasswordAuth','yes')],
    'samba': [('ShareName','shared'),('Path','/srv/samba/shared'),('Browsable','yes')],
    'ftp':   [('AnonEnable','no'),('LocalEnable','yes'),('WriteEnable','yes')],
    'dns':   [('Zone','example.local'),('Forwarder','8.8.8.8')],
    'mail':  [('Domain','example.com'),('Port','25')],
    'nodejs':[('Port','3000'),('AppPath','/opt/app'),('User','nodeuser')],
    'flask': [('Port','5000'),('Host','0.0.0.0'),('AppPath','/opt/flask')],
    'mariadb':[('Port','3306'),('BindAddr','127.0.0.1'),('RootPwd','changeme')],
}
def _gen_cmds(stype,fields):
    f=fields
    cmds={
        'apache':['sudo apt update && sudo apt install -y apache2',
                  f'sudo sed -i "s/Listen 80/Listen {f.get("Port","80")}/" /etc/apache2/ports.conf',
                  f'echo "ServerName {f.get("ServerName","localhost")}" | sudo tee -a /etc/apache2/apache2.conf',
                  'sudo ufw allow Apache','sudo systemctl enable --now apache2'],
        'nginx': ['sudo apt update && sudo apt install -y nginx',
                  f'# Edit /etc/nginx/sites-available/default: port={f.get("Port","80")} root={f.get("Root","/var/www/html")}',
                  'sudo ufw allow "Nginx HTTP"','sudo systemctl enable --now nginx'],
        'ssh':   ['sudo apt update && sudo apt install -y openssh-server',
                  f'sudo sed -i "s/#Port 22/Port {f.get("Port","22")}/" /etc/ssh/sshd_config',
                  f'sudo sed -i "s/PermitRootLogin.*/PermitRootLogin {f.get("PermitRoot","no")}/" /etc/ssh/sshd_config',
                  f'sudo ufw allow {f.get("Port","22")}/tcp','sudo systemctl enable --now ssh'],
        'samba': ['sudo apt update && sudo apt install -y samba',
                  f'sudo mkdir -p {f.get("Path","/srv/samba/shared")}',
                  f'sudo chmod 777 {f.get("Path","/srv/samba/shared")}',
                  '# Add to /etc/samba/smb.conf:',
                  f'# [{f.get("ShareName","shared")}]',
                  f'#   path = {f.get("Path","/srv/samba/shared")}',
                  f'#   browsable = {f.get("Browsable","yes")}','#   read only = no',
                  'sudo systemctl restart smbd'],
        'ftp':   ['sudo apt update && sudo apt install -y vsftpd',
                  f'sudo sed -i "s/anonymous_enable=YES/anonymous_enable={f.get("AnonEnable","NO").upper()}/" /etc/vsftpd.conf',
                  f'sudo sed -i "s/#local_enable=YES/local_enable={f.get("LocalEnable","YES").upper()}/" /etc/vsftpd.conf',
                  f'sudo sed -i "s/#write_enable=YES/write_enable={f.get("WriteEnable","YES").upper()}/" /etc/vsftpd.conf',
                  'sudo ufw allow 20/tcp && sudo ufw allow 21/tcp','sudo systemctl enable --now vsftpd'],
        'dns':   ['sudo apt update && sudo apt install -y bind9',
                  f'# Add zone {f.get("Zone","example.local")} in /etc/bind/named.conf.local',
                  f'# Forwarder: {f.get("Forwarder","8.8.8.8")} in named.conf.options',
                  'sudo ufw allow Bind9','sudo systemctl enable --now named'],
        'mail':  ['sudo apt update && sudo apt install -y postfix',
                  f'sudo postconf -e "myhostname = mail.{f.get("Domain","example.com")}"',
                  f'sudo postconf -e "mydomain = {f.get("Domain","example.com")}"',
                  'sudo ufw allow Postfix','sudo systemctl enable --now postfix'],
        'nodejs':['curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -',
                  'sudo apt install -y nodejs',
                  f'sudo useradd -m {f.get("User","nodeuser")} 2>/dev/null || true',
                  f'sudo mkdir -p {f.get("AppPath","/opt/app")}',
                  f'sudo ufw allow {f.get("Port","3000")}/tcp',
                  f'# Start: node {f.get("AppPath","/opt/app")}/app.js'],
        'flask': ['sudo apt install -y python3-pip python3-venv',
                  f'sudo mkdir -p {f.get("AppPath","/opt/flask")}',
                  f'cd {f.get("AppPath","/opt/flask")} && python3 -m venv venv',
                  'source venv/bin/activate && pip install flask gunicorn',
                  f'sudo ufw allow {f.get("Port","5000")}/tcp',
                  f'# gunicorn -b {f.get("Host","0.0.0.0")}:{f.get("Port","5000")} app:app'],
        'mariadb':['sudo apt update && sudo apt install -y mariadb-server',
                   'sudo systemctl enable --now mariadb',
                   f'sudo mysql -e "ALTER USER \'root\'@\'localhost\' IDENTIFIED BY \'{f.get("RootPwd","changeme")}\'; FLUSH PRIVILEGES;"',
                   f'sudo sed -i "s/bind-address.*/bind-address = {f.get("BindAddr","127.0.0.1")}/" /etc/mysql/mariadb.conf.d/50-server.cnf',
                   'sudo systemctl restart mariadb','sudo mysql_secure_installation'],
    }
    return cmds.get(stype,['# No commands for this type.'])

def run_server_wizard(stdscr,state):
    H,W=stdscr.getmaxyx()
    def wwin(title,h,w):
        wy=max(1,(H-h)//2); wx=max(0,(W-w)//2)
        try: win=curses.newwin(h,w,wy,wx)
        except: return None,0,0
        win.bkgd(' ',curses.color_pair(CP_WINDOW)); win.border()
        t=f' {title} '
        _safestr(win,0,max(0,(w-len(t))//2),t[:w-2],curses.color_pair(CP_WIN_TITLE)|curses.A_BOLD)
        return win,wy,wx

    # Step 1: choose server type
    sel=0
    while True:
        h=len(_SRV_TYPES)+8; w=min(W-4,54)
        win,wy,wx=wwin('Server Wizard  Step 1/3: Choose Type',h,w)
        if win is None: return
        _safestr(win,2,3,'Select server to configure:',curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
        for i,(name,_) in enumerate(_SRV_TYPES):
            a=(curses.color_pair(CP_MENU_SEL)|curses.A_BOLD) if i==sel else curses.color_pair(CP_TEXT)
            _safestr(win,4+i,3,f'{">" if i==sel else " "} [{i+1:>2}] {name}'[:w-4],a)
        _safestr(win,h-1,2,' UP/DN=select  ENTER=next  ESC=cancel ',curses.color_pair(CP_STATUS))
        win.refresh(); key=stdscr.getch()
        if key==27: return
        elif key==curses.KEY_UP: sel=(sel-1)%len(_SRV_TYPES)
        elif key==curses.KEY_DOWN: sel=(sel+1)%len(_SRV_TYPES)
        elif key in(curses.KEY_ENTER,10,13): chosen_name,chosen_type=_SRV_TYPES[sel]; break

    # Step 2: configure fields
    raw=_SRV_FIELDS.get(chosen_type,[('Option','value')])
    fnames=[n for n,_ in raw]; fvals=[v for _,v in raw]
    cur_f=0; editing=False; edit_buf=''
    while True:
        h=len(raw)+10; w=min(W-4,58)
        win,wy,wx=wwin('Server Wizard  Step 2/3: Configure',h,w)
        if win is None: break
        _safestr(win,2,3,f'Configure: {chosen_name}'[:w-6],curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
        _safestr(win,3,3,'ENTER=edit field  F=finish  ESC=back',curses.color_pair(CP_SHADOW))
        for i,name in enumerate(fnames):
            val=edit_buf if(editing and i==cur_f) else fvals[i]
            cursor='_' if(editing and i==cur_f) else ''
            al=(curses.color_pair(CP_BRIGHT)|curses.A_BOLD) if i==cur_f else curses.color_pair(CP_TEXT)
            av=curses.color_pair(CP_INPUT) if(editing and i==cur_f) \
               else curses.color_pair(CP_MENU_SEL) if i==cur_f else curses.color_pair(CP_TEXT)
            lbl=f'  {name:<16}: '
            _safestr(win,5+i,2,lbl[:w-4],al)
            _safestr(win,5+i,2+len(lbl),(val+cursor)[:w-4-len(lbl)],av)
        _safestr(win,h-1,2,' ENTER=edit  F=finish  ESC=back ',curses.color_pair(CP_STATUS))
        win.refresh(); key=stdscr.getch()
        if editing:
            if key in(curses.KEY_ENTER,10,13,9):
                fvals[cur_f]=edit_buf; editing=False; cur_f=(cur_f+1)%len(raw)
            elif key==27: editing=False
            elif key in(curses.KEY_BACKSPACE,127,8): edit_buf=edit_buf[:-1]
            elif 32<=key<=126: edit_buf+=chr(key)
        else:
            if key==27: break
            elif key==curses.KEY_UP: cur_f=(cur_f-1)%len(raw)
            elif key in(curses.KEY_DOWN,9): cur_f=(cur_f+1)%len(raw)
            elif key in(curses.KEY_ENTER,10,13): editing=True; edit_buf=fvals[cur_f]
            elif key in(ord('f'),ord('F')): break

    config=dict(zip(fnames,fvals)); cmds=_gen_cmds(chosen_type,config)

    # Step 3: generated script
    scroll=0
    while True:
        max_vis=max(4,H-14); h=min(len(cmds)+10,H-4); w=min(W-4,72)
        win,wy,wx=wwin('Server Wizard  Step 3/3: Install Script',h,w)
        if win is None: break
        _safestr(win,2,3,f'Script: {chosen_name}'[:w-6],curses.color_pair(CP_BRIGHT)|curses.A_BOLD)
        vis=cmds[scroll:scroll+max_vis]
        for i,line in enumerate(vis):
            a=curses.color_pair(CP_SHADOW) if line.startswith('#') else curses.color_pair(CP_GREEN)
            _safestr(win,4+i,2,line[:w-4],a)
        _safestr(win,h-2,2,f' {scroll+1}-{scroll+len(vis)}/{len(cmds)} ',curses.color_pair(CP_SHADOW))
        _safestr(win,h-1,2,' S=save .sh  X=save+note  ESC=close ',curses.color_pair(CP_STATUS))
        win.refresh(); key=stdscr.getch()
        if key==27: break
        elif key==curses.KEY_UP: scroll=max(0,scroll-1)
        elif key==curses.KEY_DOWN: scroll=min(max(0,len(cmds)-max_vis),scroll+1)
        elif key in(ord('s'),ord('S'),ord('x'),ord('X')):
            fname=f'/tmp/cos_{chosen_type}_setup.sh'
            with open(fname,'w') as fh:
                fh.write('#!/bin/bash\n')
                fh.write(f'# COS Server Wizard: {chosen_name}\n\n')
                for c in cmds: fh.write(c+'\n')
            os.chmod(fname,0o755)
            state['messages'].append(f'[Wizard] Saved: {fname}')
            if key in(ord('x'),ord('X')): state['messages'].append(f'[Wizard] Run: bash {fname}')
            break

# =============================================================================
# ACTION HANDLER
# =============================================================================
def handle_action(action,stdscr,state):
    H,W=stdscr.getmaxyx()
    if action=='exit': state['running']=False
    elif action=='about':
        PopupWindow(stdscr,'About COS',[
            '  COS - Channel Operating System v2.0','  TTY-Native Desktop Shell',
            '','  Part of TCF (The Creative Force)','  Built for real TTYs with full mouse.',
            '','  SHELLS: COS, Batch, POS, COM, Retro',
            '  APPS:   Calc, File Browser, Terminal',
            '  WIZARD: Server Setup (10 server types)',
            '','  "The channel is always open."'],46).draw()
    elif action=='help':
        PopupWindow(stdscr,'Help',[
            '  KEYBOARD SHORTCUTS',
            '  F  File    E  Edit    A  Apps',
            '  C  Control S  Shells  P  Power',
            '  O  Other   Q/ESC  quit/close',
            '  F1  Help',
            '','  MOUSE',
            '  Click top bar  open menu',
            '  Click desktop  move cursor',
            '','  IN SHELLS',
            '  ESC  exit shell','  UP/DN  command history'],46).draw()
    elif action=='sysinfo':
        u=platform.uname(); now=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        PopupWindow(stdscr,'System Info',[
            f'  Node    : {u.node}',f'  OS      : {u.system} {u.release}',
            f'  Arch    : {u.machine}',f'  Python  : {platform.python_version()}',
            f'  TTY     : {os.ttyname(0) if os.isatty(0) else "n/a"}',
            f'  Size    : {W}x{H}',f'  User    : {os.environ.get("USER","?")}',
            f'  Time    : {now}'],50).draw()
    elif action=='processes':
        try:
            out=subprocess.check_output(['ps','aux','--no-headers'],text=True,timeout=4)
            lines=[f'  {l[:W-8]}' for l in out.strip().split('\n')[:min(25,H-10)]]
        except Exception as e: lines=[f'  Error: {e}']
        PopupWindow(stdscr,'Processes',lines,min(W-4,80)).draw()
    elif action=='disk':
        try:
            out=subprocess.check_output(['df','-h'],text=True,timeout=4)
            lines=[f'  {l}' for l in out.strip().split('\n')]
        except Exception as e: lines=[f'  Error: {e}']
        PopupWindow(stdscr,'Disk Usage',lines,min(W-4,72)).draw()
    elif action=='network':
        try:
            out=subprocess.check_output(['ip','addr'],text=True,timeout=4)
            lines=[f'  {l}' for l in out.strip().split('\n')[:25]]
        except:
            try:
                out=subprocess.check_output(['ifconfig'],text=True,timeout=4)
                lines=[f'  {l}' for l in out.strip().split('\n')[:25]]
            except Exception as e: lines=[f'  Error: {e}']
        PopupWindow(stdscr,'Network',lines,min(W-4,70)).draw()
    elif action=='clock':
        now=datetime.now()
        PopupWindow(stdscr,'COS Clock',[
            '',f'  {now.strftime("%A")}',f'  {now.strftime("%B %d, %Y")}',
            '',f'  {now.strftime("%H:%M:%S")}',''],36).draw()
    elif action=='copy':
        if state['messages']:
            text=state['messages'][-1]; ok=sys_copy(text)
            state['messages'].append(f'[COS] Copied: "{text[:40]}"'+(' (internal)' if not ok else ''))
        else: state['messages'].append('[COS] Nothing to copy.')
    elif action=='paste':
        text=sys_paste()
        if text: state['messages'].append(f'[COS] Pasted: {text[:60]}')
        else: state['messages'].append('[COS] Clipboard empty.')
    elif action=='clear': state['messages'].clear()
    elif action=='prefs': run_prefs(stdscr,state)
    elif action=='settings':
        u=platform.uname()
        PopupWindow(stdscr,'COS Settings',[
            '  SYSTEM',f'  Hostname : {u.node}',f'  User     : {os.environ.get("USER","?")}',
            f'  Shell    : {os.environ.get("SHELL","/bin/sh")}',
            f'  Terminal : {os.environ.get("TERM","?")}',
            f'  OS       : {u.system} {u.release}','',
            '  COS STATE',f'  Theme  : {state.get("theme_idx",0)+1}',
            f'  Clock  : {"ON" if state.get("pref_clock",True) else "OFF"}',
            f'  Mouse  : {"ON" if state.get("pref_mouse",True) else "OFF"}',
            f'  Dots   : {"ON" if state.get("pref_dots",True) else "OFF"}',
            '','  Press E > Preferences to change.'],min(W-4,52)).draw()
    elif action=='calc': run_calculator(stdscr)
    elif action=='filebrowser': run_filebrowser(stdscr)
    elif action=='open_term': run_terminal(stdscr,state)
    elif action=='new_session': state['messages'].append('[COS] New session spawned.')
    elif action=='save_log':
        fname='/tmp/cos_session.log'
        try:
            with open(fname,'w') as fh: fh.write('\n'.join(state['messages']))
            state['messages'].append(f'[COS] Log saved to {fname}')
        except Exception as e: state['messages'].append(f'[COS] Save failed: {e}')
    elif action=='shell_cos': COSShell(stdscr).run()
    elif action=='shell_batch': BatchShell(stdscr).run()
    elif action=='shell_pos': POSShell(stdscr).run()
    elif action=='shell_com': COMShell(stdscr).run()
    elif action=='shell_retro': RetroShell(stdscr).run()
    elif action=='server_wizard': run_server_wizard(stdscr,state)
    elif action=='keymap':
        PopupWindow(stdscr,'Key Map',[
            '  Q / ESC      quit menus / COS',
            '  F E A C S P O  open menu',
            '  Arrow keys   navigate menus/shells',
            '  Enter        select item',
            '  Mouse        click menus',
            '  F1           help','',
            '  Calculator:',
            '  0-9 . + - * /  type expression',
            '  Enter  evaluate  C  clear','',
            '  File Browser:',
            '  Enter  open dir  ESC  close'],46).draw()
    elif action=='credits':
        PopupWindow(stdscr,'Credits',[
            '','  COS - Channel Operating System v2.0',
            '  Built by TCF - The Creative Force','',
            '  Python + curses  //  TTY + Mouse','',
            '  "Retro Outside, Modern Inside."',''],44).draw()
    elif action in('reboot','shutdown','suspend'):
        PopupWindow(stdscr,f'Power: {action.title()}',[
            f'  System {action} requires root/systemd.',
            f'  Run from a normal shell:',
            f'  sudo systemctl {action}'],52).draw()
    elif action=='restart': state['messages'].append('[COS] Shell restarted.')

# =============================================================================
# DESKTOP + MAIN LOOP
# =============================================================================
LOGO=['  +=======================+',
      '  |  COS  .  v2.0  .  TCF |',
      '  +=======================+']

def draw_desktop(stdscr,H,W,state):
    fill='.' if state.get('pref_dots',True) else ' '
    stdscr.bkgd(fill,curses.color_pair(CP_DESKTOP)); stdscr.clear()
    ly=H//2-2
    for i,line in enumerate(LOGO):
        x=max(0,(W-len(line))//2)
        _safestr(stdscr,ly+i,x,line,curses.color_pair(CP_BRIGHT)|curses.A_BOLD)

def draw_menubar(stdscr,W):
    bar=' COS (Channel Operating System)  =  '
    col=len(bar); positions={}; segments=[]
    for k in MENU_ORDER:
        m=MENUS[k]; label=f' {m["label"]} [{m["key"]}] '
        positions[k]=col; segments.append((label,k)); col+=len(label)+3
    try:
        stdscr.addstr(0,0,' '*W,curses.color_pair(CP_MENUBAR))
        stdscr.addstr(0,0,bar,curses.color_pair(CP_MENUBAR)|curses.A_BOLD)
        cx=len(bar)
        for i,(label,k) in enumerate(segments):
            _safestr(stdscr,0,cx,label,curses.color_pair(CP_MENUBAR)|curses.A_BOLD)
            cx+=len(label)
            if i<len(segments)-1:
                _safestr(stdscr,0,cx,' = ',curses.color_pair(CP_MENUBAR)); cx+=3
    except curses.error: pass
    return positions

def draw_statusbar(stdscr,H,W,mouse_pos,state):
    now=datetime.now().strftime('%H:%M:%S') if state.get('pref_clock',True) else ''
    mx,my=mouse_pos
    coords=f'  ({mx:>3},{my:>3})' if state.get('pref_mouse',True) else ''
    left=f' COS v2.0{coords}  |  F/E/A/C/S/P/O = menus  Q = quit'
    right=f' {now} '
    pad=W-len(left)-len(right)
    try: stdscr.addstr(H-1,0,(left+' '*max(0,pad)+right)[:W],curses.color_pair(CP_STATUS)|curses.A_BOLD)
    except curses.error: pass

def draw_messages(stdscr,H,W,messages):
    shown=messages[-max(1,H-6):]
    for i,msg in enumerate(shown):
        y=H-2-len(shown)+i
        if 2<=y<H-1: _safestr(stdscr,y,2,str(msg)[:W-4],curses.color_pair(CP_TEXT)|curses.A_DIM)

def draw_cursor(stdscr,H,W,mx,my):
    if 1<my<H-1 and 0<=mx<W:
        _safestr(stdscr,my,mx,'+',curses.color_pair(CP_CURSOR)|curses.A_BOLD)

def main(stdscr):
    curses.cbreak(); curses.noecho(); stdscr.keypad(True); curses.curs_set(0)
    curses.mousemask(curses.ALL_MOUSE_EVENTS|curses.REPORT_MOUSE_POSITION)
    print('\033[?1003h',end='',flush=True)
    init_colors()
    state={'running':True,'messages':[
        '[COS] Channel Operating System v2.0 ready.',
        '[COS] Menus: F E A C S P O  |  Terminal: FILE > Open Terminal',
        '[COS] Shells: SHELLS menu  |  Server Wizard: POWER menu',
    ],'theme_idx':0,'pref_clock':True,'pref_mouse':True,'pref_dots':True}
    mouse_pos=(0,0); positions={}
    while state['running']:
        H,W=stdscr.getmaxyx()
        draw_desktop(stdscr,H,W,state)
        positions=draw_menubar(stdscr,W)
        draw_messages(stdscr,H,W,state['messages'])
        draw_statusbar(stdscr,H,W,mouse_pos,state)
        draw_cursor(stdscr,H,W,*mouse_pos)
        stdscr.refresh(); stdscr.timeout(300); key=stdscr.getch()
        if key==-1: continue
        if key in(ord('q'),27): state['running']=False; continue
        if key==curses.KEY_F1: handle_action('help',stdscr,state); continue
        if key==curses.KEY_RESIZE: curses.resizeterm(*stdscr.getmaxyx()); continue
        if 32<=key<=126:
            ch=chr(key).lower()
            if ch in MENUS:
                col=positions.get(ch,0)
                action=Dropdown(stdscr,ch,col).run()
                if action: handle_action(action,stdscr,state)
                continue
        if key==curses.KEY_MOUSE:
            try:
                _,mx,my,_,bstate=curses.getmouse(); mouse_pos=(mx,my)
                if my==0 and bstate&(curses.BUTTON1_PRESSED|curses.BUTTON1_CLICKED):
                    hit=None
                    for k,col in positions.items():
                        label=f' {MENUS[k]["label"]} [{MENUS[k]["key"]}] '
                        if col<=mx<col+len(label): hit=k; break
                    if hit:
                        action=Dropdown(stdscr,hit,positions[hit]).run()
                        if action: handle_action(action,stdscr,state)
            except curses.error: pass
    print('\033[?1003l',end='',flush=True)

def run():
    try: curses.wrapper(main)
    except KeyboardInterrupt: pass
    finally:
        print('\033[?1003l',end='',flush=True)
        print('\nCOS Channel closed.')

if __name__=='__main__': run()
