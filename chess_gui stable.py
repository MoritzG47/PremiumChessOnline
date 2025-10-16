"""
Chess made with custom pyqt5 GUI
Author: Moritz G.
Date: 14.10.2025
1. Stable Version (1.4k lines of Code)

Task List:
- Add captured pieces display
- Implement draw conditions (threefold repetition (maybe use Move History), fifty-move rule)
- Add Premoves
✅ Add Move Planning
✅ Add Click-to-move option 
- Add more Cosmetics
- Add more/better animations
✅ Add Increment Option to Clock
✅ Add sound effects
- Add AI player
- Implement move history
- Improve Performance
"""

### Settings ###

BOARD_VARIANT = 0       # 0 = Black and White, 1 = Classic
INCREMENT = 2           # Increment in seconds
TIME = 5

################

from PyQt5.QtWidgets import QWidget, QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QPixmap, QFontMetrics, QIcon, QTransform, QPainterPath
from PyQt5.QtCore import QRectF, Qt, QPointF
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import QTimer, QElapsedTimer, QRect, QUrl
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from screeninfo import get_monitors
import sys
import time
import math
import os
import pprint
import copy

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


### Figure Base Object ###
class Figure(GuiElement):
    def __init__(self, pos, color, parent=None):
        super().__init__(0, 0, 0, 0, color, parent)
        self.color = color
        self.pos = pos
        self.squaresize = self.WinWidth / 8
        self.offset = QPointF(0, 0)
        self.hovered = False
        self.picked = False
        self.mouse_pos = QPointF(0, 0)
        self.direction_vectors = []
        self.range = 1
        self.EnPassant = False
        self.validMovesList = []
        self.selected = None

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

    def getSVG(self):
        self.ImgPath = os.path.join(self.parent.path, "ChessImgVec", f"{self.__class__.__name__}{'White' if self.color == 0 else 'Black'}.svg")
        self.SVGRenderer = QSvgRenderer(self.ImgPath)
        self.image = QPixmap(int(self.squaresize), int(self.squaresize))
        self.image.fill(Qt.transparent)
        self.SVGRenderer.render(QPainter(self.image))

    def getBoard(self):
        if not self.parent:
            return AttributeError("Parent not set")
        return self.parent.scanBoard()

    def paint(self, painter: QPainter):
        x = self.current_pos.x() + self.offset.x()
        y = self.current_pos.y() + self.offset.y()

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

            if self.parent.check in [5, 6, 7]:
                self.validMovesList = []
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
        condition_3 = (self.parent.check in [4, 5, 6, 7])
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
            captured.kill()

        ### Move logic and new valid Moves ###
        if isinstance(self, King) and abs(self.pos[0] - new_pos[0]) == 2:
            if new_pos[0] == 6:  # Kingside
                rook = board[self.pos[1]][7]
                rook.pos = (5, self.pos[1])
            elif new_pos[0] == 2:  # Queenside
                rook = board[self.pos[1]][0]
                rook.pos = (3, self.pos[1])
            self.parent.SM.play("castle")
        self.pos = new_pos
        if hasattr(self, "PromotionCheck"):
            self.PromotionCheck(new_pos)
        if hasattr(self, "has_moved"):
            self.has_moved = True
        if self.parent.check in [1, 2]:
            self.parent.check = 0

        self.parent.updateGameState()

        ### Change Turn ###
        self.IncMoveCount()
        self.update()
        if self.parent.check in [5, 6, 7]:
            return

        self.parent.switch_clocks()

    def specialFilters(self, board, moves):
        return moves

    ### Actions ###
    def pick_up(self, mouse_pos):
        if self.parent.check == 4:
            self.validMovesList = []
            return
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
        if self.parent.check in [4, 5, 6, 7]:
            return 
        dropped_square = self.current_square(pos.x(), pos.y())
        if dropped_square in self.validMovesList:
            self.parent.selected = None
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
        self.getSVG()
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
        if (self.color == 0 and new_pos[1] == 7) or (self.color == 1 and new_pos[1] == 0):
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
            self.parent.promoted = True
            promotion_window.selected_piece(
                pos=new_pos, color=self.color, parent=self.parent)
            self.parent.selected = None
            self.parent.PickedPiece = None
            self.parent.check = 0
            self.kill()

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
        self.getSVG()
        self.direction_vectors = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        self.range = 8
        self.has_moved = False

class Knight(Figure):
    def __init__(self, pos, color, parent=None):
        super().__init__(pos, color, parent)
        self.getSVG()
        self.direction_vectors = [(2, 1), (2, -1), (-2, 1), (-2, -1),
                                  (1, 2), (1, -2), (-1, 2), (-1, -2)]
        self.range = 1

class Bishop(Figure):
    def __init__(self, pos, color, parent=None):
        super().__init__(pos, color, parent)
        self.getSVG()
        self.direction_vectors = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        self.range = 8

class Queen(Figure):
    def __init__(self, pos, color, parent=None):
        super().__init__(pos, color, parent)
        self.getSVG()
        self.direction_vectors = [(1, 0), (-1, 0), (0, 1), (0, -1),
                                  (1, 1), (1, -1), (-1, 1), (-1, -1)]
        self.range = 8

class King(Figure):
    def __init__(self, pos, color, parent=None):
        super().__init__(pos, color, parent)
        self.getSVG()
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

        self.selected_piece = None

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        monitor = get_monitors()[0]
        self.setGeometry(0, 0, monitor.width, monitor.height)

        self.init_promotion_buttons()
        self.show()

    def getSVG(self, piece_class):
        self.ImgPath = os.path.join(self.parent.path, "ChessImgVec", f"{piece_class.__name__}{'White' if self.color == 0 else 'Black'}.svg")
        self.SVGRenderer = QSvgRenderer(self.ImgPath)
        self.image = QPixmap(int(self.squaresize), int(self.squaresize))
        self.image.fill(Qt.transparent)
        self.SVGRenderer.render(QPainter(self.image))

    def init_promotion_buttons(self):
        piece_classes = [Queen, Rook, Bishop, Knight]
        self.buttons = []
        for i, piece_class in enumerate(piece_classes):
            self.getSVG(piece_class)
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

### Main Window ###
class WindowGui(QWidget):
    def __init__(self, width=get_monitors()[0].height*0.75, height=get_monitors()[0].height*0.75):
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

        self.chess_pattern(painter, BOARD_VARIANT)

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

        # Example Line
        self.Line = Line(0, 50, self.WindowWidth, 50, width=2, parent=self)

    ### Chess Related Methods ###
    def chess_pattern(self, painter, var=0):
        square_size = self.WindowWidth/8
        if var == 0:
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
        elif var == 1:
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
        self.animation_data[self.text] = (width, 80, int(img_height*0.3 + 50), 3000)

        animationList = []
        for item in self.animation_data.items():
            key, value = item
            anim = self.animate_expand_center(self, key, target_width=value[0], target_height=value[1], duration=value[3], y_offset=value[2])
            animationList.append(anim)

        self.content_group = QParallelAnimationGroup(self)
        for anim in animationList:
            self.content_group.addAnimation(anim)

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
            7: "Stalemate"
        }
        if result == 5:
            Winner = "Black" if self.MoveCount % 2 == 1 else "White"
        elif result == 6:
            Winner = "Black" if self.MoveCount % 2 == 0 else "White"
        elif result == 7:
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

    ## Window Control Methods ###
    def close_app(self):
        print("Exiting application")
        self.SM.shutdown()
        QApplication.quit()
        QApplication.processEvents()
        self.hide()
        self.close()
        sys.exit(0)
        
    def hide_app(self):
        self.hide()
        if self.promotion_window:
            self.promotion_window.hide()
        if not hasattr(self, 'tray_icon'):
            self.tray_icon = QSystemTrayIcon(self)
            iconPath = os.path.join(self.path, "ChessImgVec", "KingWhite.svg")
            svg_renderer = QSvgRenderer(iconPath)
            svg_pixmap = QPixmap(64, 64)
            svg_pixmap.fill(Qt.transparent)
            svg_renderer.render(QPainter(svg_pixmap))
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
            self.scrollbar_mode = 0
        
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
        self.check_hover(event.pos())

    def enterEvent(self, event):
        self.update()

    def leaveEvent(self, event):
        self.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = WindowGui()
    gui.show()
    sys.exit(app.exec_())