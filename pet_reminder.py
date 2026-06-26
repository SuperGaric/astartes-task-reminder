#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
桌面任务提醒 + 阿斯塔特修士宠物 v3
PNG精灵动画 · 对话气泡 · 日历筛选 · 弹窗提醒
"""

import sys, json, os, traceback, math, random
from datetime import datetime, date
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QScrollArea,
    QCalendarWidget, QMessageBox, QSystemTrayIcon, QMenu,
    QTimeEdit, QDateEdit
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QDate, QTime
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QBrush, QPen, QLinearGradient,
    QIcon, QPixmap, QPolygon, QTransform
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITE_DIR = os.path.join(APP_DIR, "sprites")
DATA_FILE = os.path.join(APP_DIR, "tasks.json")

def load_tasks():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return []

def save_tasks(tasks):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
    except: pass

C = {"bg":"#1e1e2e","text":"#e0e0f5","text_secondary":"#b4b4c8","text_muted":"#787890",
     "success":"#78dc8c","danger":"#ff7878"}

# ==================== 阿斯塔特修士 (PNG精灵版) ====================
class AstartesPet(QWidget):
    """使用PNG精灵图的阿斯塔特修士"""
    W, H = 350, 280  # 宠物组件尺寸

    # 状态对应的帧文件
    STATE_FRAMES = {
        "idle":  "idle.png",
        "wave":  "wave.png",
        "alert": "alert.png",
        "happy": "happy.png",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scale = 1.0
        self.setFixedSize(int(self.W*self._scale), int(self.H*self._scale))
        self.setStyleSheet("background:transparent;")

        # 加载精灵帧 (缩放到合适大小)
        self._frames = {}
        self._frames_raw = {}  # 原始图片
        target_h = 200  # 目标高度
        for state, fname in self.STATE_FRAMES.items():
            path = os.path.join(SPRITE_DIR, fname)
            if os.path.exists(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    self._frames_raw[state] = pix
                    scaled = pix.scaledToHeight(target_h, Qt.FastTransformation)
                    self._frames[state] = scaled

        # 如果没有加载到图片，用备用帧
        if not self._frames:
            self._frames["idle"] = self._fallback_pixmap()

        self._state = "idle"
        self._state_frame = 0
        self._frame = 0
        self._bob = 0
        self._shake = 0
        self._bubble_text = ""
        self._bubble_timer = 0

        # 动画定时器 ~15fps
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(65)

        # 随机动作
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._random_act)
        self._idle_timer.start(4000)

    def _fallback_pixmap(self):
        """创建一个备用占位图"""
        pm = QPixmap(200, 200)
        pm.fill(Qt.transparent)
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(41,82,163))); p.setPen(QPen(QColor(20,30,60),3))
        p.drawRoundedRect(10,10,180,180,20,20)
        p.setPen(QPen(Qt.white,2))
        p.drawText(pm.rect(), Qt.AlignCenter, "ASTARTES\nFrame missing")
        p.end()
        return pm

    def set_scale(self, s):
        """缩放精灵"""
        self._scale = s
        th = int(200 * s)
        for state, raw in self._frames_raw.items():
            self._frames[state] = raw.scaledToHeight(th, Qt.FastTransformation)
        self.setFixedSize(int(self.W*s), int(self.H*s))
        self.update()

    def _tick(self):
        self._frame += 1
        self._state_frame += 1
        t = self._frame

        # 呼吸浮动
        self._bob = math.sin(t * 0.1) * 4

        # 抖动衰减
        self._shake *= 0.85

        # 气泡计时
        if self._bubble_timer > 0:
            self._bubble_timer -= 1
            if self._bubble_timer <= 0:
                self._bubble_text = ""

        # 状态恢复
        if self._state in ("happy","alert","wave") and self._state_frame > 40:
            self._state = "idle"
            self._state_frame = 0

        self.update()

    def _random_act(self):
        if self._state != "idle": return
        r = random.random()
        if r < 0.2:
            self._state = "happy"; self._state_frame = 0
            self._bubble_text = "For the\nEmperor!"
            self._bubble_timer = 55
        elif r < 0.4:
            self._state = "alert"; self._state_frame = 0
            self._bubble_text = "Vigilance!"
            self._bubble_timer = 50
        elif r < 0.5:
            self._state = "wave"; self._state_frame = 0
            self._bubble_text = "Brother!"
            self._bubble_timer = 45

    def on_click(self):
        self._state = "wave"; self._state_frame = 0
        self._bubble_text = "The Emperor\nprotects!"
        self._bubble_timer = 60

    def on_add_task(self):
        self._state = "happy"; self._state_frame = 0
        self._shake = 8
        self._bubble_text = "A new quest!"
        self._bubble_timer = 55

    def on_reminder(self):
        self._state = "alert"; self._state_frame = 0
        self._bubble_text = "Brother!\nA task awaits!"
        self._bubble_timer = 65

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.on_click()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # 获取当前帧
        pix = self._frames.get(self._state)
        if pix is None:
            pix = self._frames.get("idle")
        if pix is None:
            return

        pw, ph = pix.width(), pix.height()
        # 底部居中 + 浮动偏移 + 抖动
        base_x = (self.W - pw) // 2 + int(self._shake * math.sin(self._frame * 2))
        base_y = self.H - ph - 10 + int(self._bob)

        # 警戒/开心时小幅缩放
        scale = 1.0
        if self._state == "alert":
            scale = 1.0 + math.sin(self._frame * 0.3) * 0.03
        elif self._state == "happy":
            scale = 1.0 + abs(math.sin(self._frame * 0.4)) * 0.05

        if scale != 1.0:
            t = QTransform()
            t.translate(base_x + pw/2, base_y + ph/2)
            t.scale(scale, scale)
            t.translate(-(base_x + pw/2), -(base_y + ph/2))
            p.setTransform(t)

        p.drawPixmap(base_x, base_y, pix)
        p.resetTransform()

        # 底部阴影
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0,0,0,50)))
        shadow_w = int(pw * 0.6)
        p.drawEllipse(QPoint(self.W//2, self.H-6), shadow_w//2, 5)

        # 对话气泡
        if self._bubble_text:
            self._draw_bubble(p, base_x, base_y, pw)

        p.end()

    def _draw_bubble(self, p, cx, cy, pw):
        """漫画风格对话气泡"""
        text = self._bubble_text
        lines = text.split("\n")
        if not lines: return

        font = QFont("Microsoft YaHei", 7, QFont.Bold)
        p.setFont(font)
        fm = p.fontMetrics()
        max_w = max(fm.horizontalAdvance(line) for line in lines)
        lh = fm.height()
        bw = max_w + 24
        bh = lh * len(lines) + 20

        # 气泡位置：固定在精灵左侧（空间更大更可靠）
        bx = cx - bw - 8
        if bx < 4: bx = 4  # 贴左边界
        by = cy - 15

        # 阴影
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0,0,0,70)))
        p.drawRoundedRect(bx+2, by+2, bw, bh, 12, 12)

        # 主体
        p.setBrush(QBrush(QColor(40,42,58,248)))
        p.setPen(QPen(QColor(255,255,255,50), 1.5))
        p.drawRoundedRect(bx, by, bw, bh, 12, 12)

        # 尾巴（指向右侧的精灵）
        tail = QPolygon([
            QPoint(bx + bw - 4, by + bh - 2),
            QPoint(cx + pw//2, cy + 15),
            QPoint(bx + bw + 8, by + bh - 2),
        ])
        p.setBrush(QBrush(QColor(40,42,58,248)))
        p.setPen(QPen(QColor(255,255,255,50), 1.5))
        p.drawPolygon(tail)

        # 文字
        p.setPen(QColor(255,255,255,235))
        ty = by + lh
        for line in lines:
            p.drawText(bx + 12, ty, line)
            ty += lh


# ==================== 提醒弹窗 ====================
class ReminderPopup(QWidget):
    def __init__(self, task, parent=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setFixedSize(360, 170)
        layout = QVBoxLayout(self); layout.setContentsMargins(16,16,16,14); layout.setSpacing(8)
        title = QLabel("⏰ Time's Up, Brother!")
        title.setStyleSheet("color:#ffcc80;font-size:16px;font-weight:bold;background:transparent;")
        layout.addWidget(title)
        tt = task.get("time",""); txt = task.get("text","")
        content = QLabel(f"{txt}\nScheduled: {tt}")
        content.setWordWrap(True)
        content.setStyleSheet("color:#e0e0f5;font-size:13px;background:transparent;")
        layout.addWidget(content)
        layout.addStretch()
        bl = QHBoxLayout(); bl.setSpacing(8)
        snooze = QPushButton("Snooze 5 min"); snooze.setCursor(Qt.PointingHandCursor)
        snooze.clicked.connect(self.close)
        snooze.setStyleSheet("QPushButton{background:rgba(255,255,255,15);color:#b4b4c8;border:1px solid rgba(255,255,255,20);border-radius:6px;padding:6px 14px;font-size:11px;}QPushButton:hover{background:rgba(255,255,255,30);color:#e0e0f5;}")
        bl.addWidget(snooze)
        dismiss = QPushButton("Dismiss"); dismiss.setCursor(Qt.PointingHandCursor)
        dismiss.clicked.connect(self.close)
        dismiss.setStyleSheet("QPushButton{background:rgba(130,160,255,100);color:#fff;border:none;border-radius:6px;padding:6px 18px;font-size:11px;font-weight:bold;}QPushButton:hover{background:rgba(130,160,255,180);}")
        bl.addWidget(dismiss)
        layout.addLayout(bl)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width()-390, screen.height()-200)
        QTimer.singleShot(30000, self.close)
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = self.rect(); p.fillRect(r, QColor(30,30,50,240))
        p.setPen(QPen(QColor(255,200,130,80),2)); p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(1,1,-1,-1),12,12); p.end()
    def mousePressEvent(self, e):
        if e.button()==Qt.LeftButton: self._d=e.globalPos()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if e.buttons()==Qt.LeftButton and hasattr(self,'_d'): self.move(e.globalPos()-self._d)


# ==================== 任务项 ====================
class TaskItem(QFrame):
    def __init__(self, task, on_toggle, on_delete, parent=None):
        super().__init__(parent)
        self.task=task; self._on_toggle=on_toggle; self._on_delete=on_delete
        self._hover=False; self.setFixedHeight(54); self.setMouseTracking(True)
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
            if tt: dt+=f"  {tt}"
            if self.task.get("completed"): dt+="  ✓"
            elif self._od(): dt+="  ⚠ overdue"; p.setPen(QColor(C["danger"]))
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


# ==================== 主窗口 ====================
class PetReminderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.tasks=load_tasks(); self._drag_pos=None; self._cal_popup=None
        self._task_widgets={}; self._tray=None; self._popups=[]
        self._filter_date=None
        self._init_ui(); self._init_tray(); self._refresh()
        self._chk=QTimer(); self._chk.timeout.connect(self._check_reminders)
        self._chk.start(30000); QTimer.singleShot(2000,self._check_reminders)

    def _init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self._base_w, self._base_h = 560, 680
        self._scale = 1.0
        self.resize(self._base_w, self._base_h)
        self.setMinimumSize(420, 520)
        self.setMaximumSize(800, 980)
        self.setWindowOpacity(0.93)
        self.setStyleSheet(f"background:{C['bg']};")
        lo=QVBoxLayout(self); lo.setContentsMargins(10,10,10,6); lo.setSpacing(4)

        # 标题栏
        tl=QHBoxLayout(); tl.setContentsMargins(6,2,6,2)
        title=QLabel("✦ Astartes Reminder")
        title.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:bold;background:transparent;")
        tl.addWidget(title); tl.addStretch()
        self.date_btn=QPushButton(); self.date_btn.setFixedHeight(28)
        self.date_btn.setMinimumWidth(105); self.date_btn.setCursor(Qt.PointingHandCursor)
        self.date_btn.clicked.connect(self._toggle_cal); self._upd_date()
        tl.addWidget(self.date_btn)
        cb=QPushButton("✕"); cb.setFixedSize(24,24); cb.setCursor(Qt.PointingHandCursor)
        cb.clicked.connect(self._hide_tray)
        cb.setStyleSheet("QPushButton{background:rgba(255,100,100,40);color:#e0e0f5;border-radius:12px;font-size:11px;font-weight:bold;}QPushButton:hover{background:rgba(255,100,100,160);}")
        tl.addWidget(cb); lo.addLayout(tl)

        sep=QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:rgba(255,255,255,12);max-height:1px;"); lo.addWidget(sep)

        # 输入区
        il=QHBoxLayout(); il.setContentsMargins(4,2,4,2); il.setSpacing(4)
        self.input=QLineEdit(); self.input.setPlaceholderText("Task for the Emperor...")
        self.input.setFixedHeight(32); self.input.returnPressed.connect(self._add)
        self.input.setStyleSheet("QLineEdit{background:rgba(255,255,255,15);color:#e0e0f5;border:1px solid rgba(255,255,255,20);border-radius:7px;padding:4px 10px;font-size:13px;}QLineEdit:focus{border-color:rgba(130,160,255,160);background:rgba(255,255,255,22);}")
        il.addWidget(self.input,1)
        add_btn=QPushButton("+ Add"); add_btn.setFixedSize(52,32)
        add_btn.setCursor(Qt.PointingHandCursor); add_btn.clicked.connect(self._add)
        add_btn.setStyleSheet("QPushButton{background:rgba(130,160,255,100);color:#fff;border:none;border-radius:7px;font-size:12px;font-weight:bold;}QPushButton:hover{background:rgba(130,160,255,180);}QPushButton:pressed{background:rgba(100,130,220,200);}")
        il.addWidget(add_btn); lo.addLayout(il)

        # 日期时间
        dtl=QHBoxLayout(); dtl.setContentsMargins(4,0,4,0); dtl.setSpacing(6)
        dt_label=QLabel("Remind at:")
        dt_label.setStyleSheet(f"color:{C['text_secondary']};font-size:11px;background:transparent;")
        dtl.addWidget(dt_label)
        self.dedit=QDateEdit(QDate.currentDate())
        self.dedit.setCalendarPopup(True); self.dedit.setDisplayFormat("yyyy-MM-dd")
        self.dedit.setFixedHeight(28)
        self.dedit.setStyleSheet("QDateEdit{background:rgba(255,255,255,12);color:#d0d0f0;border:1px solid rgba(255,255,255,18);border-radius:5px;padding:2px 6px;font-size:11px;}QDateEdit:hover{background:rgba(255,255,255,20);}")
        dtl.addWidget(self.dedit)
        self.tedit=QTimeEdit(QTime.currentTime())
        self.tedit.setDisplayFormat("HH:mm"); self.tedit.setFixedHeight(28); self.tedit.setFixedWidth(60)
        self.tedit.setStyleSheet("QTimeEdit{background:rgba(255,255,255,12);color:#d0d0f0;border:1px solid rgba(255,255,255,18);border-radius:5px;padding:2px 6px;font-size:11px;}")
        dtl.addWidget(self.tedit); dtl.addStretch(); lo.addLayout(dtl)

        # 任务列表
        self._scroll=scroll=QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(140)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}QScrollBar:vertical{background:rgba(0,0,0,20);width:4px;border-radius:2px;}QScrollBar::handle:vertical{background:rgba(255,255,255,25);border-radius:2px;min-height:20px;}QScrollBar::handle:vertical:hover{background:rgba(255,255,255,50);}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        self.task_list=QWidget(); self.task_list.setStyleSheet("background:transparent;")
        self.task_layout=QVBoxLayout(self.task_list)
        self.task_layout.setContentsMargins(0,0,0,0); self.task_layout.setSpacing(2)
        self.task_layout.addStretch()
        scroll.setWidget(self.task_list); lo.addWidget(scroll)

        # ---- 宠物区域 ----
        self._pet_frame=pet_frame=QFrame(); pet_frame.setFixedHeight(300)
        pet_frame.setStyleSheet("background:transparent;border:none;")
        pfl=QHBoxLayout(pet_frame); pfl.setContentsMargins(0,0,0,0)
        pfl.addStretch(); self.pet=AstartesPet(); pfl.addWidget(self.pet); pfl.addStretch()
        lo.addWidget(pet_frame)

        # 底部栏
        fl=QHBoxLayout(); fl.setContentsMargins(6,2,6,2)
        self.st=QLabel(); self.st.setStyleSheet(f"color:{C['text_muted']};font-size:10px;background:transparent;")
        fl.addWidget(self.st)
        self._cf_btn=QPushButton("✕ filter"); self._cf_btn.setCursor(Qt.PointingHandCursor)
        self._cf_btn.clicked.connect(self._clear_filter)
        self._cf_btn.setStyleSheet("QPushButton{background:rgba(130,160,255,50);color:#a0c0ff;border:1px solid rgba(130,160,255,80);border-radius:4px;padding:2px 6px;font-size:9px;}QPushButton:hover{background:rgba(130,160,255,120);color:#fff;}")
        self._cf_btn.hide(); fl.addWidget(self._cf_btn)
        fl.addStretch()
        # 自启
        from PyQt5.QtWidgets import QCheckBox
        self._auto_cb = QCheckBox("Auto-start")
        self._auto_cb.setChecked(self._is_autostart())
        self._auto_cb.toggled.connect(self._toggle_autostart)
        self._auto_cb.setStyleSheet(f"QCheckBox{{color:{C['text_muted']};font-size:9px;background:transparent;spacing:3px;}}QCheckBox::indicator{{width:12px;height:12px;}}")
        fl.addWidget(self._auto_cb)
        # 缩放按钮
        sm = QPushButton("−"); sm.setFixedSize(18,18); sm.setCursor(Qt.PointingHandCursor)
        sm.clicked.connect(lambda: self._zoom(-1))
        sm.setStyleSheet("QPushButton{background:rgba(255,255,255,10);color:#999;border:1px solid rgba(255,255,255,15);border-radius:3px;font-size:10px;}QPushButton:hover{background:rgba(255,255,255,25);color:#ccc;}")
        fl.addWidget(sm)
        sp = QPushButton("+"); sp.setFixedSize(18,18); sp.setCursor(Qt.PointingHandCursor)
        sp.clicked.connect(lambda: self._zoom(1))
        sp.setStyleSheet("QPushButton{background:rgba(255,255,255,10);color:#999;border:1px solid rgba(255,255,255,15);border-radius:3px;font-size:10px;}QPushButton:hover{background:rgba(255,255,255,25);color:#ccc;}")
        fl.addWidget(sp)
        clr=QPushButton("Clear done"); clr.setCursor(Qt.PointingHandCursor)
        clr.clicked.connect(self._clear_done)
        clr.setStyleSheet("QPushButton{background:transparent;color:rgba(180,180,200,130);border:1px solid rgba(255,255,255,12);border-radius:5px;padding:2px 7px;font-size:10px;}QPushButton:hover{background:rgba(255,100,100,30);color:#ff7878;border-color:rgba(255,100,100,80);}")
        fl.addWidget(clr); lo.addLayout(fl)

    def _init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
        self._tray=QSystemTrayIcon(self)
        pm=QPixmap(32,32); pm.fill(Qt.transparent)
        p=QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        # 蓝色圆形底
        p.setBrush(QBrush(QColor(41,82,163))); p.setPen(QPen(QColor(20,40,80),1.5))
        p.drawEllipse(2,2,28,28)
        # 白色 Ω 符号（战锤风格）
        p.setPen(QPen(Qt.white,2.5))
        p.drawArc(10, 12, 12, 12, 0*16, 180*16)  # 顶部弧
        p.drawLine(10, 15, 10, 22)
        p.drawLine(22, 15, 22, 22)
        p.end()
        self._tray.setIcon(QIcon(pm)); self._tray.setToolTip("Astartes Reminder - Right-click for menu")
        menu=QMenu()
        menu.addAction("Show",self._show_tray)
        # 开机自启开关
        self._autostart_action = menu.addAction("Auto-start on boot")
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(self._is_autostart())
        self._autostart_action.triggered.connect(self._toggle_autostart)
        menu.addSeparator()
        menu.addAction("Quit",self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(lambda r:self._show_tray() if r==QSystemTrayIcon.DoubleClick else None)
        self._tray.show()
    def _hide_tray(self):
        if self._tray: self.hide()
        else: self.close()
    def _show_tray(self): self.show(); self.raise_(); self.activateWindow()
    def _quit(self): self._tray.hide() if self._tray else None; QApplication.quit()

    def _startup_path(self):
        """获取开机启动快捷方式路径"""
        import os as _os
        startup = _os.path.join(_os.getenv("APPDATA",""),
            r"Microsoft\Windows\Start Menu\Programs\Startup",
            "AstartesReminder.lnk")
        return startup

    def _is_autostart(self):
        return os.path.exists(self._startup_path())

    def _toggle_autostart(self, checked):
        """切换开机自启"""
        import pythoncom
        from win32com.client import Dispatch
        startup = self._startup_path()
        if checked:
            # 创建快捷方式
            try:
                shell = Dispatch("WScript.Shell")
                shortcut = shell.CreateShortcut(startup)
                shortcut.TargetPath = "D:\\python\\pythonw.exe"
                shortcut.Arguments = os.path.join(APP_DIR, "pet_reminder.py")
                shortcut.WorkingDirectory = APP_DIR
                shortcut.Description = "Astartes Task Reminder"
                shortcut.Save()
            except Exception as e:
                self._autostart_action.setChecked(False)
        else:
            if os.path.exists(startup):
                try: os.remove(startup)
                except: pass

    def paintEvent(self,e):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r=self.rect(); p.fillRect(r,QColor(30,30,42,245))
        g=QLinearGradient(0,0,self.width(),0)
        g.setColorAt(0.0,QColor(130,160,255,0)); g.setColorAt(0.3,QColor(130,160,255,70))
        g.setColorAt(0.7,QColor(180,130,255,70)); g.setColorAt(1.0,QColor(180,130,255,0))
        p.setPen(QPen(g,2)); p.drawLine(16,2,self.width()-16,2)
        # 右下角缩放手柄
        p.setPen(QPen(QColor(255,255,255,30),1.5))
        for i in range(3):
            x=self.width()-16+i*6; y=self.height()-4
            p.drawLine(x,y,x+4,y-4)
        p.end()
    def _in_resize_zone(self, pos):
        """右下角30x30为缩放热区"""
        return pos.x() > self.width()-30 and pos.y() > self.height()-30

    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:
            if self._in_resize_zone(e.pos()):
                self._resizing=True; self._resize_start=e.globalPos(); self._resize_geom=self.geometry()
            else:
                self._drag_pos=e.globalPos()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self,e):
        if e.buttons()==Qt.LeftButton:
            if hasattr(self,'_resizing') and self._resizing:
                delta=e.globalPos()-self._resize_start
                nw=max(self.minimumWidth(), self._resize_geom.width()+delta.x())
                nh=max(self.minimumHeight(), self._resize_geom.height()+delta.y())
                nw=min(self.maximumWidth(), nw); nh=min(self.maximumHeight(), nh)
                self.resize(nw, nh)
                self._update_scale()
            elif self._drag_pos:
                self.move(e.globalPos()-self._drag_pos)
        else:
            # 鼠标样式提示
            if self._in_resize_zone(e.pos()):
                self.setCursor(Qt.SizeFDiagCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
    def wheelEvent(self, e):
        """Ctrl+滚轮缩放窗口"""
        if e.modifiers() & Qt.ControlModifier:
            delta = 1 if e.angleDelta().y() > 0 else -1
            nw = self.width() + delta * 30
            nh = self.height() + delta * 36
            nw = max(self.minimumWidth(), min(self.maximumWidth(), nw))
            nh = max(self.minimumHeight(), min(self.maximumHeight(), nh))
            self.resize(nw, nh)
            self._update_scale()
        else:
            super().wheelEvent(e)

    def mouseReleaseEvent(self,e):
        self._drag_pos=None; self._resizing=False

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_scale()

    def _update_scale(self):
        self._scale = self.width() / self._base_w
        if hasattr(self, 'pet'):
            self.pet.set_scale(self._scale)
            self._pet_frame.setFixedHeight(int(300*self._scale))
        # 任务列表高度
        if hasattr(self, '_scroll'):
            self._scroll.setMaximumHeight(int(140*self._scale))
        # 全局字体
        f = QFont("Microsoft YaHei", max(7, int(10*self._scale)))
        QApplication.instance().setFont(f)

    def _upd_date(self):
        today=date.today()
        wd=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][today.weekday()]
        self.date_btn.setText(f"📅 {today.month}/{today.day} {wd}")
        self.date_btn.setStyleSheet(f"QPushButton{{background:rgba(255,255,255,12);color:{C['text_secondary']};border:1px solid rgba(255,255,255,18);border-radius:7px;padding:3px 10px;font-size:11px;}}QPushButton:hover{{background:rgba(255,255,255,30);color:{C['text']};}}")
    def _toggle_cal(self):
        if self._cal_popup and self._cal_popup.isVisible(): self._cal_popup.close(); return
        self._cal_popup=QWidget(None,Qt.Popup|Qt.FramelessWindowHint)
        self._cal_popup.setFixedSize(310,340); self._cal_popup.setStyleSheet("background:#28283a;border-radius:10px;")
        cl=QVBoxLayout(self._cal_popup); cl.setContentsMargins(6,6,6,6)
        cal=QCalendarWidget(); cal.setGridVisible(False); cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        cal.setStyleSheet("QCalendarWidget{background:#28283a;border-radius:8px;padding:4px;color:#d0d0f0;}QCalendarWidget QToolButton{color:#d0d0f0;background:rgba(255,255,255,15);border-radius:5px;padding:4px 10px;font-weight:bold;}QCalendarWidget QToolButton:hover{background:rgba(255,255,255,30);}QCalendarWidget QAbstractItemView:enabled{color:#d0d0f0;selection-background-color:rgba(130,160,255,80);selection-color:#fff;}")
        cal.clicked.connect(lambda d:(
            self.dedit.setDate(d),
            setattr(self,'_filter_date',d.toString("yyyy-MM-dd")),
            QTimer.singleShot(100,self._cal_popup.close),
            self._refresh()
        ))
        cl.addWidget(cal)
        btn=QPushButton("Today"); btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda:cal.setSelectedDate(QDate.currentDate()))
        btn.setStyleSheet("QPushButton{background:rgba(130,160,255,50);color:#d0d0f0;border:none;border-radius:6px;padding:6px;}QPushButton:hover{background:rgba(130,160,255,120);}")
        cl.addWidget(btn)
        pos=self.date_btn.mapToGlobal(self.date_btn.rect().bottomLeft())
        self._cal_popup.move(pos.x()-90,pos.y()+4); self._cal_popup.show()

    def _add(self):
        txt=self.input.text().strip()
        if not txt: return
        task={"id":datetime.now().strftime("%Y%m%d%H%M%S%f"),"text":txt,"completed":False,
              "created_at":datetime.now().isoformat(),"date":self.dedit.date().toString("yyyy-MM-dd"),
              "time":self.tedit.time().toString("HH:mm"),"reminded":False}
        self.tasks.append(task); save_tasks(self.tasks)
        self.input.clear(); self._refresh(); self.pet.on_add_task()
    def _toggle(self,tid):
        for t in self.tasks:
            if t["id"]==tid: t["completed"]=not t.get("completed",False); break
        save_tasks(self.tasks); self._refresh()
    def _delete(self,tid):
        self.tasks=[t for t in self.tasks if t["id"]!=tid]; save_tasks(self.tasks); self._refresh()
    def _clear_done(self):
        self.tasks=[t for t in self.tasks if not t.get("completed")]; save_tasks(self.tasks); self._refresh()
    def _refresh(self):
        for w in self._task_widgets.values(): self.task_layout.removeWidget(w); w.deleteLater()
        self._task_widgets.clear()
        self.tasks.sort(key=lambda t:(t.get("date",""),t.get("time",""),t.get("id","")))
        if self._filter_date:
            visible=[t for t in self.tasks if t.get("date","")>=self._filter_date]
        else:
            visible=self.tasks
        for t in visible:
            item=TaskItem(t,self._toggle,self._delete)
            self.task_layout.insertWidget(self.task_layout.count()-1,item)
            self._task_widgets[t["id"]]=item
        total=len(self.tasks); shown=len(visible)
        done=sum(1 for t in visible if t.get("completed"))
        over=sum(1 for t in visible if self._od(t))
        parts=[]
        if self._filter_date: parts.append(f"📅 {self._filter_date}")
        parts+=[f"{shown}/{total} tasks",f"{shown-done} active",f"{done} done"]
        if over: parts.append(f"{over} overdue")
        self.st.setText("  |  ".join(parts))
        if hasattr(self,'_cf_btn'): self._cf_btn.setVisible(bool(self._filter_date))
    def _clear_filter(self): self._filter_date=None; self._refresh()
    def _zoom(self, direction):
        nw = self.width() + direction * 40
        nh = self.height() + direction * 48
        nw = max(self.minimumWidth(), min(self.maximumWidth(), nw))
        nh = max(self.minimumHeight(), min(self.maximumHeight(), nh))
        self.resize(nw, nh)
        self._update_scale()
    def _od(self,task):
        if task.get("completed"): return False
        d=task.get("date","")
        if not d: return False
        try:
            tm=task.get("time",""); dt=d+(" "+tm if tm else"")
            fmt="%Y-%m-%d %H:%M" if tm else"%Y-%m-%d"
            return datetime.now()>datetime.strptime(dt,fmt)
        except: return False
    def _check_reminders(self):
        now=datetime.now()
        for task in self.tasks:
            if task.get("completed") or task.get("reminded"): continue
            d=task.get("date",""); t=task.get("time","")
            if not d: continue
            try:
                dt=d+(" "+t if t else""); fmt="%Y-%m-%d %H:%M" if t else"%Y-%m-%d"
                due=datetime.strptime(dt,fmt)
                if abs((now-due).total_seconds())<=60:
                    self._fire(task); task["reminded"]=True; save_tasks(self.tasks)
            except: pass
    def _fire(self,task):
        if self._tray and QSystemTrayIcon.supportsMessages():
            self._tray.showMessage("⏰ Task Reminder",f"[{task.get('time','')}] {task.get('text','')}",QSystemTrayIcon.Information,5000)
        popup=ReminderPopup(task); popup.show(); self._popups.append(popup)
        self._popups=[p for p in self._popups if p.isVisible()]
        self.pet.on_reminder()
    def closeEvent(self,e):
        if self._tray and self._tray.isVisible(): self.hide(); e.ignore()
        else: QApplication.quit()

def main():
    try:
        app=QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
        app.setFont(QFont("Microsoft YaHei",10))
        w=PetReminderApp()
        screen=app.primaryScreen().geometry()
        w.move(screen.width()-590,30); w.show()
        sys.exit(app.exec_())
    except Exception:
        with open(os.path.join(APP_DIR,"error.log"),"w",encoding="utf-8") as f:
            f.write(traceback.format_exc())
        try: QMessageBox.critical(None,"Error",traceback.format_exc())
        except: pass; sys.exit(1)

if __name__=="__main__":
    main()
