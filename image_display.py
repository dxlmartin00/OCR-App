
from typing import List, Dict
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor

class ImageDisplayWidget(QLabel):
    """Custom widget to display image with text boxes"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 300)
        self.setStyleSheet("border: 1px solid gray;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("No image selected")
        self.original_pixmap = None
        self.text_boxes = []
        
    def set_image(self, image_path: str):
        """Load and display image"""
        try:
            self.original_pixmap = QPixmap(image_path)
            self.display_image()
        except Exception as e:
            self.setText(f"Error loading image: {str(e)}")
            
    def set_text_boxes(self, text_data: List[Dict]):
        """Set text boxes to overlay on image"""
        self.text_boxes = text_data
        self.display_image()
        
    def display_image(self):
        """Display image with text boxes"""
        if not self.original_pixmap:
            return
            
        # Scale pixmap to fit widget
        scaled_pixmap = self.original_pixmap.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Draw text boxes if available
        if self.text_boxes:
            painter = QPainter(scaled_pixmap)
            pen = QPen(QColor(255, 0, 0), 2)
            painter.setPen(pen)
            
            # Calculate scaling factors
            scale_x = scaled_pixmap.width() / self.original_pixmap.width()
            scale_y = scaled_pixmap.height() / self.original_pixmap.height()
            
            for text_item in self.text_boxes:
                coords = text_item['coordinates']
                # Scale coordinates
                points = [
                    (int(coords['top_left'][0] * scale_x), 
                     int(coords['top_left'][1] * scale_y)),
                    (int(coords['top_right'][0] * scale_x), 
                     int(coords['top_right'][1] * scale_y)),
                    (int(coords['bottom_right'][0] * scale_x), 
                     int(coords['bottom_right'][1] * scale_y)),
                    (int(coords['bottom_left'][0] * scale_x), 
                     int(coords['bottom_left'][1] * scale_y))
                ]
                
                # Draw rectangle
                for i in range(4):
                    painter.drawLine(points[i][0], points[i][1], 
                                   points[(i+1)%4][0], points[(i+1)%4][1])
            
            painter.end()
        
        self.setPixmap(scaled_pixmap)
