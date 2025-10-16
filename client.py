from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QAbstractSocket
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QHBoxLayout, QTextEdit, QLineEdit, 
                             QPushButton, QWidget, QLabel)
import sys

class WebSocketGUI(QMainWindow):
    def __init__(self, player_name):
        super().__init__()
        self.player_name = player_name
        self.websocket = QWebSocket()
        self.init_ui()
        self.connect_signals()
        
    def init_ui(self):
        self.setWindowTitle(f"Game Client - {self.player_name}")
        self.setGeometry(100, 100, 600, 500)
        
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Status
        self.status_label = QLabel("Disconnected")
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        
        # Input area
        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Enter your move or message...")
        self.send_button = QPushButton("Send")
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        
        input_layout.addWidget(self.message_input)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.connect_button)
        input_layout.addWidget(self.disconnect_button)
        
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.chat_display)
        main_layout.addLayout(input_layout)
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
    def connect_signals(self):
        self.send_button.clicked.connect(self.send_message)
        self.connect_button.clicked.connect(self.connect_to_server)
        self.disconnect_button.clicked.connect(self.disconnect_from_server)
        self.message_input.returnPressed.connect(self.send_message)
        
        # WebSocket signals
        self.websocket.connected.connect(self.on_connected)
        self.websocket.disconnected.connect(self.on_disconnected)
        self.websocket.textMessageReceived.connect(self.on_message_received)
        self.websocket.error.connect(self.on_error)
        
    def connect_to_server(self):
        # Change this URL to match your server
        url = QUrl("ws://localhost:8000/ws")
        self.websocket.open(url)
        self.status_label.setText("Connecting...")
        
    def disconnect_from_server(self):
        self.websocket.close()
        
    def send_message(self):
        message = self.message_input.text().strip()
        # Check if connected using state() method
        if message and self.websocket.state() == QAbstractSocket.ConnectedState:
            self.websocket.sendTextMessage(f"{self.player_name}: {message}")
            self.chat_display.append(f"You: {message}")
            self.message_input.clear()
        elif message:
            self.chat_display.append("Not connected to server!")
            
    def on_connected(self):
        self.status_label.setText("Connected")
        self.chat_display.append("Connected to server!")
        
    def on_disconnected(self):
        self.status_label.setText("Disconnected")
        self.chat_display.append("Disconnected from server!")
        
    def on_message_received(self, message):
        self.chat_display.append(message)
        
    def on_error(self, error):
        self.status_label.setText(f"Error: {error}")
        self.chat_display.append(f"WebSocket error: {error}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Get player name from command line argument or use default
    if len(sys.argv) > 1:
        player_name = sys.argv[1]
    else:
        player_name = "Player"
        
    window = WebSocketGUI(player_name)
    window.show()
    
    sys.exit(app.exec_())