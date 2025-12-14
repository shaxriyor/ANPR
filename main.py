import sys, os, cv2, numpy as np, re, time
from pathlib import Path
from datetime import datetime
from collections import deque

from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF
from PyQt6.QtGui import QPixmap, QImage, QFont, QColor, QDragEnterEvent, QDropEvent, QWheelEvent, QPainter

import warnings
warnings.filterwarnings('ignore')

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

# ============== UZBEKISTAN REGIONS ==============
UZ_REGIONS = {
    '01': 'Tashkent', '10': 'Tashkent Region', '20': 'Sirdarya', '25': 'Djizzak',
    '30': 'Samarkand', '40': 'Fergana', '50': 'Namangan',
    '60': 'Andijan', '70': 'Kashkadarya', '75': 'Surkhandarya',
    '80': 'Buhara', '85': 'Navoiy', '90': 'Khorezm', '95': 'Karakalpakstan',
}


class CustomOCR:
    """
    Custom OCR using trained YOLO model for character recognition.
    Supports recognition.pt model trained on license plate characters.
    """
    
    def __init__(self, model_path="recognition.pt"):
        self.model = None
        self.model_path = model_path
        self.char_map = None
        self.load_model()
    
    def load_model(self):
        """Load the custom OCR model"""
        paths_to_try = [
            self.model_path,
            f"models/{self.model_path}",
            Path.home() / self.model_path,
            Path(__file__).parent / self.model_path,
        ]
        
        for path in paths_to_try:
            if Path(path).exists():
                try:
                    self.model = YOLO(str(path))
                    print(f"✅ OCR Model loaded: {path}")
                    
                    # Get class names from model
                    if hasattr(self.model, 'names'):
                        self.char_map = self.model.names
                        print(f"   Classes: {self.char_map}")
                    return True
                except Exception as e:
                    print(f"❌ Error loading OCR model: {e}")
        
        print(f"⚠️ OCR model not found: {self.model_path}")
        return False
    
    def preprocess(self, img):
        """Preprocess image for better OCR"""
        if img is None or img.size == 0:
            return img
        
        # Resize if too small
        h, w = img.shape[:2]
        
        if w < 200:
            scale = 200 / w
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            
        return img
    
    def read(self, img, conf=0.3):
        """
        Read text from license plate image.
        
        Args:
            img: BGR image of license plate
            conf: confidence threshold
            
        Returns:
            str: recognized text
        """
        if self.model is None:
            return ""
        
        if img is None or img.size == 0:
            return ""
        
        # Preprocess
        img = self.preprocess(img)
        
        # Run detection
        results = self.model(img, conf=conf, verbose=False)
        
        # Extract characters with positions
        detections = []
        
        for result in results:
            if result.boxes is None:
                continue
            
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf_val = float(box.conf[0])
                cls_id = int(box.cls[0])
                
                # Get character from class name
                if self.char_map and cls_id in self.char_map:
                    char = str(self.char_map[cls_id])
                else:
                    char = str(cls_id)
                
                # Store with x position for sorting
                detections.append({
                    'char': char,
                    'x': x1,
                    'y': y1,
                    'conf': conf_val
                })
        
        if not detections:
            return ""
        
        # Sort by x position (left to right)
        detections.sort(key=lambda d: d['x'])
        
        # Combine characters
        text = ''.join([d['char'] for d in detections])
        
        return text.upper()


def format_uz_plate(raw_text):
    """Format OCR text to Uzbekistan plate format"""
    text = re.sub(r'[^A-Z0-9]', '', raw_text.upper())
    
    if len(text) < 6:
        return text, None, None
    
    # Try to find region code
    region_code = None
    region_name = None
    
    # Check first 2 characters
    if len(text) >= 2 and text[:2] in UZ_REGIONS:
        region_code = text[:2]
        region_name = UZ_REGIONS[region_code]
        body = text[2:]
    else:
        # Try common OCR corrections for region
        corrections = {
            '61': '01', '6I': '01', 'O1': '01', 'OI': '01',
            'I0': '10', '1O': '10', 'IO': '10',
            'E0': '30', '3O': '30', 'EO': '30',
            'S0': '50', '5O': '50',
        }
        
        first_two = text[:2]
        if first_two in corrections:
            region_code = corrections[first_two]
            region_name = UZ_REGIONS.get(region_code)
            body = text[2:]
        else:
            return text, None, None
    
    if len(body) < 5:
        return f"{region_code} {body}", region_name, None
    
    # Determine format
    # Individual: A 123 BC (1 letter + 3 digits + 2 letters)
    # Legal: 123 ABC (3 digits + 3 letters)
    
    if body[0].isalpha():
        # Individual format
        letter1 = body[0]
        rest = body[1:]
        
        digits = ''.join([c for c in rest if c.isdigit()][:3])
        letters = ''.join([c for c in rest if c.isalpha()][:2])
        
        if len(digits) >= 3 and len(letters) >= 2:
            formatted = f"{region_code} {letter1} {digits} {letters}"
            return formatted, region_name, "individual"
    else:
        # Legal format
        digits = ''.join([c for c in body if c.isdigit()][:3])
        letters = ''.join([c for c in body if c.isalpha()][:3])
        
        if len(digits) >= 3 and len(letters) >= 2:
            formatted = f"{region_code} {digits} {letters}"
            return formatted, region_name, "legal"
    
    return f"{region_code} {body}", region_name, None


class DetectionResult:
    def __init__(self, image_path, bbox, confidence, plate_text="", region=""):
        self.image_path = image_path
        self.bbox = bbox
        self.confidence = confidence
        self.plate_text = plate_text
        self.region = region
        self.timestamp = datetime.now()


class ZoomableView(QGraphicsView):
    """Zoomable image view with mouse wheel zoom"""
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = None
        self.zoom_factor = 1.0
        
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setStyleSheet("QGraphicsView { background: #1a1a2e; border: 2px solid #2d2d44; border-radius: 8px; }")
        self.show_placeholder()
    
    def show_placeholder(self):
        self.scene.clear()
        self.pixmap_item = None
        text = self.scene.addText("📷 Drag & Drop Images/Video\nor click 'Load'")
        text.setDefaultTextColor(QColor("#8888aa"))
        text.setFont(QFont("Segoe UI", 12))
        rect = text.boundingRect()
        text.setPos(-rect.width()/2, -rect.height()/2)
    
    def set_image(self, pixmap):
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        self.zoom_factor = 1.0
        self.resetTransform()
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    
    def wheelEvent(self, event: QWheelEvent):
        if not self.pixmap_item:
            return
        zoom = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        new_zoom = self.zoom_factor * zoom
        if 0.1 <= new_zoom <= 10:
            self.zoom_factor = new_zoom
            self.scale(zoom, zoom)
    
    def reset_zoom(self):
        if self.pixmap_item:
            self.resetTransform()
            self.zoom_factor = 1.0
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


class DetectionWorker(QThread):
    progress = pyqtSignal(int)
    result = pyqtSignal(object, object, list)
    finished = pyqtSignal()
    
    def __init__(self, model, ocr, files, conf=0.25, use_ocr=True):
        super().__init__()
        self.model = model
        self.ocr = ocr  # CustomOCR instance
        self.files = files
        self.conf = conf
        self.use_ocr = use_ocr
        self.running = True
    
    def stop(self):
        self.running = False
    
    def run(self):
        for i, f in enumerate(self.files):
            if not self.running:
                break
            
            img = cv2.imread(str(f))
            if img is None:
                continue
            
            results = self.model(img, conf=self.conf, verbose=False)
            detections = []
            annotated = img.copy()
            
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    plate_text, region = "", ""
                    
                    if self.use_ocr and self.ocr:
                        try:
                            # Extract plate ROI with padding
                            pad = 5
                            y1_pad = max(0, y1 - pad)
                            y2_pad = min(img.shape[0], y2 + pad)
                            x1_pad = max(0, x1 - pad)
                            x2_pad = min(img.shape[1], x2 + pad)
                            
                            roi = img[y1_pad:y2_pad, x1_pad:x2_pad]
                            
                            if roi.size > 0:
                                # Use custom OCR
                                raw_text = self.ocr.read(roi)
                                
                                if raw_text:
                                    plate_text, region, _ = format_uz_plate(raw_text)
                        except Exception as e:
                            print(f"OCR Error: {e}")
                    
                    # Draw
                    color = (0, 255, 0) if plate_text else (0, 255, 255)
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    label = f"{plate_text} ({conf:.2f})" if plate_text else f"({conf:.2f})"
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    cv2.rectangle(annotated, (x1, y1-25), (x1+tw+8, y1), color, -1)
                    cv2.putText(annotated, label, (x1+4, y1-7), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 2)
                    
                    if region:
                        cv2.putText(annotated, region, (x1, y2+18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,136), 1)
                    
                    detections.append(DetectionResult(str(f), (x1,y1,x2,y2), conf, plate_text, region))
            
            self.result.emit(img, annotated, detections)
            self.progress.emit(int((i+1)/len(self.files)*100))
        
        self.finished.emit()


class VideoWorker(QThread):
    frame_ready = pyqtSignal(object, list)
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    fps_update = pyqtSignal(float)
    
    def __init__(self, model, ocr, path, conf=0.25, use_ocr=True):
        super().__init__()
        self.model = model
        self.ocr = ocr
        self.path = path
        self.conf = conf
        self.use_ocr = use_ocr
        self.running = True
        self.paused = False
    
    def stop(self): 
        self.running = False
    
    def pause(self): 
        self.paused = not self.paused
    
    def run(self):
        cap = cv2.VideoCapture(self.path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_q = deque(maxlen=30)
        
        while self.running and cap.isOpened():
            if self.paused:
                time.sleep(0.1)
                continue
            
            t0 = time.time()
            ret, frame = cap.read()
            if not ret:
                break
            
            curr = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            results = self.model(frame, conf=self.conf, verbose=False)
            
            detections = []
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    plate_text, region = "", ""
                    
                    # OCR every 5 frames for performance
                    if self.use_ocr and self.ocr and curr % 5 == 0:
                        try:
                            roi = frame[y1:y2, x1:x2]
                            if roi.size > 0:
                                raw_text = self.ocr.read(roi)
                                if raw_text:
                                    plate_text, region, _ = format_uz_plate(raw_text)
                        except:
                            pass
                    
                    color = (0, 255, 0) if plate_text else (0, 255, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    label = plate_text if plate_text else f"{conf:.2f}"
                    cv2.putText(frame, label, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    
                    if plate_text:
                        detections.append(DetectionResult(self.path, (x1,y1,x2,y2), conf, plate_text, region))
            
            fps_q.append(1/(time.time()-t0+0.001))
            self.frame_ready.emit(frame, detections)
            self.progress.emit(int(curr/total*100))
            self.fps_update.emit(sum(fps_q)/len(fps_q))
        
        cap.release()
        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ANPR - Uzbekistan Plates")
        self.setMinimumSize(1366, 720)
        
        self.model = None      # Detection model (best.pt)
        self.ocr = None        # OCR model (recognition.pt)
        self.det_worker = None
        self.vid_worker = None
        self.detections = []
        self.images = []
        self.idx = 0
        
        self.setup_ui()
        self.setup_style()
        self.load_models()
    
    def setup_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #0f0f1a; color: #e0e0e0; font-family: 'Segoe UI'; }
            QPushButton { background: #2d2d44; border: none; border-radius: 8px; padding: 10px 20px; font-weight: bold; }
            QPushButton:hover { background: #3d3d5c; }
            QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #00d4ff,stop:1 #00ff88); color: #000; }
            QPushButton#danger { background: #ff4444; }
            QGroupBox { border: 1px solid #2d2d44; border-radius: 8px; margin-top: 12px; font-weight: bold; color: #00d4ff; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QTableWidget { background: #1a1a2e; border: 1px solid #2d2d44; border-radius: 8px; }
            QTableWidget::item:selected { background: #00d4ff; color: #000; }
            QHeaderView::section { background: #2d2d44; padding: 6px; border: none; color: #00d4ff; }
            QProgressBar { border: none; border-radius: 5px; background: #2d2d44; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #00d4ff,stop:1 #00ff88); border-radius: 5px; }
            QSlider::groove:horizontal { height: 6px; background: #2d2d44; border-radius: 3px; }
            QSlider::handle:horizontal { background: #00d4ff; width: 16px; margin: -5px 0; border-radius: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; background: #2d2d44; }
            QCheckBox::indicator:checked { background: #00d4ff; }
            QLabel#status_ok { color: #00ff88; }
            QLabel#status_warn { color: #ffaa00; }
            QLabel#status_err { color: #ff4444; }
        """)
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # === LEFT PANEL ===
        left = QWidget()
        left.setFixedWidth(300)
        ll = QVBoxLayout(left)
        ll.setSpacing(10)
        
        # Title
        title = QLabel("ANPR System - 45 team")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #00d4ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(title)

        
        # Models status (grid for perfect left alignment)
        models_group = QGroupBox("🤖 Models")
        models_layout = QGridLayout(models_group)
        models_layout.setContentsMargins(10, 8, 10, 8)
        models_layout.setHorizontalSpacing(8)
        models_layout.setVerticalSpacing(4)

        # Left column: labels (names). Right column: status values.
        lbl_detection = QLabel("Detection:")
        lbl_detection.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_detection.setStyleSheet("padding-right:6px;")  # небольшой отступ между колонками

        self.detect_label = QLabel("⏳ Loading...")
        self.detect_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.detect_label.setStyleSheet("padding:4px;")

        lbl_ocr = QLabel("OCR:")
        lbl_ocr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_ocr.setStyleSheet("padding-right:6px;")

        self.ocr_label = QLabel("⏳ Loading...")
        self.ocr_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.ocr_label.setStyleSheet("padding:4px;")

        lbl_gpu = QLabel("GPU:")
        lbl_gpu.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_gpu.setStyleSheet("padding-right:6px;")

        self.gpu_label = QLabel("Checking...")
        self.gpu_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.gpu_label.setStyleSheet("color: #88c070; font-size: 11px; padding:4px;")  # пример зелёного статуса

        # add to grid: (row, column)
        models_layout.addWidget(lbl_detection, 0, 0)
        models_layout.addWidget(self.detect_label, 0, 1)

        models_layout.addWidget(lbl_ocr, 1, 0)
        models_layout.addWidget(self.ocr_label, 1, 1)

        models_layout.addWidget(lbl_gpu, 2, 0)
        models_layout.addWidget(self.gpu_label, 2, 1)

        # Make right column expand, left column keep minimal width
        models_layout.setColumnStretch(0, 0)
        models_layout.setColumnStretch(1, 1)

        ll.addWidget(models_group)


        
        # Input
        inp = QGroupBox("📂 Input")
        il = QVBoxLayout(inp)
        
        self.btn_img = QPushButton("🖼️ Load Images")
        self.btn_img.setObjectName("primary")
        self.btn_img.clicked.connect(self.load_images)
        il.addWidget(self.btn_img)
        
        self.btn_folder = QPushButton("📁 Load Folder")
        self.btn_folder.clicked.connect(self.load_folder)
        il.addWidget(self.btn_folder)
        
        self.btn_video = QPushButton("🎬 Load Video")
        self.btn_video.clicked.connect(self.load_video)
        il.addWidget(self.btn_video)
        
        ll.addWidget(inp)
        
        # Settings
        sett = QGroupBox("⚙️ Settings")
        sl = QVBoxLayout(sett)
        
        # Confidence slider
        cl = QHBoxLayout()
        cl.addWidget(QLabel("Confidence:"))
        self.conf_slider = QSlider(Qt.Orientation.Horizontal)
        self.conf_slider.setRange(1, 99)
        self.conf_slider.setValue(25)
        self.conf_slider.valueChanged.connect(lambda v: self.conf_lbl.setText(f"{v/100:.2f}"))
        cl.addWidget(self.conf_slider)
        self.conf_lbl = QLabel("0.25")
        cl.addWidget(self.conf_lbl)
        sl.addLayout(cl)
        
        self.ocr_check = QCheckBox("Enable OCR")
        self.ocr_check.setChecked(True)
        sl.addWidget(self.ocr_check)
        
        ll.addWidget(sett)
        
        # Zoom
        zoom = QGroupBox("🔍 Zoom")
        zl = QVBoxLayout(zoom)
        zl.addWidget(QLabel("Mouse wheel = zoom\nDrag = pan"))
        self.btn_reset = QPushButton("↺ Reset Zoom")
        self.btn_reset.clicked.connect(lambda: self.view.reset_zoom())
        zl.addWidget(self.btn_reset)
        ll.addWidget(zoom)
        
        # Video controls
        vid = QGroupBox("🎬 Video")
        vl = QVBoxLayout(vid)
        bl = QHBoxLayout()
        self.btn_play = QPushButton("▶️")
        self.btn_play.clicked.connect(self.toggle_video)
        self.btn_play.setEnabled(False)
        bl.addWidget(self.btn_play)
        self.btn_stop = QPushButton("⏹️")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.clicked.connect(self.stop_video)
        self.btn_stop.setEnabled(False)
        bl.addWidget(self.btn_stop)
        vl.addLayout(bl)
        self.fps_lbl = QLabel("FPS: --")
        self.fps_lbl.setStyleSheet("color: #00ff88;")
        vl.addWidget(self.fps_lbl)
        ll.addWidget(vid)
        
        self.btn_export = QPushButton("💾 Export CSV")
        self.btn_export.clicked.connect(self.export)
        ll.addWidget(self.btn_export)
        
        ll.addStretch()
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        ll.addWidget(self.progress)
        
        layout.addWidget(left)
        
        # === CENTER PANEL ===
        center = QWidget()
        cl = QVBoxLayout(center)
        
        self.view = ZoomableView()
        
        # Drag & drop wrapper
        wrapper = QWidget()
        wrapper.setAcceptDrops(True)
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.addWidget(self.view)
        wrapper.dragEnterEvent = lambda e: e.acceptProposedAction() if e.mimeData().hasUrls() else None
        wrapper.dropEvent = lambda e: self.handle_drop([u.toLocalFile() for u in e.mimeData().urls()])
        cl.addWidget(wrapper)
        
        # Navigation
        nav = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Prev")
        self.btn_prev.clicked.connect(self.prev_img)
        self.btn_prev.setEnabled(False)
        nav.addWidget(self.btn_prev)
        
        self.img_lbl = QLabel("No images")
        self.img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.img_lbl)
        
        self.btn_next = QPushButton("Next ▶")
        self.btn_next.clicked.connect(self.next_img)
        self.btn_next.setEnabled(False)
        nav.addWidget(self.btn_next)
        cl.addLayout(nav)
        
        layout.addWidget(center, stretch=2)
        
        # === RIGHT PANEL ===
        right = QWidget()
        right.setFixedWidth(400)
        rl = QVBoxLayout(right)
        
        # Stats
        stats = QGroupBox("📊 Statistics")
        stl = QVBoxLayout(stats)
        self.stat_det = QLabel("Detections: 0")
        self.stat_img = QLabel("Images: 0")
        self.stat_conf = QLabel("Avg Conf: --")
        stl.addWidget(self.stat_det)
        stl.addWidget(self.stat_img)
        stl.addWidget(self.stat_conf)
        rl.addWidget(stats)
        
        rl.addWidget(QLabel("📋 Detection Results"))
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["#", "Plate", "Region", "Conf", "File"])
        self.table.setColumnWidth(0, 30)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 45)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellClicked.connect(self.on_table_click)
        

        
        rl.addWidget(self.table)
        
        self.btn_clear = QPushButton("🗑️ Clear Results")
        self.btn_clear.clicked.connect(self.clear)
        rl.addWidget(self.btn_clear)
        
        layout.addWidget(right)
        
        self.statusBar().showMessage("Ready. Load images or video to start.")
    
    def load_models(self):
        """Load detection and OCR models"""
        
        # Check GPU
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                self.gpu_label.setText(f"✅ {gpu_name}")
                self.gpu_label.setStyleSheet("color: #00ff88; font-size: 10px;")
            else:
                self.gpu_label.setText("❌ CPU mode")
                self.gpu_label.setStyleSheet("color: #ffaa00; font-size: 10px;")
        except:
            self.gpu_label.setText("GPU: Unknown")
        
        # Load detection model
        if not YOLO_AVAILABLE:
            self.detect_label.setText("❌ YOLO not installed")
            return
        
        try:
            det_paths = ["best.pt", "models/best.pt", Path.home() / "best.pt"]
            det_path = next((p for p in det_paths if Path(p).exists()), None)
            
            if det_path:
                self.model = YOLO(str(det_path))
                self.detect_label.setText(f"✅ {Path(det_path).name}")
                self.detect_label.setStyleSheet("color: #00ff88; padding: 5px;")
            else:
                self.model = YOLO("yolo12s.pt")
                self.detect_label.setText("⚠️ Default model")
                self.detect_label.setStyleSheet("color: #ffaa00; padding: 5px;")
        except Exception as e:
            self.detect_label.setText(f"❌ {str(e)[:20]}")
            self.detect_label.setStyleSheet("color: #ff4444; padding: 5px;")
        
        # Load OCR model
        try:
            self.ocr = CustomOCR("recognition.pt")
            
            if self.ocr.model is not None:
                self.ocr_label.setText("✅ recognition.pt")
                self.ocr_label.setStyleSheet("color: #00ff88; padding: 5px;")
            else:
                self.ocr_label.setText("❌ Model not found")
                self.ocr_label.setStyleSheet("color: #ff4444; padding: 5px;")
                self.statusBar().showMessage("⚠️ Put recognition.pt in app folder!")
        except Exception as e:
            self.ocr_label.setText(f"❌ {str(e)[:20]}")
            self.ocr_label.setStyleSheet("color: #ff4444; padding: 5px;")
    
    def load_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", "", 
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if files:
            self.process(files)
    
    def load_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            exts = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.webp']
            files = []
            for ext in exts:
                files.extend(Path(folder).glob(ext))
            if files:
                self.process([str(f) for f in files])
    
    def load_video(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "",
            "Videos (*.mp4 *.avi *.mov *.mkv)"
        )
        if f:
            self.start_video(f)
    
    def handle_drop(self, files):
        imgs = [f for f in files if Path(f).suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp', '.webp']]
        vids = [f for f in files if Path(f).suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv']]
        
        if vids:
            self.start_video(vids[0])
        elif imgs:
            self.process(imgs)
    
    def process(self, files):
        if not self.model:
            QMessageBox.warning(self, "Error", "Detection model not loaded!")
            return
        
        self.images = []
        self.idx = 0
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        ocr = self.ocr if self.ocr_check.isChecked() and self.ocr and self.ocr.model else None
        
        self.det_worker = DetectionWorker(
            self.model, ocr, files,
            self.conf_slider.value() / 100,
            self.ocr_check.isChecked()
        )
        self.det_worker.progress.connect(self.progress.setValue)
        self.det_worker.result.connect(self.on_result)
        self.det_worker.finished.connect(self.on_finished)
        self.det_worker.start()
        
        self.statusBar().showMessage(f"Processing {len(files)} images...")
    
    def on_result(self, orig, annot, dets):
        self.images.append((orig, annot, dets))
        
        if len(self.images) == 1:
            self.show_img(0)
        
        for d in dets:
            self.detections.append(d)
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            self.table.setItem(r, 1, QTableWidgetItem(d.plate_text or "N/A"))
            self.table.setItem(r, 2, QTableWidgetItem(d.region or "-"))
            self.table.setItem(r, 3, QTableWidgetItem(f"{d.confidence:.2f}"))
            self.table.setItem(r, 4, QTableWidgetItem(Path(d.image_path).name))
        
        self.update_stats()
    
    def on_finished(self):
        self.progress.setVisible(False)
        n = len(self.images)
        self.btn_prev.setEnabled(n > 1)
        self.btn_next.setEnabled(n > 1)
        self.img_lbl.setText(f"1 / {n}" if n else "No images")
        self.statusBar().showMessage(f"✅ Done! Found {len(self.detections)} plates in {n} images")
    
    def start_video(self, path):
        if not self.model:
            return
        
        self.progress.setVisible(True)
        self.btn_play.setEnabled(True)
        self.btn_stop.setEnabled(True)
        
        ocr = self.ocr if self.ocr_check.isChecked() and self.ocr and self.ocr.model else None
        
        self.vid_worker = VideoWorker(
            self.model, ocr, path,
            self.conf_slider.value() / 100,
            self.ocr_check.isChecked()
        )
        self.vid_worker.frame_ready.connect(self.on_frame)
        self.vid_worker.progress.connect(self.progress.setValue)
        self.vid_worker.fps_update.connect(lambda f: self.fps_lbl.setText(f"FPS: {f:.1f}"))
        self.vid_worker.finished.connect(self.on_vid_done)
        self.vid_worker.start()
        
        self.btn_play.setText("⏸️")
        self.statusBar().showMessage(f"Processing video: {Path(path).name}")
    
    def on_frame(self, frame, dets):
        self.display_cv(frame)
        
        for d in dets:
            if d.plate_text:
                self.detections.append(d)
                r = self.table.rowCount()
                if r > 100:
                    self.table.removeRow(0)
                    r = 100
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(len(self.detections))))
                self.table.setItem(r, 1, QTableWidgetItem(d.plate_text))
                self.table.setItem(r, 2, QTableWidgetItem(d.region or "-"))
                self.table.setItem(r, 3, QTableWidgetItem(f"{d.confidence:.2f}"))
                self.table.setItem(r, 4, QTableWidgetItem("Video"))
        
        self.update_stats()
    
    def on_vid_done(self):
        self.progress.setVisible(False)
        self.btn_play.setText("▶️")
        self.btn_play.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.statusBar().showMessage("Video processing complete!")
    
    def toggle_video(self):
        if self.vid_worker:
            self.vid_worker.pause()
            self.btn_play.setText("▶️" if self.vid_worker.paused else "⏸️")
    
    def stop_video(self):
        if self.vid_worker:
            self.vid_worker.stop()
            self.vid_worker.wait()
            self.vid_worker = None
        
        self.btn_play.setText("▶️")
        self.btn_play.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.progress.setVisible(False)
    
    def show_img(self, i):
        if 0 <= i < len(self.images):
            self.idx = i
            _, annot, _ = self.images[i]
            self.display_cv(annot)
            self.img_lbl.setText(f"{i + 1} / {len(self.images)}")
    
    def display_cv(self, img):
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.view.set_image(QPixmap.fromImage(qimg))
    
    def prev_img(self):
        if self.idx > 0:
            self.show_img(self.idx - 1)
    
    def next_img(self):
        if self.idx < len(self.images) - 1:
            self.show_img(self.idx + 1)
    
    def update_stats(self):
        n = len(self.detections)
        self.stat_det.setText(f"Detections: {n}")
        self.stat_img.setText(f"Images: {len(self.images)}")
        if n:
            avg = sum(d.confidence for d in self.detections) / n
            self.stat_conf.setText(f"Avg Conf: {avg:.2f}")
    
    def on_table_click(self, row, col):
        if row < len(self.detections):
            d = self.detections[row]
            for i, (_, _, dets) in enumerate(self.images):
                if d in dets:
                    self.show_img(i)
                    break
    
    def clear(self):
        self.detections.clear()
        self.images.clear()
        self.idx = 0
        self.table.setRowCount(0)
        self.view.show_placeholder()
        self.update_stats()
        self.img_lbl.setText("No images")
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
    
    def export(self):
        if not self.detections:
            QMessageBox.information(self, "Export", "No results to export!")
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results",
            f"anpr_{datetime.now():%Y%m%d_%H%M%S}.csv",
            "CSV Files (*.csv)"
        )
        
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write("Plate,Region,Confidence,File,Timestamp\n")
                for d in self.detections:
                    f.write(f'"{d.plate_text}","{d.region}",{d.confidence:.3f},')
                    f.write(f'"{Path(d.image_path).name}",{d.timestamp}\n')
            
            self.statusBar().showMessage(f"Exported to {path}")
            QMessageBox.information(self, "Export", f"Results exported to:\n{path}")
    
    def closeEvent(self, e):
        if self.det_worker:
            self.det_worker.stop()
            self.det_worker.wait()
        if self.vid_worker:
            self.vid_worker.stop()
            self.vid_worker.wait()
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    win = MainWindow()
    win.show()
    
    sys.exit(app.exec())