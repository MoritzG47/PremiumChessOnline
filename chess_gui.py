"""
Chess made with custom pyqt5 GUI
Author: Moritz G.
Date: 14.10.2025
1. Stable Version (1.4k lines of Code)

Task List:
✅ Add captured pieces display
🟨 Implement draw conditions (threefold repetition (maybe use Move History), fifty-move rule)
- Add Premoves
✅ Add Move Planning
✅ Add Click-to-move option 
🟨 Add more Cosmetics
- Add more/better animations
✅ Add Increment Option to Clock
✅ Add sound effects
- Add AI player
🟨 websocket online multiplayer
✅ Implement move history + Openings
- Improve Performance
- Clock Synchronization
- Improve Connection Handling
- small bug after reconnection where Opening isnt updated properly
- flip board when playing black
"""
#ngrok http 8000

### Settings ###

INCREMENT = 2           # Increment in seconds
TIME = 5

################

from PyQt5.QtWidgets import QWidget, QApplication, QSystemTrayIcon, QMenu, QAction, QLabel
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QPixmap, QFontMetrics, QIcon, QTransform, QPainterPath
from PyQt5.QtCore import QRectF, Qt, QPointF
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import QTimer, QElapsedTimer, QRect, QUrl
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from screeninfo import get_monitors
import sys, os, math, csv, copy
import pprint
from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QAbstractSocket

### Base GUI Element Class ###
class GuiElement:
    def __init__(self, xpos, ypos, width, height, color, parent=None):
        self.xpos = xpos
        self.ypos = ypos
        self.width = width
        self.height = height
        self.color = color
        self.parent = parent
        self.z_value = 0

        if parent:
            if not hasattr(parent, "_gui_elements"):
                parent._gui_elements = []
            if self not in parent._gui_elements:
                parent._gui_elements.append(self)
        else:
            print(Warning(
                f"GuiElement \"{self.__class__.__name__}\" created without parent. It won't be displayed."))

    @property
    def topleft(self):
        if not self.parent:
            return QPointF(self.xpos, self.ypos)
        return self.parent.topleft

    @property
    def MenuSize(self):
        if not self.parent:
            return AttributeError("Parent not set")
        return self.parent.ExitSize

    @property
    def WinWidth(self):
        if not self.parent:
            return AttributeError("Parent not set")
        return self.parent.WindowWidth

    @property
    def WinHeight(self):
        if not self.parent:
            return AttributeError("Parent not set")
        return self.parent.WindowHeight

    def paint(self, painter):
        raise NotImplementedError

    def contains(self, pos):
        pass

    def update(self):
        if self.parent:
            self.parent.update()

    def repaint(self):
        if self.parent:
            self.parent.repaint()

    def setCursor(self, cursor):
        if self.parent:
            self.parent.setCursor(cursor)

    def setZValue(self, z):
        self.z_value = z
        if self.parent:
            self.parent.update()

    def kill(self):
        if self.parent and self in self.parent._gui_elements:
            self.parent._gui_elements.remove(self)
            self.parent.update()

### Clock Object ###
class ChessClock(GuiElement):
    def __init__(self, text: str, color=QColor(0, 0, 0, 120), textcolor=QColor(255, 255, 255),
                 xpos: int = 0, ypos: int = 0, fontsize: int = 10, pen: bool = True, parent=None, time_min: float = 0.5):
        super().__init__(xpos, ypos, 0, 0, 0, parent)
        self.fontsize = fontsize
        self.time_min = time_min

        self.running = False
        self.elapsed = QElapsedTimer()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.elapsedTime = 0
        self.subtractTime = 0
        self.addedTime = 0
        self.playedSoundeffect = False
        self.increment = 0

    def paint(self, painter):
        x = int(self.topleft.x() + self.xpos)
        y = int(self.topleft.y() + self.ypos)

        if self.running:
            self.elapsedTime = self.elapsed.elapsed() + self.addedTime
        ms = self.elapsedTime - self.subtractTime - self.increment
        ms = int(self.time_min * 60 * 1000 - ms)
        if ms < (1000 * 10) and not self.playedSoundeffect:
            self.parent.SM.play("tenseconds")
            self.playedSoundeffect = True
        if ms < 0:
            ms = 0
            self.stop()
            text = "Time's up!"
            if self.parent.check != 5:
                self.parent.EndGame(5)
        else:
            sec, ms = divmod(ms, 1000)
            min, sec = divmod(sec, 60)
            hundredths = round(ms / 10)
            if hundredths == 100:
                hundredths = 0
                sec += 1
            text = f"{min:02d}:{sec:02d}.{hundredths:02d}"

        painter.setPen(Qt.white)
        painter.setFont(QFont("Consolas", self.fontsize))
        painter.drawText(x, y + 20, text)

    def start(self):
        """Start or resume the clock."""
        if not self.running:
            self.elapsed.restart()
            self.timer.start(100)
            self.subtractTime = self.elapsed.elapsed()
            self.running = True

    def stop(self):
        """Stop (pause) the clock."""
        if self.running:
            self.timer.stop()
            self.addedTime += self.elapsed.elapsed() - self.subtractTime
            self.running = False

    def reset(self):
        """Reset time to zero."""
        self.elapsed.restart()
        self.elapsedTime = 0
        self.subtractTime = 0
        self.addedTime = 0
        self.update()

    def add_time(self, sec):
        """Add time in milliseconds."""
        self.increment += (sec * 1000)
        self.update()

### Line Object ###
class Line(GuiElement):
    def __init__(self, x1, y1, x2, y2, color=QColor(255, 255, 255), width=2, parent=None):
        super().__init__(0, 0, 0, 0, color, parent)
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.color = color
        self.width = width

    def paint(self, painter: QPainter):
        pen = QPen(self.color, self.width)
        painter.setPen(pen)
        painter.drawLine(
            int(self.topleft.x() + self.x1),
            int(self.topleft.y() + self.y1),
            int(self.topleft.x() + self.x2),
            int(self.topleft.y() + self.y2)
        )

### Button Object ###
class Button(GuiElement):
    def __init__(self, text: str, width: int = 100, height: int = 50, image=None,
                 action=None, color=QColor(0, 0, 0, 120), textcolor=QColor(255, 255, 255),
                 hovercolor=QColor(255, 255, 255, 50), hovertextcolor=QColor(255, 255, 255),
                 xpos: int = 0, ypos: int = 0, fontsize: int = 10, pen: bool = True, parent=None):
        super().__init__(xpos, ypos, width, height, color, parent)
        self.text = text
        self.textcolor = textcolor
        self.hovercolor = hovercolor
        self.hovertextcolor = hovertextcolor
        self.image = image
        self.fontsize = fontsize
        self.action = action
        self.pen = pen
        self.hovered = False

    def paint(self, painter: QPainter):
        x = self.topleft.x() + self.xpos
        y = self.topleft.y() + self.ypos
        self.rect = QRectF(x, y, self.width, self.height)

        color = self.hovercolor if self.hovered else self.color
        textcolor = self.hovertextcolor if self.hovered else self.textcolor
        pen = QPen(QColor(255, 255, 255, 180), 2) if self.pen else Qt.NoPen

        painter.setPen(pen)
        painter.setBrush(color)
        painter.drawRect(self.rect)

        if self.image:
            x = self.rect.x() + (self.rect.width() - self.image.width()) / 2
            y = self.rect.y() + (self.rect.height() - self.image.height()) / 2
            painter.drawPixmap(int(x), int(y), self.image)
        else:
            font = QFont("Consolas", self.fontsize)
            painter.setFont(font)
            painter.setPen(textcolor)
            painter.drawText(self.rect, Qt.AlignCenter, self.text)

    def contains(self, pos):
        return self.rect.contains(pos)

    def on_click(self):
        self.action()

### Textbox Object ###
class Textbox(GuiElement):
    def __init__(self, xpos: int=0, ypos: int=0, width: int=100, height: int=100, text="", color=QColor(0, 0, 0, 0),
                 textcolor=QColor(255, 255, 255), fontsize=10, pen: QPen=Qt.NoPen, parent=None, autoscroll: bool=False,
                 deactivate_scrollbars: int=0):
        """
        - deactivate_scrollbars: 0 = none, 1 = vertical, 2 = horizontal, 3 = both
        """
        super().__init__(xpos, ypos, width, height, color, parent)
        self.text = text
        self.color = color
        self.textcolor = textcolor
        self.fontsize = fontsize
        self.pen = pen
        self.autoscroll = autoscroll
        self.deactivate_scrollbars = deactivate_scrollbars

        # Scrolling state
        self.vert_scroll = 0.0
        self.horiz_scroll = 0.0
        self.height_fit = 0
        self.width_fit = 0
        self.vert_scrollbar_rect = None
        self.horiz_scrollbar_rect = None

        # Style constants
        self.outer_scroll_size = 14
        self.inner_scroll_size = 4
        self.scrollbar_range_y = 0
        self.scrollbar_range_x = 0
        self.scrollbar_mode = 0  # 0: none, 1: vert drag, 2: horiz drag

        self.total_text_height = 0
        self.total_text_width = 0
        self.update_text()

    def add_text(self, additional_text=""):
        self.text += additional_text
        if self.autoscroll:
            self.vert_scroll = 1.0
        self.update_text()

    def set_text(self, new_text=""):
        if self.text == new_text:
            return
        self.text = new_text
        if self.autoscroll:
            self.vert_scroll = 1.0
        self.update_text()

    def clear_text(self):
        self.text = ""
        self.vert_scroll = 0.0
        self.horiz_scroll = 0.0
        self.update_text()

    def update_text(self):
        font = QFont("Consolas", self.fontsize)
        metrics = QFontMetrics(font)

        Spacing = 10

        width, height = self.width, self.height
        width -= Spacing
        height -= Spacing

        line_height = metrics.height()
        self.total_text_height = line_height * (self.text.count("\n") + 1)
        self.height_fit = self.total_text_height / (height - self.outer_scroll_size)

        if self.autoscroll and self.height_fit > 1:
            self.vert_scroll = 1.0
        elif self.height_fit <= 1:
            self.vert_scroll = 0.0

        self.total_text_width = max(metrics.horizontalAdvance(line) for line in self.text.splitlines() or [""])
        self.width_fit = self.total_text_width / (width - self.outer_scroll_size)

        if self.deactivate_scrollbars in (1, 3):
            self.height_fit = 1
        if self.deactivate_scrollbars in (2, 3):
            self.width_fit = 1

        self.update()

    # ---------------------------------------------------
    # Main draw method
    # ---------------------------------------------------
    def paint(self, painter: QPainter):
        """Draw textbox background, scrollbars, and text."""
        self.rect = QRectF(self.topleft.x() + self.xpos,
                           self.topleft.y() + self.ypos,
                           self.width, self.height)
        painter.setBrush(self.color)
        painter.setPen(self.pen)
        painter.drawRect(self.rect)

        self._draw_scrollable_text(painter)

    # ---------------------------------------------------
    # Core text rendering + scrollbar calculation
    # ---------------------------------------------------
    def _draw_scrollable_text(self, painter: QPainter):
        font = QFont("Consolas", self.fontsize)
        painter.setFont(font)
        metrics = QFontMetrics(font)

        xSpacing = 10
        ySpacing = 3

        xpos, ypos, width, height = self.xpos, self.ypos, self.width, self.height
        xpos += self.topleft.x()
        ypos += self.topleft.y()
        width -= xSpacing
        height -= ySpacing

        # --- Calculate vert text dimensions and scrollbar needs ---
        scrollbar_inner_height = height - (self.outer_scroll_size * 2) - self.inner_scroll_size
        scrollbar_height = max((scrollbar_inner_height / max(1, self.height_fit)), 20)
        self.scrollbar_range_y = scrollbar_inner_height - scrollbar_height

        # --- Calculate horiz text dimensions and scrollbar needs ---
        scrollbar_inner_width = width - (self.outer_scroll_size * 2) - self.inner_scroll_size
        scrollbar_width = max((scrollbar_inner_width / max(1, self.width_fit)), 20)
        self.scrollbar_range_x = scrollbar_inner_width - scrollbar_width

        # --- Draw text content ---
        y_offset = self.vert_scroll * (self.total_text_height - (height - (self.outer_scroll_size * 2)))
        x_offset = self.horiz_scroll * (self.total_text_width - (width - (self.outer_scroll_size * 2)))
        text_x = xpos + xSpacing
        text_y = ypos + ySpacing
        textbox_width = int(width-(self.outer_scroll_size*2)) if self.height_fit > 1 else width - xSpacing
        textbox_height = int(height-(self.outer_scroll_size*2)) if self.width_fit > 1 else height - ySpacing

        static_textrect = QRectF(text_x, text_y, textbox_width, textbox_height)
        dynamic_textrect = QRectF(text_x - x_offset, text_y - y_offset, self.total_text_width + textbox_width, self.total_text_height + textbox_height)
        inter_rect = dynamic_textrect.intersected(static_textrect)

        if not inter_rect.isNull():
            painter.setClipRect(inter_rect)
            painter.setPen(self.textcolor)
            painter.drawText(dynamic_textrect, Qt.AlignLeft | Qt.AlignTop, self.text)
            painter.setClipping(False)

        width += xSpacing
        height += ySpacing
        # --- Draw vertical scrollbar ---
        if self.height_fit > 1:
            self._draw_scrollbar(painter, xpos, ypos, width, height,
                                self.scrollbar_range_y, scrollbar_height, "vertical")
        else:
            self.vert_scrollbar_rect = None

        # --- Draw horizontal scrollbar ---
        if self.width_fit > 1:
            self._draw_scrollbar(painter, xpos, ypos, width, height,
                                self.scrollbar_range_x, scrollbar_width, "horizontal")
        else:
            self.horiz_scrollbar_rect = None

    # ---------------------------------------------------
    # Scrollbar Drawing
    # ---------------------------------------------------
    def _draw_scrollbar(self, painter, xpos, ypos, width, height, scrollbar_range, scrollbar_height, mode):
        if mode == "vertical":
            x1 = x2 = int(xpos + width - self.outer_scroll_size)
            y1 = int(ypos + self.outer_scroll_size)
            y2 = int(ypos + height - (self.outer_scroll_size * 2))
        elif mode == "horizontal":
            x1 = int(xpos + self.outer_scroll_size)
            x2 = int(xpos + width - (self.outer_scroll_size * 2))
            y1 = y2 = int(ypos + height - self.outer_scroll_size)

        # Draw outer rounded line (scrollbar background)
        painter.setPen(QPen(QColor(150, 150, 150, 100), self.outer_scroll_size, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(x1, y1, x2, y2)

        # Draw inner rounded line (scrollbar foreground)
        if mode == "vertical":
            x = x1-(self.inner_scroll_size/2)
            y = y1+(self.scrollbar_range_y*self.vert_scroll)
            width = self.inner_scroll_size
            height = scrollbar_height
        elif mode == "horizontal":
            x = x1+(self.scrollbar_range_x*self.horiz_scroll)
            y = y1-(self.inner_scroll_size/2)
            width = scrollbar_height
            height = self.inner_scroll_size
        painter.setPen(QPen(QColor(255, 255, 255, 200), self.inner_scroll_size, Qt.SolidLine, Qt.RoundCap))
        inner_rect = QRectF(x, y, width, height)
        painter.drawRect(inner_rect)

        # Update scrollbar for mouse interaction
        if mode == "vertical":
            self.vert_scrollbar_rect = inner_rect
        elif mode == "horizontal":
            self.horiz_scrollbar_rect = inner_rect

    # ---------------------------------------------------
    # Event Handlers
    # ---------------------------------------------------
    def handle_wheel(self, delta_y):
        """Handle mouse wheel scrolling."""
        if self.height_fit > 1:
            new_scroll = (delta_y / 50) * min(0.05, (1/(self.height_fit)))
            self.vert_scroll = max(0, min(self.vert_scroll - new_scroll, 1))

    def handle_drag(self, mouse_pos, last_mouse_pos):
        """Handle manual scrollbar dragging."""
        diff = mouse_pos - last_mouse_pos
        if self.scrollbar_mode == 0:
            if self.vert_scrollbar_rect and self.vert_scrollbar_rect.contains(last_mouse_pos):
                self.scrollbar_mode = 1  # Vertical scrollbar drag
            elif self.horiz_scrollbar_rect and self.horiz_scrollbar_rect.contains(last_mouse_pos):
                self.scrollbar_mode = 2  # Horizontal scrollbar drag
        elif self.scrollbar_mode == 1 and self.vert_scrollbar_rect:
            diff = diff.y()
            scroll_change = diff/self.scrollbar_range_y if self.scrollbar_range_y > 0 else 0
            self.vert_scroll = max(0, min(self.vert_scroll + scroll_change, 1))
            return True
        elif self.scrollbar_mode == 2 and self.horiz_scrollbar_rect:
            diff = diff.x()
            scroll_change = diff/self.scrollbar_range_x if self.scrollbar_range_x > 0 else 0
            self.horiz_scroll = max(0, min(self.horiz_scroll + scroll_change, 1))
            return True
        return False
    
    def undrag(self):
        """Reset scrollbar mode on drag release."""
        self.scrollbar_mode = 0

class WebSocketClient:
    def __init__(self, player_name, parent=None):
        super().__init__()
        self.parent = parent
        self.player_name = player_name
        self.websocket = QWebSocket()
        self.connect_to_server()     
      
        # WebSocket signals
        self.websocket.connected.connect(self.on_connected)
        self.websocket.disconnected.connect(self.on_disconnected)
        self.websocket.textMessageReceived.connect(self.on_message_received)
        self.websocket.error.connect(self.on_error)
        
    def connect_to_server(self):
        # Change this URL to match your server
        url = QUrl("wss://superdiabolically-tres-kingston.ngrok-free.dev/ws")    #"ws://localhost:8000/ws"
        self.websocket.open(url)
        
    def disconnect_from_server(self):
        self.websocket.close()
        
    def send_message(self, msg):
        message = msg
        # Check if connected using state() method
        if message and self.websocket.state() == QAbstractSocket.ConnectedState:
            self.websocket.sendTextMessage(f"{message}")
            #print(f"You: {message}")
        elif message:
            print("Not connected to server!")
            
    def on_connected(self):
        self.parent.connected = True
        self.parent.update()
        print("Connected to server!")

    def on_disconnected(self):
        self.parent.connected = False
        self.parent.gameconnected = False
        self.parent.update()
        print("Disconnected from server!")
        
    def on_message_received(self, message):
        if "init" in message:
            message = message.replace("promotion:", ";")
            print(message.split(":"))
            self.parent.side = int(message.split(":")[1])
            print(f"Assigned side: {self.parent.side}")
            moves = message.split(":")[3]
            print(f"Previous moves received: {moves}")
            if moves != "[]":
                move_list = moves.strip("[]").replace("'", "").split(", ")
                for i, move in enumerate(move_list):
                    if ";" in move:
                        continue
                    elif i + 1 < len(move_list) and ";" in move_list[i + 1]:
                        self.parent.promotionpiece = move_list[i + 1].replace(";", "")
                    print(move)
                    self.parent.make_move(move)
                print(f"Loaded previous moves: {move_list}")
        elif "promotion" in message:
            self.parent.promote_pawn(message)
        elif message == "stop":
            self.parent.gameconnected = False
            self.parent.check = 4
            self.parent.update()
            print("Opponent disconnected!")
        elif message == "start":
            self.parent.gameconnected = True
            self.parent.check = 0
            self.parent.update()
            print("Game started!")
        else:
            self.parent.make_move(message)
            #print(f"Message received: {message}")
        
    def on_error(self, error):
        print(f"WebSocket error: {error}")

### Knocked Pieces Object ###
class KnockedPieces(GuiElement):
    def __init__(self, parent=None):
        super().__init__(0, 0, 0, 0, 0, parent)
        self.imagesize = int(self.WinWidth / 12)
        self.spacing = 0
        self.offset = self.imagesize / 4
        self.group_offset = self.imagesize / 2
        self.pieces = {"Pawn": [0, 0], "Knight": [0, 0], "Bishop": [0, 0], 
                       "Rook": [0, 0], "Queen": [0, 0], "King": [0, 0]}
        self.imgdict = {}
        for piece in self.pieces.keys():
            self.imgdict[piece] = [
                self.parent.SVG.getSVG(f"{piece}White", self.imagesize),
                self.parent.SVG.getSVG(f"{piece}Black", self.imagesize)
            ]

    def paint(self, painter: QPainter):
        group_count = [0, 0]
        x = self.topleft.x() - self.spacing - self.imagesize
        y = self.topleft.y()
        for color in (0, 1):
            n = 0
            for piece, counts in self.pieces.items():
                for _ in range(counts[color]):
                    xpos = x - n * self.offset - (self.group_offset * group_count[color])
                    ypos = y + (color * (self.WinHeight - self.imagesize))
                    painter.drawPixmap(int(xpos), int(ypos), self.imgdict[piece][color])
                    n += 1
                if counts[color] > 0:
                    group_count[color] += 1

    def add_piece(self, piece, color):
        self.pieces[piece][color] += 1

    def contains(self, pos):
        pass
    def on_click(self):
        pass

class SoundManager:
    def __init__(self):
        self.effects = {}
        self.active_sounds = []
        ownpath = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(ownpath, "ChessSounds", "wav")
        for sound in os.listdir(path):
            if sound.endswith(".wav"):
                name = os.path.splitext(sound)[0]
                self.loadSound(name, os.path.join(path, sound))

    def loadSound(self, name, path):
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(path))
        effect.setVolume(0.5)
        self.effects[name] = effect

    def play(self, name):
        if name in self.effects:
            self.effects[name].play()
            # keep it alive while playing
            self.active_sounds.append(self.effects[name])
            # clean up after playback ends
            QTimer.singleShot(1000, lambda: self._cleanup(self.effects[name]))

    def shutdown(self):
        for effect in self.effects.values():
            effect.stop()  # stop playback
            effect.deleteLater()  # schedule deletion in Qt
        self.effects.clear()
        self.active_sounds.clear()

    def _cleanup(self, sound):
        if sound in self.active_sounds:
            self.active_sounds.remove(sound)

class SVGManager:
    def __init__(self):
        self.svgs = {}
        self.cache = {}
        ownpath = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(ownpath, "ChessImgVec")
        for svg in os.listdir(path):
            if svg.endswith(".svg"):
                name = os.path.splitext(svg)[0]
                self.loadSVG(name, os.path.join(path, svg))

    def loadSVG(self, name, path):
        renderer = QSvgRenderer(path)
        self.svgs[name] = renderer

    def getSVG(self, name, size):
        key = (name, size)
        if key in self.cache:
            return self.cache[key]

        if name in self.svgs:
            image = QPixmap(size, size)
            image.fill(Qt.transparent)
            self.svgs[name].render(QPainter(image))
            self.cache[key] = image
            return image

        raise ValueError(f"SVG '{name}' not found.")

    def shutdown(self):
        self.svgs.clear()
        self.cache.clear()

### Figure Base Object ###
class Figure(GuiElement):
    def __init__(self, pos, color, parent=None):
        super().__init__(0, 0, 0, 0, color, parent)
        self.color = color
        self.pos = pos
        self.squaresize = self.WinWidth / 8
        self.image = self.parent.SVG.getSVG(f"{self.__class__.__name__}{'White' if color == 0 else 'Black'}", int(self.squaresize))
        self.offset = QPointF(0, 0)
        self.hovered = False
        self.picked = False
        self.mouse_pos = QPointF(0, 0)
        self.direction_vectors = []
        self.range = 1
        self.EnPassant = False
        self.validMovesList = []
        self.selected = None
        self.currentPieceStyle = "ChessImgVec"
        pieceMap = {"Pawn": "p", "Knight": "n", "Bishop": "b",
                    "Rook": "r", "Queen": "q", "King": "k"}
        self.pgnChar = pieceMap[self.__class__.__name__]

    ### Properties ###
    @property
    def current_pos(self):
        x = self.topleft.x() + self.pos[0]*self.squaresize
        y = self.topleft.y() + (7-self.pos[1])*self.squaresize + self.MenuSize
        return QPointF(x, y)

    def MoveCount(self):
        return self.parent.MoveCount

    def IncMoveCount(self):
        self.parent.MoveCount += 1

    def current_square(self, x=None, y=None):
        if x is None:
            x = self.current_pos.x()
        if y is None:
            y = self.current_pos.y()
        return (max(0, min(int((x - self.topleft.x()) // self.squaresize), 7)),
                max(0, min(int(7 - (y - self.topleft.y() - self.MenuSize) // self.squaresize), 7)))

    def getBoard(self):
        if not self.parent:
            return AttributeError("Parent not set")
        return self.parent.scanBoard()

    def paint(self, painter: QPainter):
        x = self.current_pos.x() + self.offset.x()
        y = self.current_pos.y() + self.offset.y()

        if self.currentPieceStyle != self.parent.PieceStyle:
            self.currentPieceStyle = self.parent.PieceStyle
            if self.currentPieceStyle == "ChessImgVec":
                self.image = self.parent.SVG.getSVG(f"{self.__class__.__name__}{'White' if self.color == 0 else 'Black'}", int(self.squaresize))
            else:
                self.image = QPixmap(os.path.join(self.parent.path, "ChessImgPNG", self.currentPieceStyle, f"{'w' if self.color == 0 else 'b'}{self.pgnChar}.png"))
                self.image = self.image.scaled(int(self.squaresize), int(self.squaresize), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if self.hovered:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, 200), 4))
            if self.picked:
                pos = self.current_square(
                    self.mouse_pos.x(), self.mouse_pos.y())
                x_hover = self.topleft.x() + pos[0]*self.squaresize
                y_hover = self.topleft.y() + \
                    (7-pos[1])*self.squaresize + self.MenuSize
            else:
                x_hover = x
                y_hover = y
            painter.drawRect(
                QRectF(x_hover, y_hover, self.squaresize, self.squaresize))

        if self.parent.selected == self:
            painter.setBrush(QColor(10, 70, 180, 80))
            painter.setPen(Qt.NoPen)
            painter.drawRect(QRectF(self.current_pos.x(
            ), self.current_pos.y(), self.squaresize, self.squaresize))

            if self.parent.check in [5, 6, 7, 8, 9]:
                self.validMovesList = []
            elif self.parent.check != 4:
                for pos in self.validMovesList:
                    x_highlight = self.topleft.x() + pos[0]*self.squaresize
                    y_highlight = self.topleft.y(
                    ) + (7-pos[1])*self.squaresize + self.MenuSize
                    painter.setBrush(QColor(150, 10, 30, 90))
                    painter.setPen(Qt.NoPen)
                    painter.drawRect(
                        QRectF(x_highlight, y_highlight, self.squaresize, self.squaresize))

        painter.drawPixmap(int(x), int(y), self.image)

    ### Logic ###
    def pinMoves(self, board):
        if self.color == self.MoveCount() % 2:
            return []
        threats = []
        attackVectors = self.direction_vectors
        if isinstance(self, Pawn):
            attackVectors = [
                (-1, 1), (1, 1)] if self.color == 0 else [(-1, -1), (1, -1)]
        for dx, dy in attackVectors:
            temp_threats = [(self.pos[0], self.pos[1], dx, dy)]
            blocked = False
            threatens_king = False
            for i in range(1, self.range+1):
                x = self.pos[0] + dx * i
                y = self.pos[1] + dy * i
                if 0 <= x < 8 and 0 <= y < 8:
                    temp_threats.append((x, y, dx, dy))
                    piece = board[y][x]
                    if piece is not None:
                        if piece.color != self.color and isinstance(piece, King):
                            threatens_king = True
                            if blocked:
                                pass
                            else:
                                self.parent.check = 1 if self.color == 1 else 2
                                self.parent.SM.play("move-check")
                            break
                        elif piece.color == self.color:
                            break
                        elif blocked:
                            break
                        blocked = True
            if threatens_king:
                threats += temp_threats
        return threats

    def threatMoves(self, board):
        if self.color == self.MoveCount() % 2:
            return []
        threats = []
        attackVectors = self.direction_vectors
        if isinstance(self, Pawn):
            attackVectors = [
                (-1, 1), (1, 1)] if self.color == 0 else [(-1, -1), (1, -1)]
        for dx, dy in attackVectors:
            for i in range(1, self.range+1):
                x = self.pos[0] + dx * i
                y = self.pos[1] + dy * i
                if 0 <= x < 8 and 0 <= y < 8:
                    threats.append((x, y))
                    piece = board[y][x]
                    if piece is not None:
                        if isinstance(piece, King) and piece.color != self.color:
                            pass
                        else:
                            break
        return threats

    def validMoves(self, board):
        # Piece cant move if its not its turn
        condition_1 = (self.MoveCount() % 2 != self.color)
        # Piece cant move if its pinned
        condition_2 = False  # self.isPinned
        # Piece cant move if check status is 3 (checkmate/promotion) or 4 (stalemate)
        condition_3 = (self.parent.check in [4, 5, 6, 7, 8, 9])
        if condition_1 or condition_2 or condition_3:
            self.validMovesList = []
            return
        # ----------------------
        # Calculate valid moves
        moves = []
        PinMap = self.parent.PinMap
        for dx, dy in self.direction_vectors:
            if None == PinMap[self.pos[1]][self.pos[0]] or self.__class__.__name__ == "King":
                pass
            elif (dx, dy) == PinMap[self.pos[1]][self.pos[0]] or (-dx, -dy) == PinMap[self.pos[1]][self.pos[0]]:
                pass
            else:
                continue
            for i in range(1, self.range+1):
                x = self.pos[0] + dx * i
                y = self.pos[1] + dy * i
                if 0 <= x < 8 and 0 <= y < 8:
                    piece = board[y][x]
                    if piece is not None:
                        if piece.color == self.color or piece.__class__.__name__ == "King":
                            break
                        else:
                            moves.append((x, y))
                            break
                    else:
                        moves.append((x, y))
                else:
                    break
        moves = self.specialFilters(board, moves)
        
        # --- Filter moves that dont resolve check ---
        if self.parent.check - 1 == self.color and self.__class__.__name__ != "King":
            uncheck_moves = []
            for move in moves:
                if PinMap[move[1]][move[0]] == None:
                    pass
                else:
                    uncheck_moves.append(move)
            moves = uncheck_moves

        self.validMovesList = moves

    def move(self, new_pos):
        if self.color == 0:
            self.parent.SM.play("move-self")
        else:
            self.parent.SM.play("move-opponent")

        if hasattr(self, "EnPassantCheck"):
            self.EnPassantCheck(new_pos)
        board = self.getBoard()
        ### Capture logic ###
        target = board[new_pos[1]][new_pos[0]]
        if target is not None and target.color != self.color:
            captured = target
            self.parent.SM.play("capture")
            self.parent.knocked_pieces.add_piece(
                captured.__class__.__name__, captured.color)
            captured.kill()

        ### Move logic and new valid Moves ###
        castle = 0
        if isinstance(self, King) and abs(self.pos[0] - new_pos[0]) == 2:
            if new_pos[0] == 6:  # Kingside
                rook = board[self.pos[1]][7]
                rook.pos = (5, self.pos[1])
                castle = 1
            elif new_pos[0] == 2:  # Queenside
                rook = board[self.pos[1]][0]
                rook.pos = (3, self.pos[1])
                castle = 2
            self.parent.SM.play("castle")

        prev_pos = self.pos
        self.pos = new_pos

        promo =None
        if hasattr(self, "PromotionCheck"):
            promo = self.PromotionCheck(new_pos)
            self.parent.promotionpiece = None
        if hasattr(self, "has_moved"):
            self.has_moved = True
        if self.parent.check in [1, 2]:
            self.parent.check = 0

        Move = self.MoveHistory(prev_pos, new_pos, target, castle, promo, board)
        self.parent.updateGameState()

        if self.parent.check == 6:
            Move += "#"
        if self.parent.check in [1, 2]:
            Move += "+"
        self.parent.MHList.append(Move)

        #self.ThreefoldDrawCheck()
        if isinstance(self, Pawn) or target is not None:
            self.parent.fiftyMoveCounter = 0
        else:
            self.parent.fiftyMoveCounter += 1
        if self.parent.fiftyMoveCounter >= 100:
            self.parent.EndGame(9)
            return
        ### Change Turn ###
        self.IncMoveCount()
        self.update()
        if self.parent.check in [5, 6, 7, 8, 9]:
            return

        self.parent.switch_clocks()

    def specialFilters(self, board, moves):
        return moves

    def MoveHistory(self, prev_pos, new_pos, target=None, castle=0, promo=None, board=None):
        PieceNameMap = {"Pawn": "", "Knight": "N", "Bishop": "B",
                        "Rook": "R", "Queen": "Q", "King": "K"}

        disambiguate = ""
        if self.__class__.__name__ == "Pawn" and target is not None:
            disambiguate = chr(prev_pos[0]+97)
        elif self.__class__.__name__ != "Pawn":
            same_type_pieces = [fig for row in board for fig in row if fig is not None and fig.color == self.color and fig.__class__ == self.__class__ and fig != self]
            same_row = False
            same_column = False
            for fig in same_type_pieces:
                if new_pos in fig.validMovesList:
                    if prev_pos[0] == fig.pos[0]:
                        same_column = True
                    elif prev_pos[1] == fig.pos[1]:
                        same_row = True
                    else:
                        same_row = True
            if same_row:
                disambiguate += chr(prev_pos[0]+97)
            if same_column:
                disambiguate += str(prev_pos[1]+1)

        Move = f"{PieceNameMap[self.__class__.__name__]}{disambiguate}{'x' if target else ''}{chr(new_pos[0]+97)}{new_pos[1]+1}"
        if promo is not None:
            Move += f"={PieceNameMap[promo]}"
        elif castle == 1:
            Move = "O-O"
        elif castle == 2:
            Move = "O-O-O"
        #if self.MoveCount() % 2 == 1:
        #    Move = f"{(self.MoveCount() // 2 )+ 1}.{Move}"
        return Move

    def ThreefoldDrawCheck(self):
        if len(self.parent.MHList) < 8:
            return
        recent_moves = self.parent.MHList[-8:]
        if recent_moves[0:2] == recent_moves[4:6] and recent_moves[2:4] == recent_moves[6:8]:
            print("Threefold repetition detected.")
            self.parent.EndGame(8)

    ### Actions ###
    def pick_up(self, mouse_pos):
        if self.color != self.parent.side:
            self.validMovesList = []
        self.offset = mouse_pos - self.current_pos - \
            QPointF(self.squaresize/2, self.squaresize/2)
        self.mouse_pos = mouse_pos
        self.picked = True
        self.setZValue(1)
        self.setCursor(Qt.ClosedHandCursor)
        self.update()

    def undrag(self, pos):
        self.offset = QPointF(0, 0)
        self.picked = False
        self.setZValue(0)
        self.update()
        if self.parent.check in [4, 5, 6, 7, 8, 9]:
            return 
        dropped_square = self.current_square(pos.x(), pos.y())
        if dropped_square in self.validMovesList:
            self.parent.selected = None
            self.parent.Client.send_message(f"{self.pos[0]}{self.pos[1]}{dropped_square[0]}{dropped_square[1]}")
            self.move(dropped_square)

    def contains(self, pos):
        if self.picked:
            return True
        rect = QRectF(self.current_pos.x(), self.current_pos.y(),
                      self.squaresize, self.squaresize)
        return rect.contains(pos)

    def on_click(self):
        pass

class Pawn(Figure):
    def __init__(self, pos, color, parent=None):
        super().__init__(pos, color, parent)
        self.direction_vectors = [(0, 1)] if color == 0 else [(0, -1)]
        self.range = 1

    def EnPassantCheck(self, new_pos):
        for row in self.getBoard():
            for Figure in row:
                if Figure is not None and Figure.__class__.__name__ == "Pawn":
                    if Figure.EnPassant:
                        Figure.EnPassant = False
        if self.__class__.__name__ == "Pawn":
            if self.pos[0] != new_pos[0] and self.getBoard()[new_pos[1]][new_pos[0]] is None:
                captured = self.getBoard()[self.pos[1]][new_pos[0]]
                captured.kill()
            elif abs(self.pos[1] - new_pos[1]) == 2:
                self.EnPassant = True

    def PromotionCheck(self, new_pos):
        if new_pos[1] == (7 if self.color == 0 else 0):
            if self.parent.side != self.color or self.parent.promotionpiece is not None:
                self.validMovesList = []
                while self.parent.promotionpiece is None:
                    QApplication.processEvents()
                    self.parent.check = 4
                self.parent.promoted = True
                PromotionClasses = {
                    "Queen": Queen,
                    "Rook": Rook,
                    "Bishop": Bishop,
                    "Knight": Knight
                }
                piece = PromotionClasses[self.parent.promotionpiece](
                    pos=new_pos, color=self.color, parent=self.parent)
                self.parent.selected = None
                self.parent.PickedPiece = None
                self.parent.check = 0
                self.kill()
                return self.parent.promotionpiece
            elif self.parent.side == self.color:
                promotion_window = PromotionWindow(parent=self.parent,
                                                xpos=(self.WinWidth / 2) -
                                                (self.squaresize*1.2*2),
                                                ypos=self.MenuSize +
                                                (self.WinWidth / 2) -
                                                (self.squaresize*1.2)/2,
                                                squaresize=self.squaresize*1.2,
                                                color=self.color)
                self.parent.promotion_window = promotion_window
                self.validMovesList = []
                while promotion_window.selected_piece is None:
                    QApplication.processEvents()
                    self.parent.check = 4
                self.parent.Client.send_message(f"promotion:{promotion_window.selected_piece.__name__}")
                self.parent.promoted = True
                promotion_window.selected_piece(
                    pos=new_pos, color=self.color, parent=self.parent)
                self.parent.selected = None
                self.parent.PickedPiece = None
                self.parent.check = 0
                self.kill()
                return promotion_window.selected_piece.__name__
        return None

    def specialFilters(self, board, moves):
        special_filtered = []
        step = 1 if self.color == 0 else -1
        x, y = self.pos

        # --- Forward moves ---
        one_step_y = y + step
        two_step_y = y + 2 * step

        # Single forward move
        if 0 <= one_step_y < 8 and board[one_step_y][x] is None:
            special_filtered.append((x, one_step_y))

            # Double forward move (only from starting rank)
            if ((self.color == 0 and y == 1) or (self.color == 1 and y == 6)) and board[two_step_y][x] is None:
                special_filtered.append((x, two_step_y))

        # --- Diagonal captures (including en passant) ---
        for dx in (-1, 1):
            nx, ny = x + dx, y + step
            if 0 <= nx < 8 and 0 <= ny < 8:
                target = board[ny][nx]

                # Normal capture
                if target is not None and target.color != self.color and not target.__class__.__name__ == "King":
                    special_filtered.append((nx, ny))

                # En passant capture
                side_piece = board[y][nx] if 0 <= nx < 8 else None
                if side_piece is not None and side_piece.color != self.color and getattr(side_piece, "EnPassant", False):
                    special_filtered.append((nx, ny))

        return special_filtered

class Rook(Figure):
    def __init__(self, pos, color, parent=None):
        super().__init__(pos, color, parent)
        self.direction_vectors = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        self.range = 8
        self.has_moved = False

class Knight(Figure):
    def __init__(self, pos, color, parent=None):
        super().__init__(pos, color, parent)
        self.direction_vectors = [(2, 1), (2, -1), (-2, 1), (-2, -1),
                                  (1, 2), (1, -2), (-1, 2), (-1, -2)]
        self.range = 1

class Bishop(Figure):
    def __init__(self, pos, color, parent=None):
        super().__init__(pos, color, parent)
        self.direction_vectors = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        self.range = 8

class Queen(Figure):
    def __init__(self, pos, color, parent=None):
        super().__init__(pos, color, parent)
        self.direction_vectors = [(1, 0), (-1, 0), (0, 1), (0, -1),
                                  (1, 1), (1, -1), (-1, 1), (-1, -1)]
        self.range = 8

class King(Figure):
    def __init__(self, pos, color, parent=None):
        super().__init__(pos, color, parent)
        self.direction_vectors = [(1, 0), (-1, 0), (0, 1), (0, -1),
                                  (1, 1), (1, -1), (-1, 1), (-1, -1)]
        self.range = 1
        self.has_moved = False

    def castlingMoves(self):
        if self.has_moved or self.parent.check in [1, 2]:
            return []
        board = self.getBoard()
        castling_moves = []
        y = self.pos[1]
        # Kingside castling
        if isinstance(board[y][7], Rook) and not board[y][7].has_moved:
            if all(board[y][x] is None for x in range(self.pos[0]+1, 7)):
                if all(self.parent.ThreatMap[y][x] == None for x in range(self.pos[0], 7)):
                    castling_moves.append((self.pos[0] + 2, y))
        # Queenside castling
        if isinstance(board[y][0], Rook) and not board[y][0].has_moved:
            if all(board[y][x] is None for x in range(1, self.pos[0])):
                if all(self.parent.ThreatMap[y][x] == None for x in range(0, self.pos[0]+1)):
                    castling_moves.append((self.pos[0] - 2, y))
        return castling_moves

    def specialFilters(self, board, moves):
        safe_moves = []
        ThreatMap = self.parent.ThreatMap
        for move in moves:
            if ThreatMap[move[1]][move[0]] == None:
                safe_moves.append(move)
        return safe_moves + self.castlingMoves()

### Promotion Window ###
class PromotionWindow(QWidget):
    def __init__(self, parent=None, xpos=100, ypos=100, squaresize=120, color=0):
        super().__init__(parent)

        self.parent = parent
        self.color = color
        self.topleft = self.parent.topleft
        self.xpos = int(xpos)
        self.ypos = int(ypos)
        self.squaresize = int(squaresize)
        self.WindowWidth = squaresize * 4
        self.WindowHeight = squaresize
        self.BGcolor = QColor(40, 40, 40, 220)
        self.pieceMap = {"Pawn": "p", "Knight": "n", "Bishop": "b",
                    "Rook": "r", "Queen": "q", "King": "k"}

        self.selected_piece = None

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        monitor = get_monitors()[0]
        self.setGeometry(0, 0, monitor.width, monitor.height)

        self.init_promotion_buttons()
        self.show()

    def init_promotion_buttons(self):
        piece_classes = [Queen, Rook, Bishop, Knight]
        self.buttons = []
        for i, piece_class in enumerate(piece_classes):
            if self.parent.PieceStyle == "ChessImgVec":
                self.image = self.parent.SVG.getSVG(f"{piece_class.__name__}{'White' if self.color == 0 else 'Black'}", int(self.squaresize))
            else:
                self.image = QPixmap(os.path.join(self.parent.path, "ChessImgPNG", self.parent.PieceStyle, f"{'w' if self.color == 0 else 'b'}{self.pieceMap[piece_class.__name__]}.png"))
                self.image = self.image.scaled(int(self.squaresize), int(self.squaresize), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            button = Button(
                image=self.image,
                text=piece_class.__name__,
                width=self.squaresize,
                height=self.squaresize,
                xpos=i * self.squaresize + self.xpos,
                ypos=self.ypos,
                color=QColor(50, 50, 50, 200),
                hovercolor=QColor(100, 100, 100, 250),
                textcolor=QColor(255, 255, 255),
                hovertextcolor=QColor(255, 255, 255),
                action=lambda pc=piece_class: self.select_piece(pc),
                parent=self
            )
            self.buttons.append(button)

    def paintEvent(self, event):
        self.topleft = self.parent.topleft
        x = self.xpos + (self.topleft.x() if self.topleft else 0)
        y = self.ypos + (self.topleft.y() if self.topleft else 0)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(x, y, self.WindowWidth, self.WindowHeight)
        painter.setBrush(self.BGcolor)
        painter.setPen(Qt.NoPen)
        painter.drawRect(rect)

        for button in self.buttons:
            button.paint(painter)

    def mouseMoveEvent(self, event):
        for button in self.buttons:
            button.hovered = button.contains(event.pos())
        self.update()

    def mousePressEvent(self, event):
        for button in self.buttons:
            if button.contains(event.pos()):
                button.on_click()

    def contains(self, pos):
        rect = QRectF(self.xpos, self.ypos, self.width, self.height)
        return rect.contains(pos)

    def select_piece(self, piece_class):
        self.selected_piece = piece_class
        self.parent.SM.play("promote")
        self.close()  # closes the popup

    def closeEvent(self, a0):
        self.parent.promotion_window = None
        return super().closeEvent(a0)

### Settings Window ###
class SettingsWindow(QWidget):
    def __init__(self, parent=None, squaresize=120):
        super().__init__(parent)

        self.parent = parent
        self.topleft = self.parent.topleft
        item_count = len(os.listdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ChessImgPNG"))) + 1
        self.items_per_row = 4
        self.xpos = int((self.parent.WindowWidth / 2) - (squaresize * self.items_per_row) / 2)
        self.ypos = int((self.parent.WindowHeight / 2) - (squaresize * ((item_count + self.items_per_row - 1) // self.items_per_row)) / 2) + self.parent.ExitSize/2
        self.squaresize = int(squaresize)
        self.BGcolor = QColor(40, 40, 40, 0)
        self.selectColor = QColor(50, 50, 150, 150)
        self.color = QColor(50, 50, 50, 200)
        self.path = os.path.dirname(os.path.abspath(__file__))

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        monitor = get_monitors()[0]
        self.setGeometry(0, 0, monitor.width, monitor.height)
        self.selectedButton = [None, None]
        self.initButtons = []
        self.Mode = 0  # 0: Figures, 1: Boards

        self.init_gui()
        self.init_figure_buttons()
        self.init_board_buttons()
        self.show()

    def init_gui(self):
        self.ExitSize = 40
        exitImgPath = os.path.join(self.path, "images", "Exit_Icon.png")
        ExitImage = QPixmap(exitImgPath)
        ExitImage = ExitImage.scaled(int(
            self.ExitSize*0.8), int(self.ExitSize*0.8), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ExitButton = Button(text="Exit",
                                 image=ExitImage,
                                 width=self.ExitSize+40,
                                 height=self.ExitSize,
                                 color=QColor(255, 0, 0, 160),
                                 textcolor=QColor(255, 255, 255),
                                 hovercolor=QColor(255, 0, 0, 220),
                                 hovertextcolor=QColor(255, 255, 255),
                                 xpos=self.xpos + (self.squaresize*self.items_per_row) - (self.ExitSize + 40),
                                 ypos=self.ypos - self.ExitSize,
                                 action=self.close,
                                 parent=self)

        width = self.ExitSize+100
        self.FiguresButton = Button(text="Figures",
                                 width=width,
                                 height=self.ExitSize,
                                 xpos=self.xpos + (width)*0,
                                 ypos=self.ypos - self.ExitSize,
                                 action=self.show_Figures,
                                 parent=self)

        self.BoardsButton = Button(text="Boards",
                                 width=width,
                                 height=self.ExitSize,
                                 xpos=self.xpos + (width)*1,
                                 ypos=self.ypos - self.ExitSize,
                                 action=self.show_Boards,
                                 parent=self)
        
        self.initButtons.append(self.ExitButton)
        self.initButtons.append(self.FiguresButton)
        self.initButtons.append(self.BoardsButton)

    def init_figure_buttons(self):
        self.figures = []
        count = 0
        for style in os.listdir(os.path.join(self.path, "ChessImgPNG")):
            self.image = QPixmap(os.path.join(self.path, "ChessImgPNG", style, "bk.png"))
            self.image = self.image.scaled(int(self.squaresize), int(self.squaresize), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            button = Button(
                image=self.image,
                text=style,
                width=self.squaresize,
                height=self.squaresize,
                xpos=((count % self.items_per_row) * self.squaresize) + self.xpos,
                ypos=self.ypos + (self.squaresize * (count // self.items_per_row)),
                color=self.color,
                hovercolor=QColor(100, 100, 100, 250),
                textcolor=QColor(255, 255, 255),
                hovertextcolor=QColor(255, 255, 255),
                action=lambda pc=style: self.select_piece(pc),
                parent=self
            )
            self.figures.append(button)
            if self.parent.PieceStyle == style:
                button.color = self.selectColor
                self.selectedButton[0] = button
            count += 1
        vectorlist = ["ChessImgVec"]
        for style in vectorlist:
            self.image = self.parent.SVG.getSVG(f"KingBlack", int(self.squaresize))
            button = Button(
                image=self.image,
                text=style,
                width=self.squaresize,
                height=self.squaresize,
                xpos=((count % self.items_per_row) * self.squaresize) + self.xpos,
                ypos=self.ypos + (self.squaresize * (count // self.items_per_row)),
                color=self.color,
                hovercolor=QColor(100, 100, 100, 250),
                textcolor=QColor(255, 255, 255),
                hovertextcolor=QColor(255, 255, 255),
                action=lambda pc=style: self.select_piece(pc),
                parent=self
            )
            self.figures.append(button)
            if self.parent.PieceStyle == style:
                button.color = self.selectColor
                self.selectedButton[0] = button
            count += 1

        self.WindowWidth = self.squaresize * self.items_per_row
        self.WindowHeight = self.squaresize * ((count + self.items_per_row - 1) // self.items_per_row)

    def init_board_buttons(self):
        self.boards = []
        count = 0
        boardList = ["black", "classic"] + os.listdir(os.path.join(self.path, "ChessBoards", "Preview"))
        for style in boardList:
            if style in ["black", "classic"]:
                imgpath = os.path.join(self.path, "ChessBoards", style + ".png")
            else:
                imgpath = os.path.join(self.path, "ChessBoards", "Preview", style)
            self.image = QPixmap(imgpath)
            self.image = self.image.scaled(int(self.squaresize), int(self.squaresize), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            button = Button(
                image=self.image,
                text=style,
                width=self.squaresize,
                height=self.squaresize,
                xpos=((count % self.items_per_row) * self.squaresize) + self.xpos,
                ypos=self.ypos + (self.squaresize * (count // self.items_per_row)),
                color=self.color,
                hovercolor=QColor(100, 100, 100, 250),
                textcolor=QColor(255, 255, 255),
                hovertextcolor=QColor(255, 255, 255),
                action=lambda pc=style: self.select_board(pc),
                parent=self
            )
            if self.parent.BoardStyle == style:
                button.color = self.selectColor
                self.selectedButton[1] = button
            self.boards.append(button)
            count += 1

        self.WindowWidth = self.squaresize * self.items_per_row
        self.WindowHeight = self.squaresize * ((count + self.items_per_row - 1) // self.items_per_row)

    def paintEvent(self, event):
        self.topleft = self.parent.topleft
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.Mode == 0:
            for button in self.figures:
                button.paint(painter)
        elif self.Mode == 1:
            for button in self.boards:
                button.paint(painter)
        for button in self.initButtons:
            button.paint(painter)

    def show_Boards(self):
        self.Mode = 1
        self.update()

    def show_Figures(self):
        self.Mode = 0
        self.update()

    def mouseMoveEvent(self, event):
        #for button in self.buttons:
        #    button.hovered = button.contains(event.pos())
        self.update()

    def mousePressEvent(self, event):
        visible = [self.figures, self.boards][self.Mode]
        for button in visible + self.initButtons:
            if button.contains(event.pos()):
                button.on_click()
                if button in self.figures + self.boards:
                    self.selectedButton[self.Mode].color = self.color
                    self.selectedButton[self.Mode] = button
                    self.selectedButton[self.Mode].color = self.selectColor
                    self.update()
                elif button in [self.FiguresButton, self.BoardsButton]:
                    button.color = QColor(100, 100, 100, 250)
                    if self.Mode == 0:
                        self.BoardsButton.color = QColor(50, 50, 50, 200)
                    else:
                        self.FiguresButton.color = QColor(50, 50, 50, 200)
                    self.update()

    def contains(self, pos):
        rect = QRectF(self.xpos, self.ypos, self.width, self.height)
        return rect.contains(pos)

    def select_piece(self, style):
        self.parent.PieceStyle = style
        self.parent.SM.play("promote")
        self.update()
        self.parent.update()

    def select_board(self, style):
        self.parent.BoardStyle = style
        self.parent.SM.play("promote")
        self.update()
        self.parent.update()

    def closeEvent(self, a0):
        self.parent.settings_window = None
        return super().closeEvent(a0)

### Main Window ###
class WindowGui(QWidget):
    def __init__(self, width=get_monitors()[0].height*0.75, height=get_monitors()[0].height*0.75, side=0):
        super().__init__()

        monitor = get_monitors()[0]
        self.setGeometry(0, 0, monitor.width, monitor.height)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint |
                            Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setMouseTracking(True)

        self.path = os.path.dirname(os.path.abspath(__file__))

        self.center = QPointF(monitor.width / 2, monitor.height / 2)
        self.ExitSize = 50
        self.WindowWidth = width
        self.WindowHeight = height + self.ExitSize
        self.topleft = QPointF(self.center.x() - self.WindowWidth / 2,
                               self.center.y() - self.WindowHeight / 2)

        self.hovered_element = None
        self.Move = False
        self.drag = False
        self.last_mouse_pos = QPointF(0, 0)
        self.Movepos = QPointF(0, 0)

        self.SVG = SVGManager()
        self.init_gui()
        self.init_chess()
        self.PickedPiece = None
        self.selected = None
        self.check = 0
        self.promotion_window = None
        self.promoted = False
        self.emptyMap = [[None for _ in range(8)] for _ in range(8)]
        self.ThreatMap = copy.deepcopy(self.emptyMap)
        self.PinMap = copy.deepcopy(self.emptyMap)
        self.animation_data = {}
        self.MarkerList = []
        self.Marker = []
        self.squaresize = self.WindowWidth / 8

        self.MoveCount = 0
        self.updateGameState()
        self.MoveCount = 1

        self.SM = SoundManager()
        self.knocked_pieces = KnockedPieces(parent=self)

        self.MHList = []
        self.prevMHList = []
        self.fiftyMoveCounter = 0
        self.side = side

        self.Client = WebSocketClient("Client1", self)
        self.promotionpiece = None
        self.connected = False
        self.gameconnected = False

        self.settings_window = None
        self.PieceStyle = "ChessImgVec"
        self.BoardStyle = "classic"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        winrect = QPainterPath()
        winrect.addRect(QRectF(
            self.topleft.x(),
            self.topleft.y(),
            self.WindowWidth,
            self.WindowHeight
        ))
        border_color = QColor(200, 200, 200, 220)
        border_pen = QPen(border_color, 4)
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(winrect)

        painter.setBrush(QColor(0, 0, 0, 180))
        painter.setPen(Qt.NoPen)
        painter.drawPath(winrect)

        connecttext = "Connected" if self.connected else "Disconnected"
        connectcolor = QColor(0, 200, 0, 180) if self.connected else QColor(200, 0, 0, 180)
        if self.side == -1:
            connecttext = "Spectating"
            connectcolor = QColor(100, 100, 100, 180)
        painter.setPen(QPen(connectcolor))
        painter.setFont(QFont('Arial', 12))
        painter.drawText(QRectF(self.topleft.x() + 10, self.topleft.y() + 10, 350, 30), Qt.AlignLeft | Qt.AlignVCenter, "You: " + connecttext)
        
        connecttext = "Connected" if self.gameconnected else "Disconnected"
        connectcolor = QColor(0, 200, 0, 180) if self.gameconnected else QColor(200, 0, 0, 180)
        painter.setPen(QPen(connectcolor))
        painter.drawText(QRectF(self.topleft.x() + self.WindowWidth - 800, self.topleft.y() + 10, 350, 30), Qt.AlignLeft | Qt.AlignVCenter, "Opponent: " + connecttext)

        self.chess_pattern(painter, self.BoardStyle)

        self.arrowList = []
        for Marker in self.MarkerList:
            pos1, pos2 = Marker
            if pos1 == pos2:
                self.drawMarker(painter, pos1)
            else:
                self.arrowList.append((pos1, pos2))

        sorted_elements = sorted(
            self._gui_elements, key=lambda x: getattr(x, 'z_value', 0))
        for element in sorted_elements:
            element.paint(painter)

        for pos1, pos2 in self.arrowList:
            self.drawArrow(painter, pos1, pos2)

        self.drawMoveHistory(painter)

    def init_gui(self):
        exitImgPath = os.path.join(self.path, "images", "Exit_Icon.png")
        ExitImage = QPixmap(exitImgPath)
        ExitImage = ExitImage.scaled(int(
            self.ExitSize*0.8), int(self.ExitSize*0.8), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.ExitButton = Button(text="Exit",
                                 image=ExitImage,
                                 width=self.ExitSize+40,
                                 height=self.ExitSize,
                                 color=QColor(255, 0, 0, 160),
                                 textcolor=QColor(255, 255, 255),
                                 hovercolor=QColor(255, 0, 0, 220),
                                 hovertextcolor=QColor(255, 255, 255),
                                 xpos=self.WindowWidth - (self.ExitSize + 40),
                                 ypos=0,
                                 action=self.close_app,
                                 parent=self)
        MoveImage = QPixmap(exitImgPath)
        MoveImage = MoveImage.scaled(int(
            self.ExitSize*0.7), int(self.ExitSize*0.7), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        MoveImage = MoveImage.transformed(
            QTransform().rotate(45), mode=Qt.SmoothTransformation)
        self.MoveButton = Button(text="Move",
                                 color=QColor(0, 0, 0, 0),
                                 hovercolor=QColor(255, 255, 255, 40),
                                 action=lambda: setattr(self, 'Move', True),
                                 image=MoveImage,
                                 width=self.ExitSize+40,
                                 height=self.ExitSize,
                                 xpos=self.WindowWidth -
                                 (self.ExitSize + 40)*2,
                                 ypos=0,
                                 pen=True,
                                 parent=self)
        MinimizeImage = QPixmap(os.path.join(self.path, "images", "minimize.png"))
        MinimizeImage = MinimizeImage.scaled(int(
            self.ExitSize*1.2), int(self.ExitSize*1.2), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.MinimizeButton = Button(text="Minimize",
                                     color=QColor(0, 0, 0, 0),
                                     hovercolor=QColor(255, 255, 255, 40),
                                     action=self.hide_app,
                                     image=MinimizeImage,
                                     width=self.ExitSize+40,
                                     height=self.ExitSize,
                                     xpos=self.WindowWidth -
                                     (self.ExitSize + 40)*3,
                                     ypos=0,
                                     pen=True,
                                     parent=self)
        SettingsImage = QPixmap(os.path.join(self.path, "images", "Settings_Icon.png"))
        SettingsImage = SettingsImage.scaled(int(
            self.ExitSize*0.8), int(self.ExitSize*0.8), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.SettingsButton = Button(text="Settings",
                                     color=QColor(0, 0, 0, 0),
                                     hovercolor=QColor(255, 255, 255, 40),
                                     action=self.open_settings,
                                     image=SettingsImage,
                                     width=self.ExitSize+40,
                                     height=self.ExitSize,
                                     xpos=self.WindowWidth -
                                     (self.ExitSize + 40)*4,
                                     ypos=0,
                                     pen=True,
                                     parent=self)

        # Example Line
        self.Line = Line(0, 50, self.WindowWidth, 50, width=2, parent=self)

    ### Chess Related Methods ###
    def chess_pattern(self, painter, var="classic"):
        square_size = self.WindowWidth/8
        if var == "black":
            grayscale = int(0.3*255)
            color = QColor(grayscale, grayscale, grayscale, 200)
            for row in range(8):
                for col in range(8):
                    if (row + col) % 2 == 0:
                        painter.setBrush(color)
                        painter.setPen(Qt.NoPen)
                        square_rect = QRectF(
                            self.topleft.x() + col * square_size,
                            self.topleft.y() + self.ExitSize + row * square_size,
                            square_size, square_size
                        )
                        painter.drawRect(square_rect)
        elif var == "classic":
            for row in range(8):
                for col in range(8):
                    if (row + col) % 2 == 0:
                        color = QColor(240, 217, 181, 200)  # Light square
                    else:
                        color = QColor(181, 136, 99, 200)   # Dark square
                    painter.setBrush(color)
                    painter.setPen(Qt.NoPen)
                    square_rect = QRectF(
                        self.topleft.x() + col * square_size,
                        self.topleft.y() + self.ExitSize + row * square_size,
                        square_size, square_size
                    )
                    painter.drawRect(square_rect)
        else:
            imagePath = os.path.join(self.path, "ChessBoards", "Boards", var)
            boardImage = QPixmap(imagePath)
            boardImage = boardImage.scaled(int(self.WindowWidth), int(self.WindowWidth), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            painter.drawPixmap(int(self.topleft.x()), int(self.topleft.y() + self.ExitSize), boardImage)

    def init_chess(self):
        for color in range(2):
            for i in range(8):
                pawn = Pawn(
                    pos=(i, 6 if color else 1),
                    color=color,
                    parent=self,
                )
            for i, piece_class in enumerate([Rook, Knight, Bishop, Queen, King, Bishop, Knight, Rook]):
                piece = piece_class(
                    pos=(i, 7 if color else 0),
                    color=color,
                    parent=self,
                )
       

        self.WhiteClock = ChessClock(
            text="Clock",
            color=QColor(0, 0, 0, 120),
            textcolor=QColor(255, 255, 255),
            xpos=self.WindowWidth + 20,
            ypos=self.WindowHeight/2 + 50 + self.ExitSize/2,
            fontsize=18,
            pen=None,
            parent=self,
            time_min=TIME
        )

        self.BlackClock = ChessClock(
            text="Clock",
            color=QColor(0, 0, 0, 120),
            textcolor=QColor(255, 255, 255),
            xpos=self.WindowWidth + 20,
            ypos=self.WindowHeight/2 - 50 + self.ExitSize/2,
            fontsize=18,
            pen=None,
            parent=self,
            time_min=TIME
        )

    def init_animations(self, winner, result):
        shade = 0.4
        bg_color = (255*shade, 151*shade, 28*shade, 255)
        shade = 1
        bgborder_color = (242, 183, 51, 255)
        self.bgborderrect = QLabel(self)
        self.bgborderrect.setStyleSheet(f"background-color: rgba{bgborder_color}; border-radius: 8px;")
        self.bgborderrect.hide()

        self.bgrect = QLabel(self)
        self.bgrect.setStyleSheet(f"background-color: rgba{bg_color}; border-radius: 8px;")
        self.bgrect.hide()

        img_width = int(self.WindowWidth/2.7)
        img_height = int(self.WindowHeight/2.7)
        if winner == "Noone":
            WinnerImgPath = os.path.join(self.path, "ChessImgVec", "KingNooneWinHi.png")
            self.image = QPixmap(WinnerImgPath)
            self.image = self.image.scaled(img_width, img_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            WinnerImgPath = os.path.join(self.path, "ChessImgVec", f"King{winner}Win.svg")
            self.SVGRenderer = QSvgRenderer(WinnerImgPath)
            self.SVGRenderer.setAspectRatioMode(Qt.KeepAspectRatio)
            self.image = QPixmap(img_width, img_height)
            self.image.fill(Qt.transparent)
            # Render SVG onto pixmap
            painter = QPainter(self.image)
            self.SVGRenderer.render(painter)
            painter.end()
            # Put pixmap into a QLabel
        self.imglabel = QLabel(self)
        self.imglabel.setPixmap(self.image)
        self.imglabel.setAlignment(Qt.AlignCenter)

        self.text = QLabel(parent=self, text=f"{winner} Wins!\n {result}")
        self.text.setAlignment(Qt.AlignCenter)
        self.text.setStyleSheet("font-size: 38px; font-weight: bold; color: white;")
        
        width = int(self.WindowWidth/2)
        self.animation_data[self.bgborderrect] = (width, int(self.WindowHeight/2)-65, 0, 4500)
        self.animation_data[self.bgrect] = (width, int(self.WindowHeight/2)-100, 0, 3000)
        self.animation_data[self.imglabel] = (width, int(self.WindowHeight/2)-100, -50, 3000)
        self.animation_data[self.text] = (width, 100, int(img_height*0.3 + 50), 3000)

        animationList = []
        for item in self.animation_data.items():
            key, value = item
            anim = self.animate_expand_center(self, key, target_width=value[0], target_height=value[1], duration=value[3], y_offset=value[2])
            animationList.append(anim)

        self.content_group = QParallelAnimationGroup(self)
        for anim in animationList:
            self.content_group.addAnimation(anim)

    def switch_clocks(self):
        if self.WhiteClock.running:
            self.WhiteClock.stop()
            self.BlackClock.start()
            self.WhiteClock.add_time(INCREMENT)
        elif self.BlackClock.running:
            self.BlackClock.stop()
            self.WhiteClock.start()
            self.BlackClock.add_time(INCREMENT)
        else:
            self.WhiteClock.add_time(INCREMENT)
            self.BlackClock.start()
            self.SM.play("game-start")

    def updateGameState(self):
        board = self.scanBoard()
        self.PinMap = copy.deepcopy(self.emptyMap)
        self.ThreatMap = copy.deepcopy(self.emptyMap)
        noMovesleft = True

        for element in self._gui_elements:
            if isinstance(element, Figure):
                for pin in element.pinMoves(board):         ### Creating PinMap ###
                    x, y, dx, dy = pin
                    self.PinMap[y][x] = (dx, dy)
                for threat in element.threatMoves(board):   ### Creating ThreatMap ###
                    x, y = threat
                    self.ThreatMap[y][x] = 1
        for element in self._gui_elements:
            if isinstance(element, Figure):
                element.validMoves(board)                   ### Updating Valid Moves ###
                if element.validMovesList != []:
                    noMovesleft = False
        if noMovesleft:
            if self.check in [1, 2]:
                self.check = 6  # Checkmate
            else:
                self.check = 7  # Stalemate
            self.EndGame(self.check)

    def current_square(self, x, y):
            return (max(0, min(int((x - self.topleft.x()) // self.squaresize), 7)),
                    max(0, min(int(7 - (y - self.topleft.y() - self.ExitSize) // self.squaresize), 7)))

    def make_move(self, move: str):
        try:
            if "Opponent: " in move:
                move = move.replace("Opponent: ", "")
            board = self.scanBoard()
            pos1 = (int(move[0]), int(move[1]))
            pos2 = (int(move[2]), int(move[3]))
            piece = board[pos1[1]][pos1[0]]
            if piece is not None:
                piece.move(pos2)
        except Exception as e:
            print("Error making move:", e)

    def check_hover(self, pos):
        for element in self._gui_elements:
            if isinstance(element, Button) or isinstance(element, Figure):
                if element.contains(pos):
                    if isinstance(element, Figure) and not self.drag:
                        self.setCursor(Qt.OpenHandCursor)
                    elif isinstance(element, Button) and not self.drag:
                        self.setCursor(Qt.ArrowCursor)
                    if self.hovered_element != element:
                        if self.hovered_element:
                            self.hovered_element.hovered = False
                        element.hovered = True
                        self.hovered_element = element
                        self.update()
                    break
            elif isinstance(element, Textbox):
                if self.drag:
                    if element.handle_drag(pos, self.last_mouse_pos):
                        self.last_mouse_pos = pos
                        self.update()
                else:
                    element.undrag()
        else:
            if self.hovered_element:
                self.setCursor(Qt.ArrowCursor)
                self.hovered_element.hovered = False
                self.hovered_element = None
                self.update()

    def scanBoard(self):
        board = copy.deepcopy(self.emptyMap)
        for element in self._gui_elements:
            if isinstance(element, Figure):
                x, y = element.pos
                board[y][x] = element
        return board

    def EndGame(self, result):
        self.SM.play("game-end")
        self.check = result
        RESULT_MAP = {
            5: "Time Ran Out",
            6: "Checkmate",
            7: "Stalemate",
            8: "Threefold Repetition",
            9: "50-Move Rule",
        }
        if result == 5:
            Winner = "Black" if self.MoveCount % 2 == 1 else "White"
        elif result == 6:
            Winner = "Black" if self.MoveCount % 2 == 0 else "White"
        elif result in [7, 8, 9]:
            Winner = "Noone"
        print("Game Ended:", RESULT_MAP.get(
            result, "Unknown Result"), "Winner:", Winner)
        self.WhiteClock.stop()
        self.BlackClock.stop()

        ### Animation ###
        self.init_animations(Winner, RESULT_MAP.get(result, "Unknown Result"))
        self.content_group.start()
        self.update()

    def animate_expand_center(self, parent: QWidget, widget: QWidget, target_width: int, target_height: 
                              int, duration: int = 800, y_offset: int = 0) -> QPropertyAnimation:
        """
        Animate a widget so it expands horizontally from width 0 to target_width,
        centered in the given parent widget.
        
        Args:
            parent (QWidget): The parent widget (usually your main window).
            widget (QWidget): The widget to animate (e.g., QLabel, QFrame).
            target_width (int): Final width of the widget.
            target_height (int): Final height of the widget.
            duration (int): Animation duration in ms (default: 800).
        """
        # Ensure widget is visible
        widget.show()

        # Compute geometry centered in parent
        cx, cy = int(self.topleft.x() + self.WindowWidth // 2), int(self.topleft.y() + self.WindowHeight // 2)
        cy += y_offset  # Apply vertical offset if any
        # Start with width 0, full target height
        start_rect = QRect(cx, cy - target_height // 2, 0, target_height)
        end_rect = QRect(cx - target_width // 2, cy - target_height // 2, target_width, target_height)

        # Apply start geometry before animation
        widget.setGeometry(start_rect)
        widget.update()
        # Animate geometry change
        anim = QPropertyAnimation(widget, b"geometry")
        anim.setDuration(duration)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        widget._expand_anim = anim

        return anim
    
    def current_square(self, x, y):
            return (max(0, min(int((x - self.topleft.x()) // self.squaresize), 7)),
                    max(0, min(int(7 - (y - self.topleft.y() - self.ExitSize) // self.squaresize), 7)))

    def drawMarker(self, painter, pos1):
        color = QColor(0, 255, 0, 80)
        markerrect = QRectF(
            self.topleft.x() + pos1[0] * self.squaresize,
            self.topleft.y() + self.ExitSize + (7 - pos1[1]) * self.squaresize,
            self.squaresize,
            self.squaresize
        )
        painter.fillRect(markerrect, color)

    def drawArrow(self, painter, pos1, pos2):
        color = QColor(0, 150, 0, 255)
        pos1 = list(pos1)
        pos2 = list(pos2)
        line_pen = QPen(color, 20, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(line_pen)
        
        if not (abs(pos1[0]-pos2[0]) == 2 and abs(pos1[1]-pos2[1]) == 1) and \
           not (abs(pos1[0]-pos2[0]) == 1 and abs(pos1[1]-pos2[1]) == 2):
            pass
        else:
            start_x = self.topleft.x() + (pos1[0] + 0.5) * self.squaresize
            start_y = self.topleft.y() + self.ExitSize + (7 - pos1[1] + 0.5) * self.squaresize
            if abs(pos1[0]-pos2[0]) == 2:
                pos1[0] = pos2[0]
            else:
                pos1[1] = pos2[1]
            end_x = self.topleft.x() + (pos1[0] + 0.5) * self.squaresize
            end_y = self.topleft.y() + self.ExitSize + (7 - pos1[1] + 0.5) * self.squaresize
            painter.drawLine(QPointF(start_x, start_y), QPointF(end_x, end_y))

        start_x = self.topleft.x() + (pos1[0] + 0.5) * self.squaresize
        start_y = self.topleft.y() + self.ExitSize + (7 - pos1[1] + 0.5) * self.squaresize
        end_x = self.topleft.x() + (pos2[0] + 0.5) * self.squaresize
        end_y = self.topleft.y() + self.ExitSize + (7 - pos2[1] + 0.5) * self.squaresize

        # Draw arrowhead at the end of the arrow
        # Calculate direction vector
        dx = end_x - start_x
        dy = end_y - start_y
        length = math.hypot(dx, dy)
        if length == 0:
            return
        # Normalize direction
        udx = dx / length
        udy = dy / length

        # Arrowhead size
        arrow_size = self.squaresize * 0.4
        angle = math.radians(40)  # degrees for arrowhead

        # Calculate points for arrowhead
        left_x = end_x - arrow_size * (udx * math.cos(angle) - udy * math.sin(angle))
        left_y = end_y - arrow_size * (udy * math.cos(angle) + udx * math.sin(angle))
        right_x = end_x - arrow_size * (udx * math.cos(-angle) - udy * math.sin(-angle))
        right_y = end_y - arrow_size * (udy * math.cos(-angle) + udx * math.sin(-angle))

        arrow_head = [QPointF(end_x, end_y), QPointF(left_x, left_y), QPointF(right_x, right_y)]

        arrow_pen = QPen(color, 8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(arrow_pen)
        painter.setBrush(color)
        painter.drawPolygon(*arrow_head)
        painter.setPen(line_pen)
        painter.drawLine(QPointF(start_x, start_y), QPointF(end_x-(udx*arrow_size*0.8), end_y-(udy*arrow_size*0.8)))

    def drawMoveHistory(self, painter: QPainter):
        MoveHistoryWidth = self.WindowWidth/3
        MoveHistoryHeight = self.WindowWidth/2
        x = self.topleft.x()-MoveHistoryWidth-1
        y = self.topleft.y() + self.ExitSize + self.WindowWidth/4
        opening_height = MoveHistoryHeight/9
        if hasattr(self, 'MHTextbox') == False:
            self.OpeningTextbox = Textbox(xpos=-MoveHistoryWidth-1, ypos=self.ExitSize + self.WindowWidth/4,
                                          width=MoveHistoryWidth, height=opening_height,
                                          text="Starting Position", color=QColor(0, 0, 0, 180),
                                          textcolor=QColor(255, 255, 255), fontsize=11,
                                          autoscroll=False, pen=QPen(QColor(200, 200, 200, 220), 2),
                                          parent=self, deactivate_scrollbars=0)
            self.MHTextbox = Textbox(xpos=-MoveHistoryWidth-1, ypos=self.ExitSize + self.WindowWidth/4 + opening_height,
                                     width=MoveHistoryWidth, height=MoveHistoryHeight-opening_height,
                                     text="", color=QColor(0, 0, 0, 180),
                                     textcolor=QColor(255, 255, 255), fontsize=11,
                                     autoscroll=True, pen=QPen(QColor(200, 200, 200, 220), 2),
                                     parent=self)
        if self.prevMHList != self.MHList:
            OpeningList = []
            MHText = ""
            for i, move in enumerate(self.MHList):
                if i % 2 == 0:
                    MHText += f"{(i//2)+1}.  {move}" + " " * (10 - len(move))
                    OpeningList.append(f'{(i//2)+1}.{move}')
                else:
                    MHText += f"{move}\n"
                    OpeningList.append(f'{move}')
            
            self.MHTextbox.set_text(MHText)

            rowname = "moves_list"
            with open("openings.csv", newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row[rowname] == f"{OpeningList}":
                        OpeningName = row["Opening"]
                        self.OpeningTextbox.set_text(OpeningName)
                        return
        self.prevMHList = self.MHList.copy()

    def promote_pawn(self, message):
        piece = message.replace("Opponent: promotion:", "")
        self.promotionpiece = piece

    ## Window Control Methods ###
    def open_settings(self):
        if self.promotion_window is not None and self.promotion_window.isVisible():
            return
        if self.settings_window is None or not self.settings_window.isVisible():
            self.settings_window = SettingsWindow(parent=self, squaresize=self.squaresize*1.2)
        
    def close_app(self):
        print("Exiting application")
        self.SM.shutdown()
        self.SVG.shutdown()
        QApplication.quit()
        QApplication.processEvents()
        self.hide()
        self.close()
        sys.exit(0)
        
    def hide_app(self):
        self.hide()
        if self.promotion_window:
            self.promotion_window.hide()
        if self.settings_window:
            self.settings_window.hide()
        if not hasattr(self, 'tray_icon'):
            self.tray_icon = QSystemTrayIcon(self)
            svg_pixmap = self.SVG.getSVG("KingWhite", 64)
            self.tray_icon.setIcon(QIcon(svg_pixmap))
            tray_menu = QMenu()
            restore_action = QAction("Show Menu", self)
            restore_action.triggered.connect(self.show_menu)
            tray_menu.addAction(restore_action)
            exit_action = QAction("Exit", self)
            exit_action.triggered.connect(self.close_app)
            tray_menu.addAction(exit_action)
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(
                lambda reason: self.show_menu() if reason == QSystemTrayIcon.Trigger else None
            )
            self.tray_icon.show()

    def show_menu(self):
        self.show()
        if self.promotion_window:
            self.promotion_window.show()
        if self.settings_window:
            self.settings_window.show()
        self.activateWindow()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.Marker = [self.current_square(event.pos().x(), event.pos().y())]
        if event.button() == Qt.LeftButton:
            self.MarkerList = []
            self.update()
            self.drag = True
            self.Movepos = event.pos() - self.topleft
            self.last_mouse_pos = event.pos()
            was_selected = None
            if self.selected is not None:
                was_selected = self.selected
                self.selected.undrag(event.pos())
                self.selected = None
                self.PickedPiece = None
                if self.promoted:
                    self.promoted = False
                    return
            for element in self._gui_elements:
                if element.contains(event.pos()):
                    try:
                        element.on_click()
                        if isinstance(element, Figure):
                            if element != was_selected:
                                self.selected = element
                            self.PickedPiece = element
                            self.PickedPiece.pick_up(event.pos())
                    except Exception as e:
                        print(f"Error occurred while clicking element: {e}")
                    break

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self.Marker.append(self.current_square(event.pos().x(), event.pos().y()))
            if self.Marker not in self.MarkerList and len(self.Marker) == 2:
                self.MarkerList.append(self.Marker)
            elif len(self.Marker) == 1:
                Warning("Need two positions for marker")
            else:
                self.MarkerList.remove(self.Marker)
            self.update()
        if event.button() == Qt.LeftButton:
            self.Move = False
            self.drag = False
            if self.PickedPiece:
                self.PickedPiece.undrag(event.pos())
                self.PickedPiece = None
            self.check_hover(event.pos())
        
    def mouseMoveEvent(self, event):
        if self.PickedPiece and self.drag:
            self.selected = self.PickedPiece
            self.PickedPiece.pick_up(event.pos())
            self.setCursor(Qt.ClosedHandCursor)
        if self.Move:
            self.topleft = event.pos() - self.Movepos
            for key in self.animation_data:
                target_w, target_h, y_offset, duration = self.animation_data[key]
                cx, cy = int(self.topleft.x() + self.WindowWidth // 2), int(self.topleft.y() + self.WindowHeight // 2)
                cy += y_offset
                new_rect = QRect(cx - target_w // 2, cy - target_h // 2, target_w, target_h)
                key.setGeometry(new_rect)
            self.update()
            if self.promotion_window:
                self.promotion_window.update()
            if self.settings_window:
                self.settings_window.update()
        self.check_hover(event.pos())

    def wheelEvent(self, event):
        delta_y = event.angleDelta().y()
        for element in self._gui_elements:
            if isinstance(element, Textbox):
                if element.rect.contains(event.pos()):
                    element.handle_wheel(delta_y)
                    self.update()
                    break

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = WindowGui(side=0)
    gui.show()
    sys.exit(app.exec_())