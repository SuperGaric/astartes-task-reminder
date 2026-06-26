#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌面任务提醒 + Titus Codex Pet
使用 Codex pet spritesheet — 无需额外处理
"""

import sys, json, os, traceback, math, random
from datetime import datetime, date
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QScrollArea, QCheckBox,
    QCalendarWidget, QMessageBox, QSystemTrayIcon, QMenu,
    QTimeEdit, QDateEdit
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QDate, QTime
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QBrush, QPen, QLinearGradient,
    QIcon, QPixmap, QPolygon, QTransform
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITESHEET = os.path.join(APP_DIR, "sprites", "titus.codex-pet", "spritesheet.webp")
DATA_FILE = os.path.join(APP_DIR, "tasks.json")
C = {"bg":"#1e1e2e","text":"#e0e0f5","text_secondary":"#b4b4c8","text_muted":"#787890",
     "success":"#78dc8c","danger":"#ff7878"}

# 精灵表精确帧格（从实际分析得出）
COLS = [(16,175),(208,367),(401,559),(598,745),(776,951),(971,1141),(1167,1325),(1366,1515)]
ROWS = [(5,202),(213,410),(421,618),(629,826),(837,1034),(1045,1242),(1253,1450),(1461,1658),(1669,1866)]
SCALE = 1.3

def load_tasks():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return []

def save_tasks(ts):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(ts, f, ensure_ascii=False, indent=2)
    except: pass

# ==================== Titus Pet ====================
class TitusPet(QWidget):
    ANIM_ROWS = {"idle": 0, "walk": 1, "alert": 2, "wave": 3, "happy": 5}
    FRAMES_PER_ROW = len(COLS)  # 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scale = SCALE
        # 取第一帧的尺寸作为基准
        fw = COLS[0][1] - COLS[0][0] + 1
        fh = ROWS[0][1] - ROWS[0][0] + 1
        self._fw, self._fh = fw, fh
        self.setFixedSize(int(fw*self._scale), int(fh*self._scale))
        self.setStyleSheet("background:transparent;")

        self._sheet = QPixmap(SPRITESHEET)
        if self._sheet.isNull():
            self._sheet = self._fallback()

        self._frame_idx = 0
        self._tick_count = 0
        self._state = "idle"
        self._state_timer = 0
        self._bob = 0
        self._bubble_text = ""
        self._bubble_timer = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)  # ~10fps

        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._random_act)
        self._idle_timer.start(5000)

    def _fallback(self):
        pm = QPixmap(FRAME_W*SCALE, FRAME_H*SCALE)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setBrush(QBrush(QColor(41,82,163)))
        p.setPen(QPen(Qt.white, 2))
        p.drawRect(4,4,pm.width()-8,pm.height()-8)
        p.drawText(pm.rect(), Qt.AlignCenter, "TITUS\nsprite missing")
        p.end()
        return pm

    def _get_frame(self):
        row = self.ANIM_ROWS.get(self._state, 0)
        col = self._frame_idx % self.FRAMES_PER_ROW
        x1, x2 = COLS[col]
        y1, y2 = ROWS[row]
        return self._sheet.copy(x1, y1, x2-x1+1, y2-y1+1)

    def _tick(self):
        self._tick_count += 1
        self._state_timer += 1

        # 帧切换 (idle慢，其他正常)
        speed = 8 if self._state == "idle" else 4
        if self._tick_count % speed == 0:
            self._frame_idx = (self._frame_idx + 1) % self.FRAMES_PER_ROW

        self._bob = math.sin(self._tick_count * 0.08) * 2

        if self._bubble_timer > 0:
            self._bubble_timer -= 1
            if self._bubble_timer <= 0:
                self._bubble_text = ""

        if self._state != "idle" and self._state_timer > 50:
            self._state = "idle"
            self._state_timer = 0

        self.update()

    def _random_act(self):
        if self._state != "idle": return
        r = random.random()
        if r < 0.15:
            self._state = "happy"; self._state_timer = 0; self._frame_idx = 0
            self._bubble_text = "For the\nEmperor!"
            self._bubble_timer = 60
        elif r < 0.3:
            self._state = "alert"; self._state_timer = 0; self._frame_idx = 0
            self._bubble_text = "Vigilance!"
            self._bubble_timer = 55
        elif r < 0.4:
            self._state = "wave"; self._state_timer = 0; self._frame_idx = 0
            self._bubble_text = "Brother!"
            self._bubble_timer = 50

    def on_click(self):
        self._state = "wave"; self._state_timer = 0; self._frame_idx = 0
        self._bubble_text = "The Emperor\nprotects!"
        self._bubble_timer = 65

    def on_add_task(self):
        self._state = "happy"; self._state_timer = 0; self._frame_idx = 0
        self._bubble_text = "New quest!"
        self._bubble_timer = 55

    def on_reminder(self):
        self._state = "alert"; self._state_timer = 0; self._frame_idx = 0
        self._bubble_text = "A task\nawaits!"
        self._bubble_timer = 70

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.on_click()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        frame = self._get_frame()
        scaled = frame.scaled(int(self._fw*self._scale), int(self._fh*self._scale), Qt.KeepAspectRatio, Qt.FastTransformation)
        px = (self.width()-scaled.width())//2
        py = (self.height()-scaled.height())//2 + int(self._bob)
        p.drawPixmap(px, py, scaled)

        # 阴影
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0,0,0,50)))
        p.drawEllipse(QPoint(self.width()//2, self.height()-6), 35, 4)

        if self._bubble_text:
            self._draw_bubble(p, px, py, scaled.width())

        p.end()

    def _draw_bubble(self, p, cx, cy, pw):
        text = self._bubble_text
        lines = text.split("\n")
        if not lines: return
        font = QFont("Microsoft YaHei", 8, QFont.Bold)
        p.setFont(font)
        fm = p.fontMetrics()
        max_w = max(fm.horizontalAdvance(line) for line in lines)
        lh = fm.height()
        bw, bh = max_w + 20, lh*len(lines) + 16
        bx = cx + pw + 4
        by = cy
        if bx + bw > self.width(): bx = cx - bw - 4
        if bx < 2: bx = 2

        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0,0,0,80)))
        p.drawRoundedRect(bx+2, by+2, bw, bh, 10, 10)
        p.setBrush(QBrush(QColor(40,42,60,250)))
        p.setPen(QPen(QColor(255,255,255,50), 1.5))
        p.drawRoundedRect(bx, by, bw, bh, 10, 10)

        # 尾巴
        tail_x = bx + 12 if bx < cx else bx + bw - 12
        tail = QPolygon([
            QPoint(tail_x, by+bh-2),
            QPoint(cx + pw//2, cy + 20),
            QPoint(tail_x+10, by+bh-2),
        ])
        p.setBrush(QBrush(QColor(40,42,60,250)))
        p.setPen(QPen(QColor(255,255,255,50), 1.5))
        p.drawPolygon(tail)

        p.setPen(QColor(255,255,255,235))
        ty = by + lh
        for line in lines:
            p.drawText(bx+10, ty, line)
            ty += lh

    def set_scale(self, s):
        self._scale = s
        self.setFixedSize(int(self._fw*s), int(self._fh*s))
        self.update()


# ==================== 弹窗 / 任务项 / 主窗口 ====================
class ReminderPopup(QWidget):
    def __init__(self, task):
        super().__init__(None, Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool)
        self.setFixedSize(360,170)
        lo=QVBoxLayout(self); lo.setContentsMargins(16,16,16,14); lo.setSpacing(8)
        t=QLabel("⏰ Time's Up, Brother!")
        t.setStyleSheet("color:#ffcc80;font-size:16px;font-weight:bold;background:transparent;")
        lo.addWidget(t)
        tt=task.get("time",""); txt=task.get("text","")
        c=QLabel(f"{txt}\nScheduled: {tt}")
        c.setWordWrap(True); c.setStyleSheet("color:#e0e0f5;font-size:13px;background:transparent;")
        lo.addWidget(c); lo.addStretch()
        bl=QHBoxLayout(); bl.setSpacing(8)
        sn=QPushButton("Snooze 5 min"); sn.setCursor(Qt.PointingHandCursor); sn.clicked.connect(self.close)
        sn.setStyleSheet("QPushButton{background:rgba(255,255,255,15);color:#b4b4c8;border:1px solid rgba(255,255,255,20);border-radius:6px;padding:6px 14px;font-size:11px;}QPushButton:hover{background:rgba(255,255,255,30);color:#e0e0f5;}")
        bl.addWidget(sn)
        dm=QPushButton("Dismiss"); dm.setCursor(Qt.PointingHandCursor); dm.clicked.connect(self.close)
        dm.setStyleSheet("QPushButton{background:rgba(130,160,255,100);color:#fff;border:none;border-radius:6px;padding:6px 18px;font-size:11px;font-weight:bold;}QPushButton:hover{background:rgba(130,160,255,180);}")
        bl.addWidget(dm); lo.addLayout(bl)
        self.move(QApplication.primaryScreen().geometry().width()-390,
                  QApplication.primaryScreen().geometry().height()-200)
        QTimer.singleShot(30000,self.close)
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(),QColor(30,30,50,240))
        p.setPen(QPen(QColor(255,200,130,80),2)); p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),12,12); p.end()
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton: self._d=e.globalPos()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self,e):
        if e.buttons()==Qt.LeftButton and hasattr(self,'_d'): self.move(e.globalPos()-self._d)

class TaskItem(QFrame):
    def __init__(self,task,on_toggle,on_delete,parent=None):
        super().__init__(parent)
        self.task=task; self._on_toggle=on_toggle; self._on_delete=on_delete
        self._hover=False; self.setFixedHeight(52); self.setMouseTracking(True)
    def enterEvent(self,e): self._hover=True; self.update()
    def leaveEvent(self,e): self._hover=False; self.update()
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:
            if e.pos().x()>self.width()-45: self._on_delete(self.task["id"])
            else: self._on_toggle(self.task["id"])
    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r=self.rect().adjusted(5,3,-5,-3); rd=8
        a=50 if self._hover else 20
        p.setBrush(QBrush(QColor(255,255,255,a)))
        p.setPen(QPen(QColor(255,255,255,18),1)); p.drawRoundedRect(r,rd,rd)
        cx,cy=r.left()+16,r.center().y()
        if self.task.get("completed"):
            p.setBrush(QBrush(QColor(C["success"]))); p.setPen(Qt.NoPen)
            p.drawEllipse(QPoint(cx,cy),7,7)
            p.setPen(QPen(Qt.white,2)); p.drawLine(cx-3,cy,cx-1,cy+3); p.drawLine(cx-1,cy+3,cx+4,cy-3)
        else:
            p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(150,150,170),2)); p.drawEllipse(QPoint(cx,cy),7,7)
        tc=QColor(150,150,170) if self.task.get("completed") else QColor(C["text"])
        p.setPen(tc); f=QFont("Microsoft YaHei",10)
        if self.task.get("completed"): f.setStrikeOut(True)
        p.setFont(f); txt=self.task.get("text","")
        el=p.fontMetrics().elidedText(txt,Qt.ElideRight,r.width()-80)
        p.drawText(r.adjusted(32,2,-44,-10),Qt.AlignVCenter|Qt.AlignLeft,el)
        td=self.task.get("date",""); tt=self.task.get("time","")
        if td:
            p.setPen(QColor(130,130,160)); p.setFont(QFont("Microsoft YaHei",8))
            dt=td
            if tt: dt+=f" {tt}"
            if self.task.get("completed"): dt+=" ✓"
            elif self._od(): dt+=" ⚠ overdue"; p.setPen(QColor(C["danger"]))
            p.drawText(r.adjusted(32,8,-44,0),Qt.AlignVCenter|Qt.AlignLeft,dt)
        dr=r.adjusted(r.width()-40,0,0,0)
        p.setPen(QColor(C["danger"]) if self._hover else QColor(100,100,130))
        p.setFont(QFont("Microsoft YaHei",11)); p.drawText(dr,Qt.AlignCenter,"✕"); p.end()
    def _od(self):
        d=self.task.get("date",""); t=self.task.get("time","")
        if not d: return False
        try:
            dt=d+(" "+t if t else""); f="%Y-%m-%d %H:%M" if t else"%Y-%m-%d"
            return datetime.now()>datetime.strptime(dt,f) and not self.task.get("completed")
        except: return False

class TitusApp(QWidget):
    def __init__(self):
        super().__init__()
        self.tasks=load_tasks(); self._drag_pos=None; self._cal_popup=None
        self._task_widgets={}; self._tray=None; self._popups=[]; self._filter_date=None
        self._init_ui(); self._init_tray(); self._refresh()
        self._chk=QTimer(); self._chk.timeout.connect(self._check); self._chk.start(30000)
        QTimer.singleShot(2000,self._check)

    def _init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self._base_w, self._base_h = 440, 650
        self._scale = 1.0
        self.resize(self._base_w, self._base_h)
        self.setMinimumSize(360, 520)
        self.setMaximumSize(700, 900)
        self.setWindowOpacity(0.93)
        self.setStyleSheet(f"background:{C['bg']};")
        lo=QVBoxLayout(self); lo.setContentsMargins(10,10,10,6); lo.setSpacing(4)
        tl=QHBoxLayout(); tl.setContentsMargins(6,2,6,2)
        title=QLabel("✦ Titus Reminder")
        title.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:bold;background:transparent;")
        tl.addWidget(title); tl.addStretch()
        self.date_btn=QPushButton(); self.date_btn.setFixedHeight(28); self.date_btn.setMinimumWidth(105)
        self.date_btn.setCursor(Qt.PointingHandCursor); self.date_btn.clicked.connect(self._toggle_cal); self._upd_date()
        tl.addWidget(self.date_btn)
        cb=QPushButton("✕"); cb.setFixedSize(24,24); cb.setCursor(Qt.PointingHandCursor)
        cb.clicked.connect(self._hide_tray)
        cb.setStyleSheet("QPushButton{background:rgba(255,100,100,40);color:#e0e0f5;border-radius:12px;font-size:11px;font-weight:bold;}QPushButton:hover{background:rgba(255,100,100,160);}")
        tl.addWidget(cb); lo.addLayout(tl)
        sep=QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:rgba(255,255,255,12);max-height:1px;"); lo.addWidget(sep)
        il=QHBoxLayout(); il.setContentsMargins(4,2,4,2); il.setSpacing(4)
        self.input=QLineEdit(); self.input.setPlaceholderText("Task for the Emperor...")
        self.input.setFixedHeight(32); self.input.returnPressed.connect(self._add)
        self.input.setStyleSheet("QLineEdit{background:rgba(255,255,255,15);color:#e0e0f5;border:1px solid rgba(255,255,255,20);border-radius:7px;padding:4px 10px;font-size:13px;}QLineEdit:focus{border-color:rgba(130,160,255,160);background:rgba(255,255,255,22);}")
        il.addWidget(self.input,1)
        add_btn=QPushButton("+ Add"); add_btn.setFixedSize(52,32)
        add_btn.setCursor(Qt.PointingHandCursor); add_btn.clicked.connect(self._add)
        add_btn.setStyleSheet("QPushButton{background:rgba(130,160,255,100);color:#fff;border:none;border-radius:7px;font-size:12px;font-weight:bold;}QPushButton:hover{background:rgba(130,160,255,180);}")
        il.addWidget(add_btn); lo.addLayout(il)
        dtl=QHBoxLayout(); dtl.setContentsMargins(4,0,4,0); dtl.setSpacing(6)
        dtl.addWidget(QLabel("Remind at:",styleSheet=f"color:{C['text_secondary']};font-size:11px;background:transparent;"))
        self.dedit=QDateEdit(QDate.currentDate()); self.dedit.setCalendarPopup(True); self.dedit.setDisplayFormat("yyyy-MM-dd"); self.dedit.setFixedHeight(28)
        self.dedit.setStyleSheet("QDateEdit{background:rgba(255,255,255,12);color:#d0d0f0;border:1px solid rgba(255,255,255,18);border-radius:5px;padding:2px 6px;font-size:11px;}")
        dtl.addWidget(self.dedit)
        self.tedit=QTimeEdit(QTime.currentTime()); self.tedit.setDisplayFormat("HH:mm"); self.tedit.setFixedHeight(28); self.tedit.setFixedWidth(60)
        self.tedit.setStyleSheet("QTimeEdit{background:rgba(255,255,255,12);color:#d0d0f0;border:1px solid rgba(255,255,255,18);border-radius:5px;padding:2px 6px;font-size:11px;}")
        dtl.addWidget(self.tedit); dtl.addStretch(); lo.addLayout(dtl)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(130)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}QScrollBar:vertical{background:rgba(0,0,0,20);width:4px;border-radius:2px;}QScrollBar::handle:vertical{background:rgba(255,255,255,25);border-radius:2px;min-height:20px;}QScrollBar::handle:vertical:hover{background:rgba(255,255,255,50);}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        self.task_list=QWidget(); self.task_list.setStyleSheet("background:transparent;")
        self.task_layout=QVBoxLayout(self.task_list); self.task_layout.setContentsMargins(0,0,0,0); self.task_layout.setSpacing(2)
        self.task_layout.addStretch(); scroll.setWidget(self.task_list); lo.addWidget(scroll)
        # Titus 宠物
        self._pet_frame=pf=QFrame(); pf.setFixedHeight(int(ROWS[0][1]-ROWS[0][0]+1)*SCALE+50); pf.setStyleSheet("background:transparent;border:none;")
        pfl=QHBoxLayout(pf); pfl.setContentsMargins(0,0,0,0); pfl.addStretch()
        self.pet=TitusPet(); pfl.addWidget(self.pet); pfl.addStretch(); lo.addWidget(pf)
        # 底部
        fl=QHBoxLayout(); fl.setContentsMargins(6,2,6,2)
        self.st=QLabel(); self.st.setStyleSheet(f"color:{C['text_muted']};font-size:10px;background:transparent;"); fl.addWidget(self.st)
        auto=QCheckBox("Auto-start"); auto.setChecked(self._is_autostart()); auto.toggled.connect(self._toggle_autostart)
        auto.setStyleSheet(f"QCheckBox{{color:{C['text_muted']};font-size:9px;background:transparent;spacing:3px;}}"); fl.addWidget(auto)
        fl.addStretch()
        for d,t in [(-1,"−"),(1,"+")]:
            b=QPushButton(t); b.setFixedSize(18,18); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _,dd=d: self._zoom(dd))
            b.setStyleSheet("QPushButton{background:rgba(255,255,255,10);color:#999;border:1px solid rgba(255,255,255,15);border-radius:3px;font-size:10px;}QPushButton:hover{background:rgba(255,255,255,25);color:#ccc;}")
            fl.addWidget(b)
        clr=QPushButton("Clear done"); clr.setCursor(Qt.PointingHandCursor); clr.clicked.connect(self._clear_done)
        clr.setStyleSheet("QPushButton{background:transparent;color:rgba(180,180,200,130);border:1px solid rgba(255,255,255,12);border-radius:5px;padding:2px 7px;font-size:10px;}QPushButton:hover{background:rgba(255,100,100,30);color:#ff7878;}")
        fl.addWidget(clr); lo.addLayout(fl)

    def _init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
        self._tray=QSystemTrayIcon(self)
        pm=QPixmap(32,32); pm.fill(Qt.transparent)
        p=QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(41,82,163))); p.setPen(QPen(QColor(20,40,80),1.5))
        p.drawEllipse(2,2,28,28)
        p.setPen(QPen(Qt.white,2.5)); p.drawArc(10,12,12,12,0,180*16); p.drawLine(10,15,10,22); p.drawLine(22,15,22,22); p.end()
        self._tray.setIcon(QIcon(pm)); self._tray.setToolTip("Titus Reminder")
        menu=QMenu(); menu.addAction("Show",self._show_tray)
        a=menu.addAction("Auto-start"); a.setCheckable(True); a.setChecked(self._is_autostart()); a.triggered.connect(self._toggle_autostart)
        menu.addSeparator(); menu.addAction("Quit",self._quit); self._tray.setContextMenu(menu)
        self._tray.activated.connect(lambda r:self._show_tray() if r==QSystemTrayIcon.DoubleClick else None)
        self._tray.show()

    def _hide_tray(self):
        if self._tray: self.hide()
        else: self.close()
    def _show_tray(self): self.show(); self.raise_(); self.activateWindow()
    def _quit(self): self._tray.hide() if self._tray else None; QApplication.quit()

    def _startup_path(self):
        return os.path.join(os.getenv("APPDATA",""),r"Microsoft\Windows\Start Menu\Programs\Startup","TitusReminder.lnk")
    def _is_autostart(self): return os.path.exists(self._startup_path())
    def _toggle_autostart(self, checked):
        from win32com.client import Dispatch
        sp=self._startup_path()
        if checked:
            try:
                sh=Dispatch("WScript.Shell"); sc=sh.CreateShortcut(sp)
                sc.TargetPath="D:\\python\\pythonw.exe"; sc.Arguments=os.path.join(APP_DIR,"titus_pet.py")
                sc.WorkingDirectory=APP_DIR; sc.Description="Titus Reminder"; sc.Save()
            except: pass
        else:
            if os.path.exists(sp):
                try: os.remove(sp)
                except: pass

    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(),QColor(30,30,42,245))
        g=QLinearGradient(0,0,self.width(),0)
        g.setColorAt(0,QColor(130,160,255,0)); g.setColorAt(0.3,QColor(130,160,255,70))
        g.setColorAt(0.7,QColor(180,130,255,70)); g.setColorAt(1,QColor(180,130,255,0))
        p.setPen(QPen(g,2)); p.drawLine(16,2,self.width()-16,2)
        # 缩放手柄
        p.setPen(QPen(QColor(255,255,255,25),1.5))
        for i in range(3): x=self.width()-14+i*5; y=self.height()-3; p.drawLine(x,y,x+3,y-3)
        p.end()

    def _in_rz(self, pos): return pos.x()>self.width()-28 and pos.y()>self.height()-28
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:
            if self._in_rz(e.pos()): self._rz=True; self._rz_s=e.globalPos(); self._rz_g=self.geometry()
            else: self._drag_pos=e.globalPos()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self,e):
        if e.buttons()==Qt.LeftButton:
            if hasattr(self,'_rz') and self._rz:
                d=e.globalPos()-self._rz_s
                nw=max(self.minimumWidth(),min(self.maximumWidth(),self._rz_g.width()+d.x()))
                nh=max(self.minimumHeight(),min(self.maximumHeight(),self._rz_g.height()+d.y()))
                self.resize(nw,nh); self._update_scale()
            elif self._drag_pos: self.move(e.globalPos()-self._drag_pos)
        else:
            self.setCursor(Qt.SizeFDiagCursor if self._in_rz(e.pos()) else Qt.ArrowCursor)
    def mouseReleaseEvent(self,e): self._drag_pos=None; self._rz=False
    def wheelEvent(self,e):
        if e.modifiers()&Qt.ControlModifier:
            d=1 if e.angleDelta().y()>0 else -1
            self.resize(max(self.minimumWidth(),min(self.maximumWidth(),self.width()+d*30)),
                        max(self.minimumHeight(),min(self.maximumHeight(),self.height()+d*36)))
            self._update_scale()
        else: super().wheelEvent(e)

    def _update_scale(self):
        s = self.width()/self._base_w
        self.pet.set_scale(SCALE*s)
        self._pet_frame.setFixedHeight(int(self.pet._fh*SCALE*s)+50)
        f = QFont("Microsoft YaHei", max(7,int(10*s)))
        QApplication.instance().setFont(f)

    def _zoom(self, d):
        self.resize(max(self.minimumWidth(),min(self.maximumWidth(),self.width()+d*35)),
                    max(self.minimumHeight(),min(self.maximumHeight(),self.height()+d*42)))
        self._update_scale()

    def _upd_date(self):
        today=date.today(); wd=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][today.weekday()]
        self.date_btn.setText(f"📅 {today.month}/{today.day} {wd}")
        self.date_btn.setStyleSheet(f"QPushButton{{background:rgba(255,255,255,12);color:{C['text_secondary']};border:1px solid rgba(255,255,255,18);border-radius:7px;padding:3px 10px;font-size:11px;}}QPushButton:hover{{background:rgba(255,255,255,30);color:{C['text']};}}")

    def _toggle_cal(self):
        if self._cal_popup and self._cal_popup.isVisible(): self._cal_popup.close(); return
        self._cal_popup=QWidget(None,Qt.Popup|Qt.FramelessWindowHint)
        self._cal_popup.setFixedSize(310,340); self._cal_popup.setStyleSheet("background:#28283a;border-radius:10px;")
        cl=QVBoxLayout(self._cal_popup); cl.setContentsMargins(6,6,6,6)
        cal=QCalendarWidget(); cal.setGridVisible(False); cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        cal.setStyleSheet("QCalendarWidget{background:#28283a;border-radius:8px;padding:4px;color:#d0d0f0;}QCalendarWidget QToolButton{color:#d0d0f0;background:rgba(255,255,255,15);border-radius:5px;padding:4px 10px;font-weight:bold;}QCalendarWidget QToolButton:hover{background:rgba(255,255,255,30);}QCalendarWidget QAbstractItemView:enabled{color:#d0d0f0;selection-background-color:rgba(130,160,255,80);selection-color:#fff;}")
        cal.clicked.connect(lambda d:(self.dedit.setDate(d),setattr(self,'_filter_date',d.toString("yyyy-MM-dd")),QTimer.singleShot(100,self._cal_popup.close),self._refresh()))
        cl.addWidget(cal)
        btn=QPushButton("Today"); btn.setCursor(Qt.PointingHandCursor); btn.clicked.connect(lambda:cal.setSelectedDate(QDate.currentDate()))
        btn.setStyleSheet("QPushButton{background:rgba(130,160,255,50);color:#d0d0f0;border:none;border-radius:6px;padding:6px;}QPushButton:hover{background:rgba(130,160,255,120);}")
        cl.addWidget(btn)
        self._cal_popup.move(self.date_btn.mapToGlobal(self.date_btn.rect().bottomLeft())-QPoint(90,-4)); self._cal_popup.show()

    def _add(self):
        txt=self.input.text().strip()
        if not txt: return
        task={"id":datetime.now().strftime("%Y%m%d%H%M%S%f"),"text":txt,"completed":False,"created_at":datetime.now().isoformat(),"date":self.dedit.date().toString("yyyy-MM-dd"),"time":self.tedit.time().toString("HH:mm"),"reminded":False}
        self.tasks.append(task); save_tasks(self.tasks); self.input.clear(); self._refresh(); self.pet.on_add_task()

    def _toggle(self,tid):
        for t in self.tasks:
            if t["id"]==tid: t["completed"]=not t.get("completed",False); break
        save_tasks(self.tasks); self._refresh()
    def _delete(self,tid): self.tasks=[t for t in self.tasks if t["id"]!=tid]; save_tasks(self.tasks); self._refresh()
    def _clear_done(self): self.tasks=[t for t in self.tasks if not t.get("completed")]; save_tasks(self.tasks); self._refresh()

    def _refresh(self):
        for w in self._task_widgets.values(): self.task_layout.removeWidget(w); w.deleteLater()
        self._task_widgets.clear()
        self.tasks.sort(key=lambda t:(t.get("date",""),t.get("time",""),t.get("id","")))
        visible=[t for t in self.tasks if not self._filter_date or t.get("date","")>=self._filter_date] if hasattr(self,'_filter_date') else self.tasks
        for t in visible:
            item=TaskItem(t,self._toggle,self._delete)
            self.task_layout.insertWidget(self.task_layout.count()-1,item)
            self._task_widgets[t["id"]]=item
        total=len(self.tasks); shown=len(visible); done=sum(1 for t in visible if t.get("completed"))
        over=sum(1 for t in visible if self._od(t))
        parts=[]
        if self._filter_date: parts.append(f"📅 {self._filter_date}")
        parts+=[f"{shown}/{total} tasks",f"{shown-done} active",f"{done} done"]
        if over: parts.append(f"{over} overdue")
        self.st.setText("  |  ".join(parts))

    def _od(self,task):
        if task.get("completed"): return False
        d=task.get("date","")
        if not d: return False
        try:
            tm=task.get("time",""); dt=d+(" "+tm if tm else""); f="%Y-%m-%d %H:%M" if tm else"%Y-%m-%d"
            return datetime.now()>datetime.strptime(dt,f)
        except: return False

    def _check(self):
        now=datetime.now()
        for task in self.tasks:
            if task.get("completed") or task.get("reminded"): continue
            d=task.get("date",""); t=task.get("time","")
            if not d: continue
            try:
                dt=d+(" "+t if t else""); f="%Y-%m-%d %H:%M" if t else"%Y-%m-%d"
                if abs((now-datetime.strptime(dt,f)).total_seconds())<=60:
                    self._fire(task); task["reminded"]=True; save_tasks(self.tasks)
            except: pass

    def _fire(self,task):
        if self._tray and QSystemTrayIcon.supportsMessages():
            self._tray.showMessage("⏰ Task Reminder",f"[{task.get('time','')}] {task.get('text','')}",QSystemTrayIcon.Information,5000)
        popup=ReminderPopup(task); popup.show(); self._popups.append(popup)
        self._popups=[p for p in self._popups if p.isVisible()]; self.pet.on_reminder()

    def closeEvent(self,e):
        if self._tray and self._tray.isVisible(): self.hide(); e.ignore()
        else: QApplication.quit()

def main():
    try:
        app=QApplication(sys.argv); app.setQuitOnLastWindowClosed(False); app.setFont(QFont("Microsoft YaHei",10))
        w=TitusApp(); w.move(app.primaryScreen().geometry().width()-490,30); w.show()
        sys.exit(app.exec_())
    except Exception:
        with open(os.path.join(APP_DIR,"error.log"),"w",encoding="utf-8") as f: f.write(traceback.format_exc())
        try: QMessageBox.critical(None,"Error",traceback.format_exc())
        except: pass; sys.exit(1)

if __name__=="__main__": main()
